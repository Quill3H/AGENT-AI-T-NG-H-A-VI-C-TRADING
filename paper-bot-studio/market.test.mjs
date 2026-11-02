import test from 'node:test';
import assert from 'node:assert/strict';
import {BinanceMarket} from './market.mjs';
test('aggregate replay paginates inclusive IDs without mixing time parameters or including future trades',async()=>{
 const market=new BinanceMarket(),now=Date.now(),trade={symbol:'SOLUSDT',openedAt:now-10000,lastAggId:null,replayTime:now-10000};let calls=0;
 market.get=async(endpoint,q)=>{
  assert.equal(endpoint,'/fapi/v1/aggTrades');calls++;
  if(calls===1){assert.equal(q.startTime,trade.openedAt+1);return Array.from({length:1000},(_,i)=>({a:i+1,T:trade.openedAt+i+1,p:'100'}));}
  assert.equal(q.fromId,1001);assert.equal(q.startTime,undefined);assert.equal(q.endTime,undefined);return [{a:1001,T:now-1,p:'101'},{a:1002,T:now+1,p:'102'}];
 };
 const result=await market.replay(trade,now);assert.equal(result.events.length,1001);assert.equal(result.events.at(-1).a,1001);assert.equal(result.complete,true);
});
test('replay beyond public history fails closed rather than silently using recent trades',async()=>{
 const market=new BinanceMarket(),now=Date.now();await assert.rejects(()=>market.replay({openedAt:now-49*3600000,replayTime:now-49*3600000},now),/REVIEW_REQUIRED/);
});
test('funding reconciliation shares symbol history to avoid per-closed-trade API requests',async()=>{
 const market=new BinanceMarket(),now=Date.now();let calls=0;
 market.get=async()=>{calls++;return [{fundingTime:now-1000,fundingRate:'.001',markPrice:'100'}];};
 const a=await market.funding({symbol:'SOLUSDT',openedAt:now-10000},now),b=await market.funding({symbol:'SOLUSDT',openedAt:now-5000},now-500);
 assert.equal(a.length,1);assert.equal(b.length,1);assert.equal(calls,1);
});
