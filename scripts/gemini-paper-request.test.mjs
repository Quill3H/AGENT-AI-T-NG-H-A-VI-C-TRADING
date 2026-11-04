import {test} from 'node:test';
import assert from 'node:assert/strict';
import {geminiRequest} from './gemini-request.mjs';
const ok=()=>new Response('{"ok":true}');
const unavailable=(headers={})=>new Response(JSON.stringify({error:{status:'UNAVAILABLE',message:'Overloaded fixture-secret'}}),{status:503,headers});
function fixture(responses,budget=90000){let now=0,calls=0;const waits=[];return {waits,get calls(){return calls;},options:{key:'fixture-secret',timeoutMs:budget,clock:()=>now,random:()=>0,pause:async ms=>{waits.push(ms);now+=ms;},fetcher:async()=>{calls++;return responses.shift()??unavailable();}}};}
test('503 retries twice with backoff, then returns the single successful response',async()=>{const f=fixture([unavailable(),unavailable(),ok()]);assert.equal((await geminiRequest('https://fixture',{},f.options)).status,200);assert.equal(f.calls,3);assert.deepEqual(f.waits,[1000,2000]);});
test('persistent503 stops at three total attempts and redacts provider error',async()=>{const f=fixture([]);await assert.rejects(geminiRequest('https://fixture',{},f.options),e=>/503.*UNAVAILABLE/.test(e.message)&&!e.message.includes('fixture-secret'));assert.equal(f.calls,3);});
test('Retry-After cannot extend the original budget or be silently shortened',async()=>{const f=fixture([unavailable({'Retry-After':'10'})],5000);await assert.rejects(geminiRequest('https://fixture',{},f.options),/503/);assert.equal(f.calls,1);assert.deepEqual(f.waits,[]);});
test('non503 errors and ambiguous network failures are never retried',async()=>{for(const status of [400,401,403,429,500,504]){const f=fixture([new Response('{}',{status})]);await assert.rejects(geminiRequest('https://fixture',{},f.options),new RegExp(String(status)));assert.equal(f.calls,1);}let calls=0;await assert.rejects(geminiRequest('https://fixture',{},{fetcher:async()=>{calls++;throw Error('network');}}),/network/);assert.equal(calls,1);});
test('budget consumed during an attempt prevents another request',async()=>{let now=0,calls=0;await assert.rejects(geminiRequest('https://fixture',{},{timeoutMs:1000,clock:()=>now,fetcher:async()=>{calls++;now=2000;return unavailable();}}),/503/);assert.equal(calls,1);});
