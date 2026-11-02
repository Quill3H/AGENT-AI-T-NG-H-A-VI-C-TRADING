import {test} from 'node:test';
import assert from 'node:assert/strict';
import {makeKronosInput,validateForecast,MODEL,ARTIFACTS} from './kronos-advisory.mjs';
import {FRAMES} from '../paper-bot-studio/engine.mjs';
export const cutoff=Date.UTC(2026,10,1,12);
export function market(frame='15m'){
 const ms=FRAMES[frame];return {venue:'OKX',frame,closedThrough:cutoff-1,symbols:[{symbol:'SOLUSDT',candles:Array.from({length:40},(_,i)=>({openTime:cutoff-(40-i)*ms,closeTime:cutoff-(39-i)*ms-1,o:100,h:102,l:98,c:101,v:100,quoteVolume:10100}))}]};
}
export function forecast(input,now=cutoff+1000){return {...MODEL,artifacts:ARTIFACTS,version:1,frame:input.frame,venue:'OKX',cycleAt:input.cycleAt,generatedAt:now,symbols:input.symbols.map(s=>({symbol:s.symbol,inputSha256:s.inputSha256,forecast:Array.from({length:4},(_,i)=>({openTime:cutoff+i*FRAMES[input.frame],closeTime:cutoff+(i+1)*FRAMES[input.frame]-1,open:101,high:103,low:99,close:102,volume:100,amount:10200}))}))};}
for(const frame of Object.keys(FRAMES))test('bound forecast for '+frame,()=>{
 const m=market(frame),input=makeKronosInput(m,cutoff),f=forecast(input);
 assert.equal(input.symbols[0].inputJson.includes('10100'),true);
 assert.equal(validateForecast(f,m,cutoff,cutoff+2000).frame,frame);
 for(const mutate of [x=>x.cycleAt++,x=>x.modelRevision='bad',x=>x.symbols[0].inputSha256='0'.repeat(64),x=>x.symbols[0].forecast[0].close=NaN,x=>x.generatedAt=cutoff+3000,x=>x.symbols.push(x.symbols[0]),x=>x.symbols[0].forecast[0].openTime--]){
  const bad=structuredClone(f);mutate(bad);assert.throws(()=>validateForecast(bad,m,cutoff,cutoff+2000));
 }
 assert.throws(()=>validateForecast(f,m,cutoff,cutoff+241001),/stale|expired/i);
});
test('invalid OHLC, duplicate, future, gaps and provisional inputs fail closed',()=>{
 for(const mutate of [m=>m.symbols[0].candles[0].h=1,m=>m.symbols[0].candles[0].provisional=true,m=>m.symbols[0].candles[0].openTime++,m=>m.symbols[0].candles.at(-1).closeTime++,m=>m.symbols.push(m.symbols[0]),m=>m.symbols[0].candles[0].v=-1]){
  const m=market();mutate(m);assert.throws(()=>makeKronosInput(m,cutoff));
 }
});
