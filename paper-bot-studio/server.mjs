import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {randomUUID,randomBytes,timingSafeEqual} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {newState,FRAMES,SYMBOLS,LEVERAGE,cycleFor,acceptDecision,replayTrades,applyFunding,walletMetrics,manageTrade} from './engine.mjs';
import {BinanceMarket} from './market.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
const assetMap={'/':['index.html','text/html'],'/dashboard.js':['dashboard.js','text/javascript'],'/style.css':['style.css','text/css']};
async function atomic(filename,data){const temp=filename+'.tmp';const f=await fs.open(temp,'w');try{await f.writeFile(JSON.stringify(data,null,2));await f.sync();}finally{await f.close();}await fs.rename(temp,filename);}
export async function createRuntime({directory=path.join(ROOT,'data'),market=new BinanceMarket(),clock=()=>Date.now()}={}){
 await fs.mkdir(directory,{recursive:true});await fs.mkdir(path.join(directory,'contexts'),{recursive:true});
 const lockPath=path.join(directory,'worker.lock'),statePath=path.join(directory,'state.json');
 let lock;
 try{lock=await fs.open(lockPath,'wx');}catch(e){
  if(e.code!=='EEXIST')throw e;
  let pid;try{pid=Number((await fs.readFile(lockPath,'utf8')).trim());}catch{}
  let alive=true;if(Number.isSafeInteger(pid)&&pid>0)try{process.kill(pid,0);}catch(err){if(err.code==='ESRCH')alive=false;}
  if(alive)throw Error('Worker directory locked');
  await fs.unlink(lockPath);lock=await fs.open(lockPath,'wx');
 }
 await lock.writeFile(String(process.pid));await lock.close();
 let state,token;
 try{
  try{state=JSON.parse(await fs.readFile(statePath,'utf8'));if(state.version!==1||state.wallets?.length!==3||state.mode!=='PAPER_ONLY'||state.wallets.some((w,i)=>w.frame!==Object.keys(FRAMES)[i]||!Number.isFinite(w.balance)||!Array.isArray(w.trades)||!Array.isArray(w.decisions)))throw Error('Invalid ledger schema');}
  catch(e){if(e.code==='ENOENT')state=newState(clock());else throw Error('Corrupt ledger; manual review required: '+e.message);}
  const tokenPath=path.join(directory,'auth-token');
  try{token=(await fs.readFile(tokenPath,'utf8')).trim();}catch(e){if(e.code!=='ENOENT')throw e;token=randomBytes(32).toString('hex');await fs.writeFile(tokenPath,token,{mode:0o600});}
  state.worker.startedAt=clock();await atomic(statePath,state);
 }catch(e){await fs.unlink(lockPath);throw e;}
 let queue=Promise.resolve(),timer,closed=false;
 const serial=fn=>{const result=queue.then(fn);queue=result.catch(()=>{});return result;};
 const save=async()=>{state.updatedAt=clock();await atomic(statePath,state);};
 async function transaction(fn){const previous=structuredClone(state);try{const result=await fn();await save();return result;}catch(e){state=previous;throw e;}}
 function view(){const freshQuotes=Object.fromEntries(Object.entries(state.quotes).filter(([,q])=>clock()-q.time>=0&&clock()-q.time<=30000));return {...state,contexts:state.contexts.map(({id,frame,cycleAt,capturedAt,expiresAt,snapshotPath})=>({id,frame,cycleAt,capturedAt,expiresAt,snapshotPath})),wallets:state.wallets.map(w=>({...w,metrics:walletMetrics(w,freshQuotes)})),serverTime:clock(),policy:{venue:state.venue??market.venue??'BINANCE',fundingPolicy:state.fundingPolicy??'NATIVE_EVENT_PRICE',allocation:'3–5% booked balance as initial margin PER TRADE; notional=margin*symbol leverage',allocationScope:'PER_TRADE_CUMULATIVE',risk:'SL loss depends on stop distance, leverage and costs; not capped at3–5%',riskScope:'SL_DISTANCE_DEPENDENT',riskBasis:'BOOKED_BALANCE_BEFORE_ENTRY',maxOpenTrades:null,mandatoryEntry:true,feePerSide:.0005,slippagePerSide:.0002,leverageBySymbol:LEVERAGE,allocationMin:.03,allocationMax:.05,aggregateNotionalCap:null,marginModel:'VIRTUAL_NO_MARGIN_RESERVATION',positionManagement:'AI_UPDATE_LEVELS_OR_EARLY_EXIT',ai:'Codex heartbeat',monitorMs:10000},worker:{...state.worker,healthy:state.worker.lastSuccess!==null&&clock()-state.worker.lastSuccess<45000&&!state.worker.error}};}
 async function capture(body){return transaction(async()=>{
  const frame=body.frame;if(!FRAMES[frame])throw Error('Invalid frame');
  const started=clock(),cycleAt=cycleFor(frame,started),wallet=state.wallets.find(w=>w.frame===frame);
  if(wallet.decisions.some(d=>d.cycleAt>=cycleAt))throw Error('No new cycle; already decided');
  if(started-cycleAt>600000&&!body.bootstrap)throw Error('Missed cycle; wait for next candle boundary');
  if(body.bootstrap&&wallet.decisions.length)throw Error('Bootstrap only allowed on the first decision');
  const data=await market.capture(frame,cycleAt);
  if(data.closedThrough!==cycleAt-1||!Array.isArray(data.symbols)||!data.symbols.length)throw Error('Future or missing candle coverage');
  for(const s of data.symbols){
   if(!SYMBOLS.includes(s.symbol)||!s.candles?.length||s.candles.at(-1).closeTime!==cycleAt-1)throw Error('Invalid symbol/candle coverage');
   for(let i=0;i<s.candles.length;i++){const b=s.candles[i];if(b.closeTime>=cycleAt||b.openTime>b.closeTime||!['o','h','l','c','v'].every(k=>Number.isFinite(b[k]))||(i&&b.openTime-s.candles[i-1].openTime!==FRAMES[frame]))throw Error('Malformed or future candle');}
  }
  const capturedAt=clock();if(capturedAt-started>90000)throw Error('Market capture too slow');
  const c={id:randomUUID(),frame,cycleAt,capturedAt,expiresAt:Math.min(capturedAt+240000,cycleAt+FRAMES[frame]),bootstrap:!!body.bootstrap};
  if(c.expiresAt<=capturedAt)throw Error('Expired market cycle');
  c.snapshotPath=path.join(directory,'contexts',c.id+'.json');
  const lowerIndex=Object.keys(FRAMES).indexOf(frame)-1,lower=lowerIndex>=0?state.wallets[lowerIndex]:null;
  const context={...c,market:data,wallet:structuredClone(wallet),lowerFrame:lower?{frame:lower.frame,decisions:lower.decisions.slice(-5),closed:lower.trades.filter(t=>t.status!=='OPEN').slice(-5)}:null,policy:view().policy};
  await atomic(c.snapshotPath,context);state.contexts.push(c);state.contexts=state.contexts.slice(-64);return context;
 });}
 async function decide(body){
  try{return await transaction(async()=>{
   const c=state.contexts.find(x=>x.id===body.contextId);if(!c)throw Error('Unknown context');
   let q=null,r=null;
   if(body.action!=='HOLD'){q=await market.quote(body.symbol);r=await market.rules(body.symbol);if(q.askQty!==undefined){const maxQty=body.action==='LONG'?q.askQty:q.bidQty;if(!(maxQty>0))throw Error('Empty top of book');r={...r,maxQty:Math.min(r.maxQty,maxQty)};}}
   const record=acceptDecision(state,body,c,q,r,clock());if(q)state.quotes[q.symbol]=q;return record;
  });}catch(e){
   state.rejections.push({time:clock(),frame:body?.frame,contextId:body?.contextId,action:body?.action,error:e.message});state.rejections=state.rejections.slice(-200);await save();throw e;
  }
 }
 async function manage(body){return transaction(async()=>{
  const wallet=state.wallets.find(w=>w.frame===body.frame),trade=wallet?.trades.find(t=>t.id===body.tradeId);
  if(!trade)throw Error('Unknown trade');
  const duplicate=trade.managementEvents?.find(e=>e.id===body.managementId);if(duplicate)return duplicate;
  if(trade.status!=='OPEN')throw Error('Trade already closed or unverified');
  const q=await market.quote(trade.symbol),now=clock();
  if(!Number.isFinite(q.time)||q.time>now||now-q.time>15000||q.time<=trade.openedAt||q.time<(trade.replayTime??trade.openedAt))throw Error('Management quote is stale or precedes verified replay');
  const replay=await market.replay(trade,q.time);
  if(!replay.events.every(e=>e.T<=q.time))throw Error('Future trade in management replay');
  replayTrades(wallet,trade,replay.events,clock());
  const through=trade.closedAt??q.time;
  applyFunding(wallet,trade,await market.funding(trade,through),through,clock());trade.lastFundingCheckedAt=clock();
  if(trade.status!=='OPEN')return {preempted:true,tradeId:trade.id,status:trade.status,reason:'Existing TP/SL triggered before management'};
  if(!replay.complete||replay.through!==q.time)throw Error('Complete replay required before management');
  trade.replayTime=q.time;trade.replayBehind=false;
  const result=manageTrade(wallet,trade,body,q,await market.rules(trade.symbol),clock());state.quotes[trade.symbol]=q;return result;
 });}
 async function tick(){return serial(()=>transaction(async()=>{
  const errors=[];state.worker.lastTick=clock();
  const quotes=await Promise.allSettled(SYMBOLS.map(s=>market.quote(s)));
  quotes.forEach((v,i)=>{if(v.status==='fulfilled')state.quotes[SYMBOLS[i]]=v.value;else errors.push(SYMBOLS[i]+': '+v.reason.message);});
  for(const wallet of state.wallets){
   const walletErrors=[];
   if(wallet.trades.some(t=>t.status==='UNVERIFIED'))walletErrors.push('Unverified trade requires review');
   for(const tradeId of wallet.trades.filter(t=>t.status==='OPEN').map(t=>t.id)){
    const trade=wallet.trades.find(t=>t.id===tradeId),previous=structuredClone(wallet);
    try{
     const cutoff=clock(),result=await market.replay(trade,cutoff);
     if(!result.events.every(e=>e.T<=cutoff))throw Error('Future trade in replay');
     replayTrades(wallet,trade,result.events,clock());
     const through=trade.closedAt??result.through;
     applyFunding(wallet,trade,await market.funding(trade,through),through,clock());trade.lastFundingCheckedAt=clock();
     trade.replayBehind=trade.status==='OPEN'&&!result.complete;
     if((result.complete||market.venue==='OKX')&&trade.status==='OPEN')trade.replayTime=through;
     if(trade.status==='OPEN'&&!result.complete)walletErrors.push(trade.id+': Replaying market history');
    }catch(e){
     Object.assign(wallet,previous);walletErrors.push(tradeId+': '+e.message);
    }
   }
   const fundingErrors=[];
   for(const trade of wallet.trades.filter(t=>['TP','SL','EARLY_EXIT'].includes(t.status)&&clock()-(t.lastFundingCheckedAt??0)>300000)){
    const previous=structuredClone(wallet);
    try{applyFunding(wallet,trade,await market.funding(trade,clock()),clock());trade.lastFundingCheckedAt=clock();}
    catch(e){Object.assign(wallet,previous);fundingErrors.push(e.message);break;}
   }
   if(fundingErrors.length)walletErrors.push('Funding review: '+fundingErrors.join('; '));
   wallet.blocked=walletErrors.length?walletErrors.join(' | '):null;
   if(wallet.blocked)errors.push(wallet.frame+': '+wallet.blocked);
  }
  state.worker.error=errors.length?errors.join(' | '):null;if(!errors.length)state.worker.lastSuccess=clock();
  return {ok:!errors.length,error:state.worker.error};
 }));}
 function authorized(req){const input=Buffer.from(req.headers.authorization??'');const expected=Buffer.from('Bearer '+token);return input.length===expected.length&&timingSafeEqual(input,expected);}
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");
  const send=(code,data)=>{res.writeHead(code,{'Content-Type':'application/json; charset=utf-8'});res.end(JSON.stringify(data));};
  try{
   if(req.headers.host!==`127.0.0.1:${server.address().port}`){send(403,{error:'Invalid host'});return;}
   if(req.method==='GET'){
    if(req.url==='/api/state'){send(200,await serial(()=>view()));return;}
    if(req.url==='/api/health'){send(200,await serial(()=>({...view().worker,mode:'PAPER_ONLY'})));return;}
    const asset=assetMap[req.url];if(!asset){send(404,{error:'Not found'});return;}
    res.writeHead(200,{'Content-Type':asset[1]+'; charset=utf-8'});res.end(await fs.readFile(path.join(ROOT,asset[0])));return;
   }
   if(req.method!=='POST'){send(405,{error:'Method not allowed'});return;}
   if(req.headers.origin&&req.headers.origin!==`http://${req.headers.host}`){send(403,{error:'Cross origin request'});return;}
   if(!authorized(req)){send(401,{error:'Unauthorized'});return;}
   let text='';for await(const chunk of req){text+=chunk;if(text.length>64000){send(413,{error:'Body too large'});return;}}
   let body;try{body=JSON.parse(text);}catch{send(400,{error:'Invalid JSON'});return;}
   const result=await serial(async()=>{
    if(req.url==='/api/context')return capture(body);
    if(req.url==='/api/decision')return decide(body);
    if(req.url==='/api/manage')return manage(body);
    if(req.url==='/api/review')return transaction(async()=>{const w=state.wallets.find(w=>w.frame===body.frame),trade=w?.trades.find(t=>t.id===body.tradeId);if(!trade||!['TP','SL','EARLY_EXIT'].includes(trade.status)||typeof body.lesson!=='string'||body.lesson.length<10||body.lesson.length>6000)throw Error('Invalid closed trade review');if(w.reviews.some(r=>r.tradeId===body.tradeId))throw Error('Review already recorded');const review={tradeId:body.tradeId,time:clock(),lesson:body.lesson};w.reviews.push(review);return review;});
    throw Error('Unknown command');
   });send(200,result);
  }catch(e){send(422,{error:e.message});}
 });
 async function poll(){if(closed)return;try{await tick();}catch(e){console.error(e);}finally{if(!closed)timer=setTimeout(poll,10000);}}
 return {token,get port(){return server.address()?.port;},async listen(port=8792){await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',resolve);});},tick,async start(){await tick();if(!closed)timer=setTimeout(poll,10000);},async close(){if(closed)return;closed=true;clearTimeout(timer);await queue;await new Promise(resolve=>server.listening?server.close(resolve):resolve());await fs.unlink(lockPath);}};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const runtime=await createRuntime();await runtime.listen(Number(process.env.PAPER_STUDIO_PORT??8792));console.log(`Paper AI Studio http://127.0.0.1:${runtime.port}`);await runtime.start();
 for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>runtime.close().then(()=>process.exit(0)));
}
