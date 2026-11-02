import test from 'node:test';
import assert from 'node:assert/strict';
import {packContext,nextFrame} from './analysis-pack.mjs';
const cycleAt=1800000000000,interval=900000;
function context(){return {id:'fixture',frame:'15m',cycleAt,capturedAt:cycleAt+1000,expiresAt:cycleAt+240000,snapshotPath:'fixture.json',policy:{riskScope:'PER_TRADE_CUMULATIVE'},wallet:{balance:100,trades:[],reviews:[]},lowerFrame:null,market:{frame:'15m',closedThrough:cycleAt-1,symbols:[{symbol:'SOLUSDT',quote:{bid:99,ask:100},rules:{stepSize:.01},premium:{lastFundingRate:'.001'},candles:Array.from({length:60},(_,i)=>({openTime:cycleAt-(60-i)*interval,closeTime:cycleAt-(59-i)*interval-1,o:100,h:101,l:99,c:100,v:10}))}]}};}
test('compact candles retain exact latest40 values, timing and market constraints without mutating source',()=>{
 const c=context(),before=JSON.stringify(c),p=packContext(c,before);
 assert.equal(JSON.stringify(c),before);assert.equal(p.market.symbols[0].rows.length,40);assert.deepEqual(p.market.symbols[0].rows[0],[100,101,99,100,10]);
 assert.equal(p.market.symbols[0].firstOpenTime,cycleAt-40*interval);assert.equal(p.market.intervalMs,interval);
 assert.deepEqual(p.market.symbols[0].quote,c.market.symbols[0].quote);assert.deepEqual(p.market.symbols[0].rules,c.market.symbols[0].rules);
 assert.equal(p.source.sha256.length,64);assert.equal(p.source.bytes,Buffer.byteLength(before));
 assert.deepEqual(p.market.symbols[0].indicators,{sma20:100,sma50:100,atr14:2});
});
test('pack excludes historical ledger bulk, preserves open levels and flags reviews needing full evidence',()=>{
 const c=context();c.wallet.trades=[{id:'a',status:'OPEN',symbol:'SOLUSDT',side:'LONG',qty:1,entry:100,tp:110,sl:95,plannedLoss:4,notional:100,reason:'long explanation'}, {id:'b',status:'SL',reason:'closed evidence'}];
 c.wallet.trades.push({id:'uncertain',status:'UNVERIFIED',symbol:'SOLUSDT',tp:110,sl:95});
 const p=packContext(c,JSON.stringify(c));assert.equal(p.wallet.open[0].sl,95);assert.equal(p.wallet.open[0].plannedLoss,4);assert.equal(p.wallet.open[0].reason,undefined);assert.deepEqual(p.wallet.unreviewedTradeIds,['b']);assert.equal(p.wallet.trades,undefined);
 assert.equal(p.wallet.open[1].status,'UNVERIFIED');assert.equal(p.wallet.open[1].sl,95);
});
test('invalid or future/gapped candles fail instead of silently compressing bad data',()=>{
 for(const mutate of [c=>c.frame='5m',c=>c.market.symbols[0].candles.pop(),c=>c.market.symbols[0].candles[40].o=NaN,c=>c.market.symbols[0].candles[40].openTime++,c=>c.market.symbols=[]]){const c=context();mutate(c);assert.throws(()=>packContext(c,JSON.stringify(c)));}
});
test('next-frame selection respects time, priority, decided cycles and technical blocks, not cumulative risk',()=>{
 const now=Date.UTC(2026,10,1,0,0,30),wallets=['15m','1h','4h'].map(frame=>({frame,balance:100,enabled:true,trades:[{status:'OPEN'}],decisions:[]}));
 const s={serverTime:now,worker:{healthy:true},wallets};assert.equal(nextFrame(s).frame,'15m');
 wallets[0].decisions.push({cycleAt:now-30000});assert.equal(nextFrame(s).frame,'1h');wallets[1].blocked='replay offline';assert.equal(nextFrame(s).frame,'4h');
 s.worker.healthy=false;assert.equal(nextFrame(s).frame,null);s.worker.healthy=true;s.serverTime+=11*60000;assert.equal(nextFrame(s).frame,null);
 s.serverTime=Date.UTC(2026,10,1,0,14,50);const n=nextFrame(s);assert.equal(n.frame,null);assert.equal(n.waitMs,10000);
});
