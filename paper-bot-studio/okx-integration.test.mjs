import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {OkxMarket} from './okx-market.mjs';
import {newState,acceptDecision,replayTrades,applyFunding,FRAMES} from './engine.mjs';
import {createRuntime} from './server.mjs';
const now=Date.UTC(2026,10,2,12),id='SOL-USDT-SWAP';
function market(options={}){return new OkxMarket({clock:()=>now,pause:async()=>{},allowEstimatedFunding:true,...options});}
const quote={symbol:'SOLUSDT',venue:'OKX',instId:id,bid:99.99,ask:100,bidQty:100,askQty:100,time:now};
const rules={venue:'OKX',instId:id,quantityUnit:'BASE_COIN',contractSize:.1,stepSize:.001,minQty:.001,maxQty:100,minNotional:0,notionalRule:'CONTRACT_LOT_ONLY',tickSize:.01};
function entered(){const state=newState(now,'OKX'),context={id:'fixture',frame:'15m',cycleAt:now,capturedAt:now,expiresAt:now+240000};acceptDecision(state,{contextId:context.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:90,tp:120,method:'Fixture',reason:'Observed support',invalidation:'Support fails'},context,quote,rules,now);return {state,wallet:state.wallets[0],trade:state.wallets[0].trades[0]};}
const foreign={venue:'BINANCE',instId:'SOLUSDT',symbol:'SOLUSDT',openedAt:now,replayTime:now,fundingEvents:[]};
const rawTrade=(tradeId,ts,px='100')=>({tradeId,ts:String(ts),px});
test('null, boolean and whitespace realized rates never become a permanent zero funding event',async()=>{
 for(const realizedRate of [null,false,' ',undefined]){
  const m=market(),{trade}=entered();m.get=async endpoint=>endpoint.includes('funding-rate-history')?[{fundingTime:String(now+1000),realizedRate}]:assert.fail('Invalid rate must not request mark price');
  await assert.rejects(m.funding(trade,now+2000),/realized/);assert.equal(trade.fundingEvents.length,0);
 }
});
function captureFixture(frame,change=x=>x){
 const m=market(),ms=FRAMES[frame];
 const bars=Array.from({length:80},(_,i)=>[String(now-(80-i)*ms),'100','102','98','101','10','1000','101000','1']).reverse();
 bars.unshift([String(now),'101','103','100','102','10','1000','102000','0']);
 m.get=async(endpoint)=>endpoint.endsWith('/time')?[{ts:String(now)}]:endpoint.endsWith('/candles')?change(structuredClone(bars)):[{fundingRate:'.001'}];
 m.quote=async symbol=>({...quote,symbol,instId:m.instId(symbol)});m.rules=async symbol=>({...rules,instId:m.instId(symbol)});return m;
}
test('all frames capture only confirmed UTC candles in ascending contiguous order',async()=>{
 for(const frame of Object.keys(FRAMES)){
  const data=await captureFixture(frame).capture(frame,now);
  assert.equal(data.venue,'OKX');assert.equal(data.symbols.length,4);
  for(const s of data.symbols){assert.equal(s.candles.length,80);assert.equal(s.candles.at(-1).closeTime,now-1);assert.equal(s.candles[0].openTime,now-80*FRAMES[frame]);assert.equal(s.candles[0].v,1000);assert.equal(s.candles[0].quoteVolume,101000);assert.equal(s.premium.fundingRateIsForecast,true);}
 }
});
test('missing confirmation on latest closed bar and internal gaps fail coverage',async()=>{
 await assert.rejects(captureFixture('15m',bars=>{bars[1][8]='0';return bars;}).capture('15m',now),/closed candle coverage/);
 await assert.rejects(captureFixture('15m',bars=>{bars.splice(10,1);return bars;}).capture('15m',now),/gapped/);
 await assert.rejects(captureFixture('15m',bars=>{bars[10][0]=String(Number(bars[10][0])+1);return bars;}).capture('15m',now),/Malformed/);
});
test('invalid OHLC and an absent clock fail before model input',async()=>{
 await assert.rejects(captureFixture('15m',bars=>{bars[3][2]='-1';return bars;}).capture('15m',now),/Malformed/);
 const m=captureFixture('15m'),get=m.get;m.get=(endpoint,p)=>endpoint.endsWith('/time')?[]:get(endpoint,p);
 await assert.rejects(m.capture('15m',now),/Clock/);
});
test('native string IDs above 2^53 may be noncontiguous and paginate backwards without precision loss',async()=>{
 const m=market(),{wallet,trade}=entered();let calls=0;
 m.get=async(endpoint,q)=>{
  assert.equal(endpoint,'/api/v5/market/history-trades');calls++;
  if(calls===1){assert.equal(q.type,'2');assert.equal(q.after,String(now+1001));return [rawTrade('9007199254741999',now+900),rawTrade('9007199254741101',now+100)];}
  assert.equal(q.type,'1');assert.equal(q.after,'9007199254741101');return [rawTrade('9007199254741001',now)];
 };
 const r=await m.replay(trade,now+1000);assert.equal(calls,2);assert.equal(r.complete,true);
 assert.deepEqual(r.events.map(e=>e.venueId),['9007199254741101','9007199254741999']);assert.deepEqual(r.events.map(e=>e.a),[1,2]);
 replayTrades(wallet,trade,r.events,now+1000);assert.equal(trade.lastVenueTradeId,'9007199254741999');assert.equal(trade.lastAggId,2);
});
test('numeric native IDs are rejected instead of accepting already rounded values',async()=>{
 const m=market(),{trade}=entered();m.get=async()=>[rawTrade(9007199254740993,now)];
 await assert.rejects(m.replay(trade,now+1000),/Malformed/);
});
test('stalled native pagination and missing backward boundary fail closed',async()=>{
 const {trade}=entered();let calls=0;const m=market();
 m.get=async()=>{calls++;return [rawTrade('9007199254741001',now+500)];};
 await assert.rejects(m.replay(trade,now+1000),/stalled/);assert.equal(calls,2);
 const empty=market();empty.get=async()=>[];await assert.rejects(empty.replay(trade,now+1000),/cannot prove coverage/);
});
test('decreasing timestamps in ascending native IDs are rejected',async()=>{
 const m=market(),{trade}=entered();m.get=async()=>[rawTrade('9007199254741001',now),rawTrade('9007199254741101',now+900),rawTrade('9007199254741999',now+100)];
 await assert.rejects(m.replay(trade,now+1000),/Noncausal/);
});
test('funding uses realizedRate and pre-event confirmed mark with preserved provenance and idempotency',async()=>{
 const m=market(),{wallet,trade}=entered(),settlement=now+3600000;let markCalls=0;
 m.get=async(endpoint,q)=>{
  if(endpoint.includes('funding-rate-history'))return [{fundingTime:String(settlement),fundingRate:'.9',realizedRate:'.001'}];
  assert.equal(endpoint,'/api/v5/market/history-mark-price-candles');assert.equal(q.after,String(settlement));markCalls++;
  return [[String(settlement-60000),'100','102','98','101','1']];
 };
 const events=await m.funding(trade,settlement);assert.equal(events[0].fundingRate,'.001');assert.equal(events[0].markPrice,'101');
 const before=wallet.balance;applyFunding(wallet,trade,events,settlement);applyFunding(wallet,trade,events,settlement);
 assert.ok(Math.abs(wallet.balance-(before-trade.qty*101*.001))<1e-12);assert.equal(trade.fundingEvents.length,1);
 const stored=trade.fundingEvents[0];assert.equal(stored.estimated,true);assert.equal(stored.venue,'OKX');assert.equal(stored.priceMethod,'MARK_1M_PRE_EVENT_PROXY');assert.deepEqual(stored.priceWindow,{openTime:settlement-60000,closeTime:settlement-1});assert.match(stored.source,/funding-rate-history/);assert.match(stored.priceSource,/history-mark-price-candles/);
 assert.deepEqual(await m.funding(trade,settlement),[]);assert.equal(markCalls,1);
});
test('missing realized rate and missing/unconfirmed pre-event mark cannot book funding',async()=>{
 for(const realizedRate of ['',undefined,'not-a-number',null,false,' ']){
  const m=market(),{trade}=entered();m.get=async()=>[{fundingTime:String(now+3600000),realizedRate}];await assert.rejects(m.funding(trade,now+3600000),/realized/);
 }
 for(const bar of [[],[[String(now+3600000),'100','102','98','101','1']],[[String(now+3540000),'100','102','98','101','0']]]){
  const m=market(),{trade}=entered();m.get=async endpoint=>endpoint.includes('funding-rate-history')?[{fundingTime:String(now+3600000),realizedRate:'.001'}]:bar;
  await assert.rejects(m.funding(trade,now+3600000),/pre-event/);
 }
 const unapproved=market({allowEstimatedFunding:false}),{trade}=entered();unapproved.get=async()=>[{fundingTime:String(now+3600000),realizedRate:'.001'}];await assert.rejects(unapproved.funding(trade,now+3600000),/not approved/);
});

