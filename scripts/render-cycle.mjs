import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {sign,verify,safeFile,validateState} from './cloud-transport.mjs';
import {newState,FRAMES} from '../paper-bot-studio/engine.mjs';

export async function invokeCloud({directory,key,endpoint='https://paper-studio-connectivity.onrender.com',baseRevision,runId=randomUUID(),fetcher=fetch,testEndpoint=false,warmupDelayMs=3000,kronosForecasts=[]}={}){
 if(!key?.trim())throw Error('Missing GEMINI_API_KEY');
 if(!testEndpoint&&endpoint!=='https://paper-studio-connectivity.onrender.com')throw Error('Unapproved cloud endpoint');
 await fs.rm(path.join(directory,'.cloud-ready'),{force:true});
 const warmUntil=Date.now()+120000;
 for(let attempt=0;;attempt++){
  const left=warmUntil-Date.now();if(left<=0||attempt>=40)throw Error('Render warmup deadline reached');
  const health=await fetcher(endpoint+'/health',{signal:AbortSignal.timeout(Math.min(left,15000)),redirect:'error'});
  if(health.ok)break;
  if(![502,503,504].includes(health.status))throw Error(`Render warmup HTTP ${health.status}`);
  await new Promise(resolve=>setTimeout(resolve,Math.min(warmupDelayMs,Math.max(0,warmUntil-Date.now()))));
 }
 const state=validateState(JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'))),intents={};
 for(const [frame,ms] of Object.entries(FRAMES)){
  const name=`decisions/intent-${frame}-${Math.floor(Date.now()/ms)*ms}.json`;
  try{intents[name]=await fs.readFile(path.join(directory,name),'utf8');}catch(e){if(e.code!=='ENOENT')throw e;}
 }
 const body=JSON.stringify({state,intents,runId,baseRevision,model:'gemini-3-flash-preview',kronosForecasts}),time=Date.now();
 const response=await fetcher(endpoint+'/run',{method:'POST',headers:{'Content-Type':'application/json','x-paper-time':String(time),'x-paper-signature':sign(key,'request',time,body)},body,redirect:'error',signal:AbortSignal.timeout(420000)});
 if(!response.ok)throw Error(`Cloud HTTP ${response.status}; keep committed state, do not automatically retry`);
 const raw=await response.text();
 if(Buffer.byteLength(raw)>30*1024*1024||!verify(key,'response',Number(response.headers.get('x-paper-time')),raw,response.headers.get('x-paper-signature')))throw Error('Invalid cloud response signature/size');
 const result=JSON.parse(raw);
 if(result.runId!==runId||result.baseRevision!==baseRevision||typeof result.ok!=='boolean'||!result.files||typeof result.files!=='object'||Array.isArray(result.files))throw Error('Response identity mismatch');
 for(const [name,text] of Object.entries(result.files)){if(!safeFile(name)||typeof text!=='string')throw Error('Unsafe response file');JSON.parse(text);}
 validateState(JSON.parse(result.files['state.json']));
 // The workflow commits the whole batch; state.json is installed last, never from an unsigned response.
 const staged=await fs.mkdtemp(path.join(directory,'.response-'));
 try{
  for(const [name,text] of Object.entries(result.files)){const target=path.join(staged,name);await fs.mkdir(path.dirname(target),{recursive:true});await fs.writeFile(target,text);}
  for(const name of Object.keys(result.files).filter(n=>n!=='state.json').concat('state.json')){
   const target=path.join(directory,name);await fs.mkdir(path.dirname(target),{recursive:true});await fs.rename(path.join(staged,name),target);
  }
 }finally{
  if(path.dirname(staged)!==path.resolve(directory)||!path.basename(staged).startsWith('.response-'))throw Error('Invalid staging cleanup path');
  await fs.rm(staged,{recursive:true,force:true});
 }
 await fs.writeFile(path.join(directory,'.cloud-ready'),JSON.stringify({runId:result.runId,baseRevision,ok:result.ok}));
 return {ok:result.ok,error:result.error,runId:result.runId,diagnostics:result.diagnostics??null};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{
  const directory=path.resolve(process.env.PAPER_DATA_DIR??'paper-state');
  const validation=process.env.PAPER_VALIDATION==='true';
  if(validation){
   if(path.basename(directory)!=='cloud-validation')throw Error('Validation must use isolated cloud-validation directory');
   await fs.mkdir(directory,{recursive:true});
   await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(newState(Date.now(),'OKX')));
  }
  const baseRevision=execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8',cwd:validation?process.cwd():directory}).trim();
  let kronosForecasts=[];if(process.env.KRONOS_FORECAST_PATH)try{const advisory=JSON.parse(await fs.readFile(process.env.KRONOS_FORECAST_PATH,'utf8'));if(Array.isArray(advisory.frames))kronosForecasts=advisory.frames;}catch{console.error('No Kronos bundle; cloud will reconcile existing positions and block new entries');}
  const result=await invokeCloud({directory,key:process.env.GEMINI_API_KEY,baseRevision,kronosForecasts,runId:`${process.env.GITHUB_RUN_ID??randomUUID()}-${process.env.GITHUB_RUN_ATTEMPT??1}`});
  console.log(JSON.stringify({...result,error:result.error?String(result.error).replaceAll(process.env.GEMINI_API_KEY??'REDACTED','[redacted]'):null,validation,commitRequired:!validation}));
  if(!result.ok)process.exitCode=1;
 }catch(e){console.error(String(e.message).replaceAll(process.env.GEMINI_API_KEY??'REDACTED','[redacted]'));process.exitCode=1;}
}
