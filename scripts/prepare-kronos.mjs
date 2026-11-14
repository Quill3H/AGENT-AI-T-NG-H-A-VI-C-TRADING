import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {sign,verify,validateState} from './cloud-transport.mjs';
import {FRAMES} from '../paper-bot-studio/engine.mjs';
const ENDPOINT='https://paper-studio-connectivity.onrender.com';
export function dueKronosFrames(state,now=Date.now()){
 validateState(state);
 return Object.entries(FRAMES).filter(([frame,ms])=>{const w=state.wallets.find(w=>w.frame===frame),cycleAt=Math.floor(now/ms)*ms;return w.enabled&&!w.blocked&&w.balance>0&&now-cycleAt<=600000&&!w.decisions.some(d=>d.cycleAt>=cycleAt);}).map(([frame])=>frame);
}
export async function fetchKronosInputs({key,frames,endpoint=ENDPOINT,fetcher=fetch}={}){
 if(endpoint!==ENDPOINT)throw Error('Unapproved forecast endpoint');
 const body=JSON.stringify({task:'KRONOS_INPUT_V1',frames}),time=Date.now();
 const response=await fetcher(endpoint+'/kronos/input',{method:'POST',headers:{'Content-Type':'application/json','x-paper-time':String(time),'x-paper-signature':sign(key,'request',time,body)},body,redirect:'error',signal:AbortSignal.timeout(150000)});
 if(!response.ok)throw Error('Kronos input HTTP '+response.status);
 const raw=await response.text();
 if(Buffer.byteLength(raw)>2*1024*1024||!verify(key,'response',Number(response.headers.get('x-paper-time')),raw,response.headers.get('x-paper-signature')))throw Error('Kronos input signature/size invalid');
 const data=JSON.parse(raw);if(data.version!==1||!Array.isArray(data.frames)||data.frames.length>3)throw Error('Invalid forecast input');return data;
}
export async function prepareKronos({directory=path.resolve(process.env.PAPER_DATA_DIR??'paper-state'),output=path.resolve(process.env.KRONOS_FORECAST_PATH??'.kronos/forecast.json'),key=process.env.GEMINI_API_KEY,python=process.env.KRONOS_PYTHON??'python',source=path.resolve('.kronos/source'),models=path.resolve('.kronos/models')}={}){
 await fs.mkdir(path.dirname(output),{recursive:true});
 await fs.writeFile(output,JSON.stringify({version:1,frames:[],errors:{setup:'Inference not completed'}}));
 const state=JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'));
 const frames=dueKronosFrames(state);
 if(!frames.length){await fs.writeFile(output,JSON.stringify({version:1,frames:[],errors:{}}));return;}
 try{
  const input=await fetchKronosInputs({key,frames}),inputPath=path.join(path.dirname(output),'input.json');
  await fs.writeFile(inputPath,JSON.stringify(input));
  if(!input.frames.length){await fs.writeFile(output,JSON.stringify(input));return;}
  const env={...process.env};delete env.GEMINI_API_KEY;delete env.GITHUB_TOKEN;delete env.GH_TOKEN;
  const worker=fileURLToPath(new URL('./kronos_forecast.py',import.meta.url));
  const {stdout}=await promisify(execFile)(python,[worker,'--input',inputPath,'--output',output,'--source',source,'--models',models],{timeout:150000,maxBuffer:1024*1024,env});
  console.log(stdout.trim());
 }catch(e){
  // Settlement still executes in /run with an empty advisory bundle.
  const message=String(e.message).replaceAll(key??'REDACTED','[redacted]').slice(0,500);
  await fs.writeFile(output,JSON.stringify({version:1,frames:[],errors:{setup:message}}));console.error('Kronos unavailable; new entries will be blocked');
 }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))prepareKronos().catch(e=>{console.error('Kronos preparation failed');process.exitCode=1;});