test('malformed wire timestamps cannot prove replay coverage or omit funding',async()=>{
 for(const time of [null,undefined,false,'',' ',0,'0','-1','1.5','9007199254740993']){
  const {trade}=entered(),replay=market(),funding=market();
  replay.get=async()=>[{tradeId:'9007199254740993',ts:time,px:'100'}];
  funding.get=async()=>[{fundingTime:time,realizedRate:'.001'}];
  await assert.rejects(replay.replay(trade,now+1000),/Malformed/);
  await assert.rejects(funding.funding(trade,now+3600000),/timestamp/);
 }
});
test('contract conversion applies ctVal*ctMult to minimum, step, max and quote depth',async()=>{
 const m=market();m.get=async endpoint=>endpoint.includes('instruments')?[{instId:id,state:'live',ctType:'linear',settleCcy:'USDT',ctValCcy:'SOL',ctVal:'0.1',ctMult:'2',lotSz:'0.01',minSz:'0.1',maxMktSz:'100',tickSz:'.01'}]:[{bidPx:'100',askPx:'100.01',bidSz:'3',askSz:'4',ts:String(now)}];
 const r=await m.rules('SOLUSDT'),q=await m.quote('SOLUSDT');assert.equal(r.contractSize,.2);assert.equal(r.stepSize,.002);assert.ok(Math.abs(r.minQty-.02)<1e-12);assert.equal(r.maxQty,20);assert.equal(r.minNotional,0);assert.ok(Math.abs(q.bidQty-.6)<1e-12);assert.equal(q.askQty,.8);
 const {trade}=entered();assert.ok(Math.abs(trade.contracts*trade.contractSize-trade.qty)<1e-12);assert.equal(trade.venue,'OKX');assert.equal(trade.instId,id);
});
test('adapter refuses foreign venues before any request and engine rejects foreign quotes',async()=>{
 const m=market();m.get=async()=>assert.fail('No foreign-market request');
 await assert.rejects(m.replay(foreign,now+1000),/venue mismatch/);await assert.rejects(m.funding(foreign,now+1000),/venue mismatch/);
 const {state}=entered(),c={id:'new',frame:'1h',cycleAt:now,capturedAt:now,expiresAt:now+1000};
 assert.throws(()=>acceptDecision(state,{contextId:c.id,frame:'1h',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:90,tp:120,method:'Fixture',reason:'Support',invalidation:'Fails'},c,{...quote,venue:'BINANCE'},rules,now),/venue mismatch/);
});
test('runtime advances proven empty partial replay windows rather than repeatedly querying the first minute',async t=>{
 const root=path.join(path.dirname(fileURLToPath(import.meta.url)),'.test-data');await fs.mkdir(root,{recursive:true});const directory=await fs.mkdtemp(path.join(root,'okx-empty-'));
 const {state}=entered();await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(state));
 const cutoff=now+120000,m=market({clock:()=>cutoff}),requests=[];
 m.quote=async symbol=>({...quote,symbol,instId:m.instId(symbol),time:cutoff});m.funding=async()=>[];
 m.get=async(endpoint,q)=>{assert.equal(endpoint,'/api/v5/market/history-trades');requests.push(q);return [rawTrade('9007199254741001',Number(q.after)-60001)];};
 const rt=await createRuntime({directory,market:m,clock:()=>cutoff});t.after(async()=>{await rt.close();if(path.dirname(directory)!==root)throw Error('Unexpected cleanup');await fs.rm(directory,{recursive:true,force:true});});
 assert.equal((await rt.tick()).ok,false);let stored=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));assert.equal(stored.wallets[0].trades[0].replayTime,now+60000);assert.equal(stored.wallets[0].trades[0].replayBehind,true);
 assert.equal((await rt.tick()).ok,true);stored=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));assert.equal(stored.wallets[0].trades[0].replayTime,cutoff);assert.equal(stored.wallets[0].trades[0].replayBehind,false);assert.equal(requests[1].after,String(cutoff+1));assert.equal(stored.wallets[0].trades[0].lastAggId,null);
});
