import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {packContext,nextFrame} from './analysis-pack.mjs';
const root=path.dirname(fileURLToPath(import.meta.url));
const base='http://127.0.0.1:'+String(process.env.PAPER_STUDIO_PORT??8792);
const args=process.argv.slice(2),command=args[0];
async function request(route,body){
 const headers=body?{'Content-Type':'application/json',Authorization:'Bearer '+(await fs.readFile(path.join(root,'data','auth-token'),'utf8')).trim()}:{};
 const response=await fetch(base+route,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(90000)});
 const result=await response.json();if(!response.ok)throw Error(result.error??'HTTP '+response.status);return result;
}
async function capture(frame,bootstrap=false){
 const c=await request('/api/context',{frame,bootstrap});
 const source=await fs.readFile(c.snapshotPath,'utf8'),analysis=packContext(JSON.parse(source),source);
 const analysisPath=c.snapshotPath.replace(/\.json$/,'.analysis.json');
 await fs.writeFile(analysisPath,JSON.stringify(analysis));
 return {frame,id:c.id,cycleAt:c.cycleAt,expiresAt:c.expiresAt,snapshotPath:c.snapshotPath,analysisPath};
}
try{
 if(command==='status'){const state=await request('/api/state');console.log(JSON.stringify(state,null,2));}
 else if(command==='next'){
  const state=await request('/api/state'),plan=nextFrame(state);
  const reviews=state.wallets.flatMap(w=>w.trades.filter(t=>['TP','SL','EARLY_EXIT'].includes(t.status)&&!w.reviews.some(r=>r.tradeId===t.id)).map(t=>({frame:w.frame,trade:t})));
  console.log(JSON.stringify({...plan,worker:state.worker,reviews,...(plan.frame?await capture(plan.frame):{})},null,2));
 }
 else if(command==='context'){
  const frames=args[1]&&args[1]!=='all'?[args[1]]:['15m','1h','4h'];
  const results=[];
  for(const frame of frames)try{results.push(await capture(frame,args.includes('--bootstrap')));}catch(e){results.push({frame,error:e.message});}
  console.log(JSON.stringify(results,null,2));if(results.every(x=>x.error))process.exitCode=2;
 }
 else if(command==='submit'||command==='review'||command==='manage'){
  if(!args[1])throw Error('Provide JSON file path');const body=JSON.parse(await fs.readFile(path.resolve(args[1]),'utf8'));
  console.log(JSON.stringify(await request(command==='submit'?'/api/decision':command==='manage'?'/api/manage':'/api/review',body),null,2));
 }else throw Error('Usage: node cli.mjs next | status | context [15m|1h|4h|all] [--bootstrap] | submit decision.json | review review.json | manage management.json');
}catch(e){console.error(e.message);process.exitCode=1;}
