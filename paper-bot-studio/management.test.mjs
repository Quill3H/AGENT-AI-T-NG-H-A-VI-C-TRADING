import test from 'node:test';
import assert from 'node:assert/strict';
import {newState,acceptDecision,manageTrade,replayTrades,walletMetrics} from './engine.mjs';
const now=Date.UTC(2026,10,1),rules={stepSize:.001,minQty:.001,maxQty:10000,minNotional:5,tickSize:.01};
function fixture(side='LONG'){
 const s=newState(now),c={id:'c',frame:'15m',cycleAt:now,capturedAt:now,expiresAt:now+240000};
 acceptDecision(s,{contextId:'c',frame:'15m',action:side,symbol:'SOLUSDT',allocationPct:.04,sl:side==='LONG'?95:105,tp:side==='LONG'?110:90,method:'Test',reason:'Source evidence',invalidation:'Invalidation'},c,{symbol:'SOLUSDT',bid:99.99,ask:100,time:now},rules,now);
 return {w:s.wallets[0],t:s.wallets[0].trades[0]};
}
const command={managementId:'change-1',action:'UPDATE_LEVELS',sl:101,tp:112,reason:'1. Support moved higher. 2. Momentum holds. 3. Protect the open gain.'};
test('trailing SL may cross entry; audit preserves original levels and duplicate request is idempotent',()=>{
 const {w,t}=fixture();const entry=t.entry,qty=t.qty;t.replayTime=now+1000;
 const q={symbol:'SOLUSDT',bid:103,ask:103.01,time:now+1000};
 manageTrade(w,t,command,q,rules,now+1001);assert.equal(t.sl,101);assert.equal(t.tp,112);assert.equal(t.managementEvents[0].before.sl,95);assert.equal(t.managementEvents[0].after.sl,101);assert.equal(t.currentPlannedLoss,0);
 assert.equal(t.entry,entry);assert.equal(t.qty,qty);manageTrade(w,t,command,q,rules,now+1001);assert.equal(t.managementEvents.length,1);
});
test('replay uses levels effective at event time, never a newly moved stop retroactively',()=>{
 const {w,t}=fixture();t.replayTime=now+1000;manageTrade(w,t,command,{symbol:'SOLUSDT',bid:103,ask:103.01,time:now+1000},rules,now+1001);
 replayTrades(w,t,[{a:1,p:'100.5',T:now+999},{a:2,p:'102',T:now+1001}]);assert.equal(t.status,'OPEN');
 replayTrades(w,t,[{a:3,p:'100.5',T:now+1002}]);assert.equal(t.status,'SL');assert.equal(t.closedAt,now+1002);
});
test('early long/short exits use executable quote with fees and settle once',()=>{
 for(const side of ['LONG','SHORT']){
  const {w,t}=fixture(side);const q={symbol:'SOLUSDT',bid:101,ask:101.01,time:now+1000};t.replayTime=q.time;
  const body={managementId:'exit-1',action:'CLOSE',reason:'Momentum reversed.'};manageTrade(w,t,body,q,rules,now+1001);
  assert.equal(t.status,'EARLY_EXIT');assert.equal(t.exit,(side==='LONG'?q.bid:q.ask)*(side==='LONG'?.9998:1.0002));assert.ok(Math.abs(w.balance-(100+t.pnl))<1e-9);
  const b=w.balance;manageTrade(w,t,body,q,rules,now+1002);assert.equal(w.balance,b);assert.equal(walletMetrics(w,{}).closedCount,1);
 }
});
test('stale quote, stale replay, invalid ticks/direction or invalid action cannot edit trade',()=>{
 for(const [body,q] of [[{...command,sl:104},{symbol:'SOLUSDT',bid:103,ask:103.01,time:now+1000}],[{...command,sl:101.001},{symbol:'SOLUSDT',bid:103,ask:103.01,time:now+1000}],[{...command,action:'OTHER'},{symbol:'SOLUSDT',bid:103,ask:103.01,time:now+1000}],[command,{symbol:'SOLUSDT',bid:103,ask:103.01,time:now-1}]]){
  const {w,t}=fixture();t.replayTime=now+1000;const before=JSON.stringify(t);assert.throws(()=>manageTrade(w,t,body,q,rules,now+1001));assert.equal(JSON.stringify(t),before);
 }
});
