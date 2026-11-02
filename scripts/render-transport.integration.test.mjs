import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import http from 'node:http';
import {createCloudServer} from './render-service.mjs';
import {invokeCloud} from './render-cycle.mjs';
import {sign,verify,safeFile} from './cloud-transport.mjs';
import {newState} from '../paper-bot-studio/engine.mjs';

const key='fixture-only-not-a-real-key',revision='a'.repeat(40);
async function setup(t,cycle){
 const root=path.join(path.dirname(fileURLToPath(import.meta.url)),'.test-data');await fs.mkdir(root,{recursive:true});
 const directory=await fs.mkdtemp(path.join(root,'transport-'));
 const state=newState();await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(state));
 const server=createCloudServer({key,cycle});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 t.after(async()=>{server.closeAllConnections();await new Promise(r=>server.close(r));if(path.dirname(directory)!==root)throw Error('Unexpected cleanup path');await fs.rm(directory,{recursive:true,force:true});});
 return {directory,state,endpoint:`http://127.0.0.1:${server.address().port}`,read:async()=>JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'))};
}
const options=f=>({...f,key,baseRevision:revision,runId:'fixture-run',testEndpoint:true});
function requestBody(state,extra={}){return JSON.stringify({state,intents:{},runId:'fixture-run',baseRevision:revision,model:'gemini-3-flash-preview',...extra});}
async function post(endpoint,body,signature){const time=Date.now();return fetch(endpoint+'/run',{method:'POST',headers:{'Content-Type':'application/json','x-paper-time':String(time),'x-paper-signature':signature??sign(key,'request',time,body)},body});}
function response(body,{signature=true}={}){const raw=JSON.stringify(body),time=Date.now();return new Response(raw,{status:200,headers:{'x-paper-time':String(time),'x-paper-signature':signature?sign(key,'response',time,raw):'0'.repeat(64)}});}
function mockResponse(f,body){return async url=>url.endsWith('/health')?new Response('{}',{status:200}):response(body);}

