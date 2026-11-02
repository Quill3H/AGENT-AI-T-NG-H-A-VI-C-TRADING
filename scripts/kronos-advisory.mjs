import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {FRAMES,SYMBOLS} from '../paper-bot-studio/engine.mjs';
export const MODEL=Object.freeze({model:'NeoQuasar/Kronos-small',modelRevision:'901c26c1332695a2a8f243eb2f37243a37bea320',tokenizerRevision:'0e0117387f39004a9016484a186a908917e22426',sourceRevision:'67b630e67f6a18c9e9be918d9b4337c960db1e9a',seed:123,sampleCount:3});
export const ARTIFACTS=Object.freeze(JSON.parse(readFileSync(new URL('./kronos-model-manifest.json',import.meta.url),'utf8')));
const check=(ok,message)=>{if(!ok)throw Error('Kronos: '+message);};
const finite=v=>typeof v==='number'&&Number.isFinite(v);
export function makeKronosInput(market,cycleAt){
 const {frame,venue,symbols}=market??{},ms=FRAMES[frame];
 check(ms&&venue==='OKX'&&Number.isSafeInteger(cycleAt)&&cycleAt%ms===0&&market.closedThrough===cycleAt-1,'invalid candle boundary/venue');
 check(Array.isArray(symbols)&&symbols.length>0&&symbols.length<=SYMBOLS.length&&new Set(symbols.map(s=>s.symbol)).size===symbols.length,'invalid symbol set');
 return {frame,venue,cycleAt,symbols:symbols.map(s=>{
  check(SYMBOLS.includes(s.symbol)&&Array.isArray(s.candles)&&s.candles.length>=40,'missing confirmed candles');
  const bars=s.candles.slice(-40),amount=bars.every(b=>finite(b.quoteVolume)&&b.quoteVolume>=0);
  bars.forEach((b,i)=>check(b.provisional!==true&&b.openTime===cycleAt-(40-i)*ms&&b.closeTime===b.openTime+ms-1&&['o','h','l','c','v'].every(k=>finite(b[k]))&&Math.min(b.o,b.h,b.l,b.c)>0&&b.v>=0&&b.h>=Math.max(b.o,b.c,b.l)&&b.l<=Math.min(b.o,b.c,b.h),'malformed, future or gapped candle'));
  const inputJson=JSON.stringify({frame,venue,symbol:s.symbol,cycleAt,intervalMs:ms,firstOpenTime:bars[0].openTime,columns:['open','high','low','close','volume',...(amount?['amount']:[])],rows:bars.map(b=>[b.o,b.h,b.l,b.c,b.v,...(amount?[b.quoteVolume]:[])])});
  return {symbol:s.symbol,inputJson,inputSha256:createHash('sha256').update(inputJson).digest('hex')};
 })};
}
export function validateForecast(f,market,cycleAt,now=Date.now()){
 const expected=makeKronosInput(market,cycleAt),ms=FRAMES[expected.frame];
 check(f?.version===1&&f.frame===expected.frame&&f.venue===expected.venue&&f.cycleAt===cycleAt,'forecast context mismatch');
 check(Object.entries(MODEL).every(([k,v])=>f[k]===v),'model identity mismatch');
 check(Object.entries(ARTIFACTS).every(([k,v])=>f.artifacts?.[k]===v),'model artifact hash mismatch');
 check(Number.isSafeInteger(f.generatedAt)&&f.generatedAt>=cycleAt&&f.generatedAt<=now&&now-f.generatedAt<=240000&&now-cycleAt<=600000,'stale/expired forecast');
 check(Array.isArray(f.symbols)&&f.symbols.length===expected.symbols.length&&new Set(f.symbols.map(s=>s.symbol)).size===f.symbols.length,'forecast symbols mismatch');
 for(const s of expected.symbols){
  const p=f.symbols.find(p=>p.symbol===s.symbol);
  check(p?.inputSha256===s.inputSha256&&Array.isArray(p.forecast)&&p.forecast.length===4,'input hash/horizon mismatch');
  p.forecast.forEach((b,i)=>check(b.openTime===cycleAt+i*ms&&b.closeTime===cycleAt+(i+1)*ms-1&&['open','high','low','close','volume','amount'].every(k=>finite(b[k]))&&Math.min(b.open,b.high,b.low,b.close)>0&&Math.min(b.volume,b.amount)>=0&&b.high>=Math.max(b.open,b.close,b.low)&&b.low<=Math.min(b.open,b.close,b.high),'invalid forecast values/target time'));
 }
 return {...f,interpretation:'Model-generated scenario; no calibrated confidence, no guaranteed direction. Gemini may disagree.'};
}
