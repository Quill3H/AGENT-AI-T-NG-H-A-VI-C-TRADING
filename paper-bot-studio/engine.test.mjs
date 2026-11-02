import test from 'node:test';
import assert from 'node:assert/strict';
import {newState,cycleFor,acceptDecision,replayTrades,applyFunding,walletMetrics} from './engine.mjs';
const now=Date.UTC(2026,9,31,12);
const context={id:'context-15m-1',frame:'15m',cycleAt:now,capturedAt:now,expiresAt:now+240000};
const quote={symbol:'SOLUSDT',bid:99.99,ask:100,time:now};
const rules={stepSize:.001,minQty:.001,maxQty:100000,minNotional:5,tickSize:.01};
const decision={contextId:context.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'Price action',reason:'Closed candle support',invalidation:'Break support'};
function opened(){const state=newState(now);acceptDecision(state,decision,context,quote,rules,now);return {state,wallet:state.wallets[0],trade:state.wallets[0].trades[0]};}
test('three wallets own separate $100 balances and UTC cycles',()=>{
 const state=newState(now);assert.deepEqual(state.wallets.map(w=>w.balance),[100,100,100]);
 state.wallets[0].balance=90;assert.equal(state.wallets[1].balance,100);
 assert.equal(cycleFor('4h',now+7200000),now);assert.equal(cycleFor('15m',now+899999),now);
});
test('sizing uses cash, spread, adverse slippage and fees; books entry fee once',()=>{
 const {state,wallet,trade}=opened();assert.equal(trade.status,'OPEN');
 assert.equal(trade.entry,100.02);assert.equal(trade.qty,.279);
 assert.ok(trade.plannedLoss>1&&trade.plannedLoss<2);assert.ok(trade.notional<28);assert.equal(trade.leverage,7);assert.ok(trade.initialMargin<=4);
 assert.ok(Math.abs(wallet.balance-(100-trade.entryFee))<1e-10);assert.equal(state.wallets[1].balance,100);
});
test('rejects stale, future, mismatched, malformed and out-of-bound AI decisions without money mutation',()=>{
 for(const change of [{allocationPct:.029},{allocationPct:.051},{allocationPct:'0.04'},{sl:101},{tp:90},{sl:95.001},{reason:''},{contextId:'wrong'},{frame:'4h'},{action:'BUY'},{symbol:'UNKNOWN'}]){
  const s=newState(now);assert.throws(()=>acceptDecision(s,{...decision,...change},context,quote,rules,now));assert.equal(s.wallets[0].balance,100);assert.equal(s.wallets[0].decisions.length,0);
 }
 for(const clock of [now-1,now+240001])assert.throws(()=>acceptDecision(newState(now),decision,context,quote,rules,clock));
 assert.throws(()=>acceptDecision(newState(now),decision,context,{...quote,time:now-15001},rules,now));
 assert.throws(()=>acceptDecision(newState(now),decision,context,{...quote,bid:101},rules,now));
});
test('allocation sizing is independent of stop distance and rejects minimum-notional failures',()=>{
 const s=newState(now);acceptDecision(s,{...decision,sl:99},context,quote,rules,now);assert.equal(s.wallets[0].trades[0].qty,.279);
 assert.throws(()=>acceptDecision(newState(now),decision,context,quote,{...rules,minNotional:1000},now),/notional/i);
});
test('a duplicate cycle cannot create another trade but a new cycle can accumulate allocated margin above5%',()=>{
 const {state,wallet}=opened();const balance=wallet.balance;
 assert.throws(()=>acceptDecision(state,decision,context,quote,rules,now),/duplicate/i);
 const next={...context,id:'context-2',cycleAt:now+900000,capturedAt:now+900000,expiresAt:now+1140000};
 const original=structuredClone(wallet.trades[0]);
 acceptDecision(state,{...decision,contextId:next.id},next,{...quote,time:now+900000},rules,now+900000);
 assert.equal(wallet.trades.length,2);assert.ok(wallet.balance<balance);
 assert.ok(wallet.trades.reduce((s,t)=>s+t.initialMargin,0)>7);assert.ok(walletMetrics(wallet,quote).notional>50);
 assert.deepEqual(wallet.trades[0],original);assert.equal(state.wallets[1].balance,100);
 assert.equal(wallet.trades[1].riskBasis,'BOOKED_BALANCE_BEFORE_ENTRY');assert.equal(wallet.trades[1].balanceAtEntry,balance);
 assert.throws(()=>acceptDecision(state,{...decision,contextId:next.id},next,{...quote,time:now+900000},rules,now+900000),/duplicate/i);
});
test('routine HOLD cannot consume a mandatory entry slot or fabricate a trade',()=>{
 const state=newState(now);assert.throws(()=>acceptDecision(state,{contextId:context.id,frame:'15m',action:'HOLD',method:'Trend filter',reason:'No entry',invalidation:'Await breakout'},context,null,null,now),/LONG.*SHORT|mandatory/i);
 assert.equal(state.wallets[0].trades.length,0);assert.equal(state.wallets[0].decisions.length,0);
});
test('new schema needs only per-trade allocation and independent trades settle without changing each other levels',()=>{
 const state=newState(now),d={...decision};delete d.riskPct;
 acceptDecision(state,d,context,quote,rules,now);
 const next={...context,id:'context-2',cycleAt:now+900000,capturedAt:now+900000,expiresAt:now+1140000};
 acceptDecision(state,{...d,contextId:next.id,action:'SHORT',sl:105,tp:90},next,{...quote,time:now+900000},rules,now+900000);
 const w=state.wallets[0],first=w.trades[0],second=w.trades[1],levels=w.trades.map(t=>[t.sl,t.tp]);
 replayTrades(w,first,[{a:1,p:'111',T:now+900001}]);replayTrades(w,second,[{a:2,p:'111',T:now+900001}]);
 assert.equal(first.status,'TP');assert.equal(second.status,'SL');assert.deepEqual(w.trades.map(t=>[t.sl,t.tp]),levels);
 assert.ok(Math.abs(w.balance-(100+first.pnl+second.pnl))<1e-9);assert.equal(state.wallets[1].balance,100);
});
test('chronological trade replay skips pre-entry, settles first touch and never rewrites closed trades',()=>{
 const {wallet,trade}=opened();const entry=trade.openedAt;
 replayTrades(wallet,trade,[{a:1,p:'90',T:entry-1},{a:2,p:'101',T:entry+1},{a:3,p:'94',T:entry+2},{a:4,p:'111',T:entry+3}]);
 assert.equal(trade.status,'SL');assert.equal(trade.closedAt,entry+2);assert.equal(trade.exit,94*(1-.0002));
 assert.ok(trade.pnl< -trade.plannedLoss);const balance=wallet.balance;
 replayTrades(wallet,trade,[{a:4,p:'111',T:entry+3}]);assert.equal(wallet.balance,balance);
 assert.ok(Math.abs(wallet.balance-(100+trade.pnl))<1e-9);
});
test('short first-touch TP and net PnL include both fees',()=>{
 const state=newState(now);acceptDecision(state,{...decision,action:'SHORT',sl:105,tp:90},context,quote,rules,now);
 const wallet=state.wallets[0],trade=wallet.trades[0];replayTrades(wallet,trade,[{a:1,p:'89',T:now+1}]);
 assert.equal(trade.status,'TP');assert.equal(trade.exit,90*(1+.0002));assert.ok(trade.pnl>0);
 assert.ok(Math.abs(wallet.balance-(100+trade.pnl))<1e-9);
});
test('funding debits long, credits short, ignores pre-entry/future/duplicates and reconciles closed pnl',()=>{
 const {wallet,trade}=opened();const balance=wallet.balance;
 const event={fundingTime:now+1000,fundingRate:'.001',markPrice:'100'};
 applyFunding(wallet,trade,[{...event,fundingTime:now-1},event,event,{...event,fundingTime:now+9999}],now+1000);
 assert.ok(Math.abs(wallet.balance-(balance-trade.qty*.1))<1e-9);assert.equal(trade.fundingEvents.length,1);
 replayTrades(wallet,trade,[{a:1,p:'111',T:now+1500}]);
 const closedBalance=wallet.balance;applyFunding(wallet,trade,[{...event,fundingTime:now+2000}],now+3000);assert.equal(wallet.balance,closedBalance);
 assert.ok(Math.abs(wallet.balance-(100+trade.pnl))<1e-9);
});
test('equity marks open positions after estimated exit costs without mixing realized balance',()=>{
 const {wallet,trade}=opened();const metrics=walletMetrics(wallet,{bid:101,ask:101.01,time:now});
 assert.ok(metrics.equity>wallet.balance);assert.equal(metrics.openRisk,trade.plannedLoss);assert.equal(metrics.openCount,1);
});
test('late funding correction appends an accounting point instead of rewriting a later trade result',()=>{
 const {wallet,trade}=opened();replayTrades(wallet,trade,[{a:1,p:'111',T:now+1000}]);wallet.curve.push({time:now+2000,value:wallet.balance});
 const lastValue=wallet.curve.at(-1).value;
 applyFunding(wallet,trade,[{fundingTime:now+500,fundingRate:'.001',markPrice:'100'}],now+3000);
 assert.equal(wallet.curve.at(-2).value,lastValue);assert.equal(wallet.curve.at(-1).time,now+3000);assert.ok(wallet.curve.at(-1).value<lastValue);
});
test('catch-up curve uses booking time even when older and newer positions closed out of event order',()=>{
 const {state,wallet,trade:first}=opened();
 const next={...context,id:'context-2',cycleAt:now+900000,capturedAt:now+900000,expiresAt:now+1140000};
 acceptDecision(state,{...decision,contextId:next.id},next,{...quote,time:now+900000},rules,now+900000);const second=wallet.trades[1];
 replayTrades(wallet,first,[{a:1,p:'111',T:now+900003}],now+1000000);
 replayTrades(wallet,second,[{a:2,p:'111',T:now+900002}],now+1000001);
 assert.equal(first.closedAt,now+900003);assert.equal(second.closedAt,now+900002);
 assert.deepEqual(wallet.curve.slice(-2).map(p=>p.time),[now+1000000,now+1000001]);
 assert.deepEqual(wallet.curve.slice(-2).map(p=>p.eventTime),[now+900003,now+900002]);
 applyFunding(wallet,first,[{fundingTime:now+500,fundingRate:'.001',markPrice:'100'}],first.closedAt,now+1000002);
 assert.equal(wallet.curve.at(-1).time,now+1000002);assert.equal(wallet.curve.at(-1).eventTime,now+500);
});

