import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OkxMarket} from './okx-market.mjs';

test('shared deadline stops queued replay requests after pacing',async()=>{
 let now=1000,calls=0;
 const m=new OkxMarket({clock:()=>now,deadline:1001,pause:async()=>{now=1002;},fetcher:async()=>{calls++;throw Error('must not fetch');}});
 await assert.rejects(m.get('/fixture'),/deadline/);await assert.rejects(m.get('/fixture'),/deadline/);assert.equal(calls,0);
});
test('shared deadline aborts an in-flight replay request',async()=>{
 const keepAlive=setTimeout(()=>{},1000);
 try{
  const m=new OkxMarket({deadline:Date.now()+30,pause:async()=>{},fetcher:async(url,{signal})=>new Promise((resolve,reject)=>{signal.addEventListener('abort',()=>reject(signal.reason),{once:true});})});
  await assert.rejects(m.get('/fixture'),/timeout/i);
 }finally{clearTimeout(keepAlive);}
});
test('OKX contract sizes convert to base quantities without Binance filters',async()=>{
 const m=new OkxMarket();
 m.get=async(endpoint)=>endpoint.includes('instruments')?[{instId:'BTC-USDT-SWAP',state:'live',ctType:'linear',settleCcy:'USDT',ctValCcy:'BTC',ctVal:'0.01',ctMult:'1',lotSz:'0.01',minSz:'0.01',maxMktSz:'1000',tickSz:'0.1'}]:[{bidPx:'100000',askPx:'100001',bidSz:'2',askSz:'3',ts:String(Date.now())}];
 const r=await m.rules('BTCUSDT'),q=await m.quote('BTCUSDT');
 assert.equal(r.stepSize,.0001);assert.equal(r.minQty,.0001);assert.equal(r.maxQty,10);
 assert.equal(q.bidQty,.02);assert.equal(q.askQty,.03);assert.equal(q.venue,'OKX');
});
test('OKX refuses replay of an unknown or Binance position',async()=>{
 const m=new OkxMarket();m.get=async()=>assert.fail('No request allowed');
 await assert.rejects(m.replay({symbol:'BTCUSDT',openedAt:Date.now()},Date.now()),/venue/);
});
