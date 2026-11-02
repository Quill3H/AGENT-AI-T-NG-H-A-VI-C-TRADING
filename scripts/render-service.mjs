import http from 'node:http';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {runCycle} from './gemini-paper.mjs';
import {sign,verify,validateState,safeFile} from './cloud-transport.mjs';
import {probeOkx} from './probe-okx.mjs';

export async function loadKey(){
 const key=process.env.GEMINI_API_KEY??await fs.readFile('/etc/secrets/GEMINI_API_KEY','utf8');
 if(!key.trim())throw Error('Missing Gemini credential');return key.trim();
}
export function createCloudServer({key,cycle=runCycle,clock=Date.now}={}){
 const cache=new Map();let busy=false,publicView=null,okxProbe=null,okxProbeAt=0;
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
  const send=(status,value)=>{res.writeHead(status);res.end(JSON.stringify(value));};
  if(req.url==='/okx-probe'&&req.method==='GET'){
   if(!okxProbe||clock()-okxProbeAt>300000){okxProbeAt=clock();okxProbe=probeOkx();}
   try{send(200,await okxProbe);}catch{send(502,{ok:false,error:'OKX diagnostic unavailable'});}return;
  }
  if(req.method==='GET'&&['/','/dashboard.js','/style.css'].includes(req.url)){
   const asset={'/':['index.html','text/html'],'/dashboard.js':['dashboard.js','text/javascript'],'/style.css':['style.css','text/css']}[req.url];
   try{res.setHeader('Content-Type',asset[1]);res.end(await fs.readFile(new URL('../paper-bot-studio/'+asset[0],import.meta.url)));}catch{send(500,{error:'Dashboard unavailable'});}return;
  }
  if(req.method==='GET'&&req.url==='/api/state'){
   try{
    if(!publicView||clock()-publicView.fetchedAt>30000){
     const r=await fetch('https://raw.githubusercontent.com/Quill3H/AGENT-AI-T-NG-H-A-VI-C-TRADING/paper-state/state-view.json',{signal:AbortSignal.timeout(15000)});
     if(!r.ok)throw Error('No committed cloud snapshot');publicView={fetchedAt:clock(),value:await r.json()};
    }
    const view=structuredClone(publicView.value);view.serverTime=clock();
    view.worker.healthy=clock()-view.cloudUpdatedAt<1200000&&!view.worker.error;view.policy.ai='Gemini API scheduled';view.policy.monitorMs=900000;
    send(200,view);
   }catch{send(503,{error:'No committed cloud ledger available yet'});}return;
  }
  if(req.url==='/health'){send(200,{ok:true,mode:'PAPER_CLOUD',credentialConfigured:!!key});return;}
  if(req.url==='/probe'&&req.method==='GET'){
   try{const r=await fetch('https://fapi.binance.com/fapi/v1/time',{signal:AbortSignal.timeout(15000)});send(200,{status:r.status,ok:r.ok});}catch{send(502,{ok:false});}return;
  }
  if(req.url!=='/run'||req.method!=='POST'){send(404,{error:'Not found'});return;}
  let raw='';
  try{
   const chunks=[];let bytes=0;
   for await(const chunk of req){bytes+=chunk.length;if(bytes>10*1024*1024){send(413,{error:'Body too large'});return;}chunks.push(chunk);}
   raw=Buffer.concat(chunks).toString('utf8');
   const time=Number(req.headers['x-paper-time']);
   if(!key||!verify(key,'request',time,raw,req.headers['x-paper-signature'],clock())){send(401,{error:'Unauthorized or expired request'});return;}
   const input=JSON.parse(raw);validateState(input.state);
   if(!/^[a-zA-Z0-9_-]{1,100}$/.test(input.runId??'')||!/^[a-f0-9]{40}$/.test(input.baseRevision??''))throw Error('Invalid request identity');
   if(input.model!=='gemini-3-flash-preview')throw Error('Unapproved model');
   if(!input.intents||typeof input.intents!=='object'||Array.isArray(input.intents))throw Error('Invalid intents');
   for(const [name,text] of Object.entries(input.intents)){
    if(!/^decisions\/intent-[a-zA-Z0-9_-]+\.json$/.test(name)||!safeFile(name)||typeof text!=='string')throw Error('Invalid intent file');JSON.parse(text);
   }
   const identity=sign(key,'request',0,raw);
   for(const [id,item] of cache)if(clock()-item.createdAt>900000)cache.delete(id);
   const cached=cache.get(input.runId);
   if(cached){if(cached.identity!==identity){send(409,{error:'Run identity conflict'});return;}const result=await cached.promise;res.writeHead(200,result.headers);res.end(result.body);return;}
   if(busy||cache.size>=8){send(409,{error:'Busy; no automatic ambiguous retry'});return;}
   busy=true;
   const promise=(async()=>{
    const directory=await fs.mkdtemp(path.join(os.tmpdir(),'paper-cloud-'));
    try{
     await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(input.state));
     await fs.mkdir(path.join(directory,'decisions'));
     for(const [name,text] of Object.entries(input.intents))await fs.writeFile(path.join(directory,name),text);
     let error=null;
     try{await cycle({directory,maxRunMs:360000});}catch(e){error=String(e.message).replaceAll(key,'[redacted]');}
     const files={};
     for(const file of ['state.json','state-view.json'])try{files[file]=await fs.readFile(path.join(directory,file),'utf8');}catch(e){if(e.code!=='ENOENT')throw e;}
     for(const sub of ['contexts','decisions']){
      let names=[];try{names=await fs.readdir(path.join(directory,sub));}catch(e){if(e.code!=='ENOENT')throw e;}
      for(const name of names)if(safeFile(sub+'/'+name))files[sub+'/'+name]=await fs.readFile(path.join(directory,sub,name),'utf8');
     }
     validateState(JSON.parse(files['state.json']));
     const body=JSON.stringify({runId:input.runId,baseRevision:input.baseRevision,ok:!error,error,files,provisional:true});
     const responseTime=clock();return {body,headers:{'x-paper-time':String(responseTime),'x-paper-signature':sign(key,'response',responseTime,body)}};
    }finally{
     if(path.dirname(directory)!==os.tmpdir()||!path.basename(directory).startsWith('paper-cloud-'))throw Error('Invalid cleanup path');
     await fs.rm(directory,{recursive:true,force:true});busy=false;
    }
   })();
   cache.set(input.runId,{identity,promise,createdAt:clock()});
   try{const result=await promise;res.writeHead(200,result.headers);res.end(result.body);}catch{cache.delete(input.runId);send(500,{error:'Cloud run failed; keep committed ledger'});}
  }catch{if(!res.headersSent)send(422,{error:'Invalid cloud request'});}
 });
 server.requestTimeout=450000;server.headersTimeout=30000;
 return server;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const key=await loadKey();process.env.GEMINI_API_KEY=key;process.env.GEMINI_MODEL='gemini-3-flash-preview';
 createCloudServer({key}).listen(Number(process.env.PORT??10000),'0.0.0.0',()=>console.log('Paper cloud service ready'));
}
