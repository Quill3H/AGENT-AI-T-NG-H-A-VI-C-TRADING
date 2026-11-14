import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OkxMarket} from './okx-market.mjs';

const from=600000,base=9007199254741000n;
const trade={venue:'OKX',symbol:'BTCUSDT',instId:'BTC-USDT-SWAP',openedAt:from,replayTime:from,sl:90,tp:110};
function denseFixture(){
 const rows=Array.from({length:18001},(_,i)=>({tradeId:String(base+BigInt(i)),ts:String(from+Math.ceil(i/3)*10),px:i===1?'90':'100'}));
 const market=new OkxMarket();let calls=0;
 market.get=async(endpoint,q)=>{
  assert.equal(endpoint,'/api/v5/market/history-trades');calls++;
  return rows.filter(r=>q.type==='2'?Number(r.ts)<Number(q.after):BigInt(r.tradeId)<BigInt(q.after)).slice(-100).reverse();
 };
 return {market,rows,calls:()=>calls};
}
test('dense native minute recovers a complete prefix instead of repeating page exhaustion',async()=>{
 const f=denseFixture(),result=await f.market.replay(trade,from+60000);
 assert.ok(result.through>from&&result.through<from+60000);assert.equal(result.complete,false);
 assert.deepEqual(result.events.map(e=>e.venueId),f.rows.filter(r=>Number(r.ts)>from&&Number(r.ts)<=result.through).map(r=>r.tradeId));
 assert.equal(result.events[0].p,'90');assert.ok(f.calls()<=128);
 const calls=f.calls();
 const next=await f.market.replay({...trade,replayTime:result.through,lastAggId:result.events.at(-1).a},from+60000);
 assert.deepEqual(next.events.map(e=>e.venueId),f.rows.filter(r=>Number(r.ts)>result.through&&Number(r.ts)<=next.through).map(r=>r.tradeId));
 assert.equal(next.events[0].a,result.events.at(-1).a+1);
 assert.ok(f.calls()-calls<=16,'adapt from the previous window instead of restarting at one minute');
});
test('replay window grows again after a dense burst instead of remaining at one millisecond',async()=>{
 const m=new OkxMarket();m.replayCache.set(trade.symbol,{from:from-1,through:from,rows:[]});
 m.get=async()=>[{tradeId:String(base),ts:String(from),px:'100'}];
 const r=await m.replay(trade,from+60000);
 assert.equal(r.through,from+2);assert.deepEqual(r.events,[]);
 const next=await m.replay({...trade,replayTime:r.through},from+60000);
 assert.equal(next.through,from+6);
});
test('even a single millisecond without full coverage fails closed within total page budget',async()=>{
 const m=new OkxMarket();let calls=0,id=base+20000n;
 m.get=async()=>{calls++;return Array.from({length:100},()=>({tradeId:String(id--),ts:String(from+1),px:'100'}));};
 await assert.rejects(m.replay(trade,from+60000),/bounded page coverage/);
 assert.equal(calls,128);assert.equal(m.replayCache.size,0);assert.equal(trade.replayTime,from);
});
