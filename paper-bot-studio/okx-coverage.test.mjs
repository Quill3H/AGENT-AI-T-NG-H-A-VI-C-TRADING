import {test} from 'node:test';
import assert from 'node:assert/strict';
import {OkxMarket} from './okx-market.mjs';
const from=601000,cutoff=841500;
const position={venue:'OKX',symbol:'BTCUSDT',instId:'BTC-USDT-SWAP',openedAt:from,replayTime:from,sl:90,tp:110};
const bars=()=>[600000,660000,720000,780000].map(t=>[String(t),'100','105','95','101','1','1','1','1']);
function fixture(rows=bars()){
 const m=new OkxMarket({allowCandleCoverage:true});let native=0;
 m.get=async endpoint=>{if(endpoint.includes('history-candles'))return rows;native++;return [{tradeId:'1',ts:String(from),px:'100'}];};
 return {m,native:()=>native};
}
test('closed no-touch candles skip old windows while retaining source evidence and current-minute replay',async()=>{
 const f=fixture(),r=await f.m.replay(position,cutoff);assert.equal(r.through,839999);assert.equal(r.complete,false);assert.deepEqual(r.events,[]);assert.equal(f.native(),0);assert.equal(r.proof.bars.length,4);assert.equal(r.proof.method,'CONFIRMED_NO_TOUCH');assert.equal(r.proof.from,from);
});
test('potential touch stops proof before that minute, including exact level touches',async()=>{
 for(const column of [2,3]){const rows=bars();rows[2][column]=column===2?'110':'90';const f=fixture(rows),r=await f.m.replay(position,cutoff);assert.equal(r.through,719999);assert.equal(r.proof.bars.length,2);}
 const rows=bars();rows[0][3]='90';const f=fixture(rows),r=await f.m.replay(position,cutoff);assert.equal(f.native(),1);assert.equal(r.proof,undefined);
});
test('short levels use the same no-touch range',async()=>{const f=fixture();assert.equal((await f.m.replay({...position,sl:110,tp:90},cutoff)).through,839999);});
test('managed positions and absent/gapped/unconfirmed coverage require native replay',async()=>{
 for(const rows of [[],bars().slice(1),bars().map((b,i)=>i===1?[...b.slice(0,8),'0']:b)]){const f=fixture(rows);await f.m.replay(position,cutoff);assert.equal(f.native(),1);}
 const f=fixture();await f.m.replay({...position,managementEvents:[{}]},cutoff);assert.equal(f.native(),1);
});
test('malformed confirmed prices cannot establish no-touch coverage',async()=>{const rows=bars();rows[0][2]='-1';await assert.rejects(fixture(rows).m.replay(position,cutoff),/Malformed/);});
test('no candle at or beyond cutoff may establish coverage',async()=>{
 const f=fixture([...bars(),['840000','100','105','95','101','1','1','1','1']]);const r=await f.m.replay(position,cutoff);assert.equal(r.through,839999);assert.ok(r.proof.bars.every(b=>Number(b[0])+60000<=cutoff));
});
test('native replay includes a touch exactly at the next minute open after proven safe bars',async()=>{
 const rows=bars();rows[2][2]='110';const f=fixture(rows),proof=await f.m.replay(position,cutoff);
 assert.equal(proof.through,719999);
 const original=f.m.get;f.m.get=async endpoint=>endpoint.includes('history-trades')?[{tradeId:'2',ts:'720000',px:'110'},{tradeId:'1',ts:'719999',px:'100'}]:original(endpoint);
 const r=await f.m.replay({...position,replayTime:proof.through},cutoff);assert.equal(r.events[0].T,720000);assert.equal(r.events[0].p,'110');
});
