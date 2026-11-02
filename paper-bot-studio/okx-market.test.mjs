import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OkxMarket} from './okx-market.mjs';
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