test('invalid request signature never executes a cloud cycle',async t=>{
 let calls=0;const f=await setup(t,async()=>{calls++;});
 const r=await post(f.endpoint,requestBody(f.state),'0'.repeat(64));assert.equal(r.status,401);assert.equal(calls,0);
});
test('signed cloud result installs state and evidence but excludes runtime credentials',async t=>{
 const f=await setup(t,async({directory})=>{
  const state=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));state.wallets[0].balance=99;
  await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(state));
  await fs.writeFile(path.join(directory,'auth-token'),'private-worker-token');await fs.writeFile(path.join(directory,'worker.lock'),'123');
  await fs.mkdir(path.join(directory,'contexts'));await fs.writeFile(path.join(directory,'contexts','sample.json'),'{"fixture":true}');
 });
 let signedBody;
 const result=await invokeCloud({...options(f),fetcher:async(url,opts)=>{const r=await fetch(url,opts);if(url.endsWith('/run'))signedBody=await r.clone().text();return r;}});
 assert.equal(result.ok,true);assert.equal((await f.read()).wallets[0].balance,99);
 assert.equal(JSON.parse(await fs.readFile(path.join(f.directory,'contexts','sample.json'),'utf8')).fixture,true);
 assert.ok(!signedBody.includes(key));assert.ok(!signedBody.includes('private-worker-token'));assert.ok(!signedBody.includes('worker.lock'));
 await assert.rejects(fs.access(path.join(f.directory,'auth-token')),/ENOENT/);
});
test('partial cycle error returns signed partial ledger and client persists it',async t=>{
 const f=await setup(t,async({directory})=>{
  const state=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));state.wallets[0].balance=98;
  await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(state));throw Error('Fixture partial failure '+key);
 });
 const result=await invokeCloud(options(f));assert.equal(result.ok,false);assert.match(result.error,/Fixture partial failure/);assert.ok(!result.error.includes(key));assert.equal((await f.read()).wallets[0].balance,98);
});
test('same signed run identity executes once and a different payload conflicts',async t=>{
 let calls=0;const f=await setup(t,async()=>{calls++;});const body=requestBody(f.state);
 const first=await post(f.endpoint,body);assert.equal(first.status,200);const raw=await first.text();
 assert.ok(verify(key,'response',Number(first.headers.get('x-paper-time')),raw,first.headers.get('x-paper-signature')));
 const second=await post(f.endpoint,body);assert.equal(second.status,200);assert.equal(await second.text(),raw);assert.equal(calls,1);
 const changed=structuredClone(f.state);changed.wallets[0].balance=99;
 const conflict=await post(f.endpoint,requestBody(changed));assert.equal(conflict.status,409);assert.equal(calls,1);
});
test('tampered signed response cannot write local files',async t=>{
 const f=await setup(t,async()=>{}),state=structuredClone(f.state);state.wallets[0].balance=1;
 const body={runId:'fixture-run',baseRevision:revision,ok:true,files:{'state.json':JSON.stringify(state)}};
 await assert.rejects(invokeCloud({...options(f),fetcher:async url=>url.endsWith('/health')?new Response('{}'):response(body,{signature:false})}),/signature/);
 assert.deepEqual(await f.read(),f.state);assert.deepEqual((await fs.readdir(f.directory)).sort(),['state.json']);
});
test('authenticated mismatched base revision cannot write local files',async t=>{
 const f=await setup(t,async()=>{}),state=structuredClone(f.state);state.wallets[0].balance=1;
 const body={runId:'fixture-run',baseRevision:'b'.repeat(40),ok:true,files:{'state.json':JSON.stringify(state)}};
 await assert.rejects(invokeCloud({...options(f),fetcher:mockResponse(f,body)}),/identity mismatch/);
 assert.deepEqual(await f.read(),f.state);assert.deepEqual(await fs.readdir(f.directory),['state.json']);
});
test('unsafe response file refuses entire batch before any state install',async t=>{
 const f=await setup(t,async()=>{}),state=structuredClone(f.state);state.wallets[0].balance=1;
 const body={runId:'fixture-run',baseRevision:revision,ok:true,files:{'state.json':JSON.stringify(state),'../escape.json':'{}'}};
 await assert.rejects(invokeCloud({...options(f),fetcher:mockResponse(f,body)}),/Unsafe response file/);
 assert.deepEqual(await f.read(),f.state);assert.deepEqual(await fs.readdir(f.directory),['state.json']);
 assert.equal(safeFile('../escape.json'),false);assert.equal(safeFile('decisions/../../auth-token'),false);
});
test('server refuses unsafe incoming intent without executing cycle',async t=>{
 let calls=0;const f=await setup(t,async()=>{calls++;});
 const r=await post(f.endpoint,requestBody(f.state,{intents:{'../auth-token':'{}'}}));assert.equal(r.status,422);assert.equal(calls,0);
});
test('ambiguous transport failure has no automatic retry or local writes',async t=>{
 const f=await setup(t,async()=>{});let attempts=0;
 await assert.rejects(invokeCloud({...options(f),fetcher:async url=>{
  if(url.endsWith('/health'))return new Response('{}');attempts++;throw Error('Fixture connection dropped after send');
 }}),/connection dropped/);
 assert.equal(attempts,1);assert.deepEqual(await f.read(),f.state);assert.deepEqual(await fs.readdir(f.directory),['state.json']);
});
test('signed Vietnamese request survives a chunk split inside a UTF-8 character',async t=>{
 let calls=0;const f=await setup(t,async()=>{calls++;});
 const state=structuredClone(f.state);state.wallets[0].note='Tín hiệu đã kiểm chứng';
 const raw=requestBody(state),bytes=Buffer.from(raw),split=bytes.indexOf(Buffer.from('ệ'))+1;
 assert.ok(split>0);assert.ok((bytes[split]&0xc0)===0x80);
 const time=Date.now();
 const result=await new Promise((resolve,reject)=>{
  const req=http.request(f.endpoint+'/run',{method:'POST',headers:{'Content-Type':'application/json','x-paper-time':String(time),'x-paper-signature':sign(key,'request',time,raw)}},res=>{
   const chunks=[];res.on('data',c=>chunks.push(c));res.on('end',()=>resolve({status:res.statusCode,body:Buffer.concat(chunks).toString('utf8')}));
  });
  req.on('error',reject);req.write(bytes.subarray(0,split));setTimeout(()=>req.end(bytes.subarray(split)),25);
 });
 assert.equal(result.status,200);assert.equal(calls,1);
 const returned=JSON.parse(result.body);assert.equal(JSON.parse(returned.files['state.json']).wallets[0].note,state.wallets[0].note);
});
test('partial file installation removes stale readiness and cannot publish a mixed batch',async t=>{
 const f=await setup(t,async()=>{}),state=structuredClone(f.state);state.wallets[0].balance=1;
 await fs.writeFile(path.join(f.directory,'.cloud-ready'),'old readiness');
 await fs.writeFile(path.join(f.directory,'state-view.json'),'{"old":true}');
 await fs.mkdir(path.join(f.directory,'contexts','a.json'),{recursive:true});
 const body={runId:'fixture-run',baseRevision:revision,ok:true,files:{'state-view.json':'{"new":true}','contexts/a.json':'{}','state.json':JSON.stringify(state)}};
 await assert.rejects(invokeCloud({...options(f),fetcher:mockResponse(f,body)}),e=>['EPERM','EISDIR','EEXIST','ENOTEMPTY'].includes(e.code));
 assert.deepEqual(JSON.parse(await fs.readFile(path.join(f.directory,'state-view.json'),'utf8')),{new:true});
 assert.deepEqual(await f.read(),f.state);
 await assert.rejects(fs.access(path.join(f.directory,'.cloud-ready')),/ENOENT/);
 assert.ok(!(await fs.readdir(f.directory)).some(n=>n.startsWith('.response-')));
});
