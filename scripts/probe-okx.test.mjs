import {test} from 'node:test';
import assert from 'node:assert/strict';
import {probeOkx} from './probe-okx.mjs';
test('fixed public OKX checks use no credentials and retain per-endpoint failures',async()=>{
 let calls=0;
 const result=await probeOkx({pause:async()=>{},fetcher:async(url,options)=>{
  calls++;assert.ok(url.startsWith('https://www.okx.com/api/v5/'));assert.equal(options.headers,undefined);
  return {status:200,ok:true,json:async()=>({code:url.includes('HYPE')?'51001':'0',msg:'',data:url.includes('HYPE')?[]:[{ts:'123',instId:'BTC-USDT-SWAP',state:'live'}]})};
 }});
 assert.equal(calls,12);assert.equal(result.checks.length,12);assert.ok(!result.ok);
 assert.equal(result.checks.find(c=>c.name==='instrument HYPE').code,'51001');
 assert.equal(result.authenticated,false);
});