test("per-symbol leverage multiplies allocated margin, not SL risk or PnL twice",()=>{
 for(const [symbol,leverage] of Object.entries({BTCUSDT:15,HYPEUSDT:5,SOLUSDT:7,ETHUSDT:10})){const s=newState(now);acceptDecision(s,{...decision,symbol},context,{...quote,symbol},rules,now);const t=s.wallets[0].trades[0];assert.equal(t.leverage,leverage);assert.ok(t.notional<=4*leverage);assert.ok(4*leverage-t.notional<100.02*rules.stepSize+1e-9);assert.ok(Math.abs(t.initialMargin-t.notional/leverage)<1e-12);assert.ok(t.allocationPct>=.03&&t.allocationPct<=.04);assert.ok(Math.abs(t.plannedLoss/100-t.riskPct)<1e-12);const before=s.wallets[0].balance;replayTrades(s.wallets[0],t,[{a:1,p:"111",T:now+1}]);assert.ok(Math.abs((s.wallets[0].balance-before)-(t.qty*(t.exit-t.entry)-t.exitFee))<1e-9);}
});
test("allocation round-down below3% or exchange lot minimum cannot force an entry",()=>{
 assert.throws(()=>acceptDecision(newState(now),{...decision,allocationPct:.03},context,quote,{...rules,stepSize:.1,minQty:.1},now),/allocation/i);
 assert.throws(()=>acceptDecision(newState(now),{...decision,symbol:"BTCUSDT",allocationPct:.05,sl:76000,tp:80000},context,{...quote,symbol:"BTCUSDT",bid:77500,ask:77500.1},{...rules,stepSize:.001,minQty:.001},now),/Quantity/i);
});
