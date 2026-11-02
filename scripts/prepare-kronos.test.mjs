import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fetchKronosInputs} from './prepare-kronos.mjs';
import {sign} from './cloud-transport.mjs';
const key='fixture-only';
test('verify input signature before handing any candles to inference',async()=>{
 const body=JSON.stringify({version:1,frames:[],errors:{}}),time=Date.now();
 const fetcher=async(url,opts)=>{assert.equal(url,'https://paper-studio-connectivity.onrender.com/kronos/input');assert.ok(!opts.body.includes(key));return new Response(body,{headers:{'x-paper-time':String(time),'x-paper-signature':sign(key,'response',time,body)}});};
 assert.deepEqual((await fetchKronosInputs({key,frames:['15m'],fetcher})).frames,[]);
 await assert.rejects(fetchKronosInputs({key,frames:['15m'],fetcher:async()=>new Response(body,{headers:{'x-paper-time':String(time),'x-paper-signature':'0'.repeat(64)}})}),/signature/);
 await assert.rejects(fetchKronosInputs({key,frames:['15m'],endpoint:'https://example.com'}),/endpoint/);
});
