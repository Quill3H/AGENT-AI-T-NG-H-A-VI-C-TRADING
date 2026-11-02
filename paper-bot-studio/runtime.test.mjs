import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRuntime} from './server.mjs';
const start=Date.UTC(2026,9,31,12);
const rules={stepSize:.001,minQty:.001,maxQty:10000,minNotional:5,tickSize:.01};
function fixture(){let now=start;return {clock:()=>now,advance:n=>now+=n,market:{async capture(frame,cutoff){return {frame,serverTime:now,closedThrough:cutoff-1,symbols:[{symbol:'SOLUSDT',candles:[{openTime:cutoff-900000,closeTime:cutoff-1,o:100,h:102,l:98,c:100,v:1000}]}],source:'test market'};},async quote(symbol){return {symbol,bid:99.99,ask:100,time:now};},async rules(){return rules;},async replay(){return {events:[],complete:true,through:now};},async funding(){return [];}}};}
const testRoot=path.join(path.dirname(fileURLToPath(import.meta.url)),'.test-data');
async function setup(t){await fs.mkdir(testRoot,{recursive:true});const dir=await fs.mkdtemp(path.join(testRoot,'runtime-'));const f=fixture();const rt=await createRuntime({directory:dir,market:f.market,clock:f.clock});await rt.listen(0);t.after(async()=>{await rt.close();if(path.dirname(dir)!==testRoot)throw Error('Unexpected test cleanup path');await fs.rm(dir,{recursive:true,force:true});});return {...f,rt,dir,base:`http://127.0.0.1:${rt.port}`,token:rt.token};}
async function post(s,url,body,token=s.token){const r=await fetch(s.base+url,{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify(body)});return {status:r.status,body:await r.json()};}
test('auth protects mutations, GET state excludes secrets and same-site origin is enforced',async t=>{
 const s=await setup(t);assert.equal((await post(s,'/api/context',{frame:'15m'},'wrong')).status,401);
 const r=await fetch(s.base+'/api/state');const state=await r.json();assert.equal(state.wallets.length,3);assert.ok(!JSON.stringify(state).includes(s.token));
 assert.equal(state.policy.allocationScope,'PER_TRADE_CUMULATIVE');assert.equal(state.policy.maxOpenTrades,null);assert.equal(state.policy.aggregateNotionalCap,null);assert.deepEqual(state.policy.leverageBySymbol,{BTCUSDT:15,ETHUSDT:10,SOLUSDT:7,HYPEUSDT:5});assert.equal(state.policy.mandatoryEntry,true);
 const cross=await fetch(s.base+'/api/context',{method:'POST',headers:{Origin:'https://attacker.example',Authorization:'Bearer '+s.token,'Content-Type':'application/json'},body:JSON.stringify({frame:'15m'})});assert.equal(cross.status,403);
});
test('real HTTP entry, restart and duplicate protection preserve balances',async t=>{
 const s=await setup(t);const c=await post(s,'/api/context',{frame:'15m'});assert.equal(c.status,200);
 const d={contextId:c.body.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI discretionary',reason:'Sample',invalidation:'Support break'};
 assert.equal((await post(s,'/api/decision',d)).status,200);assert.equal((await post(s,'/api/decision',d)).status,422);
 await s.rt.close();const restarted=await createRuntime({directory:s.dir,market:s.market,clock:s.clock});await restarted.listen(0);
 try{const state=await (await fetch(`http://127.0.0.1:${restarted.port}/api/state`)).json();assert.equal(state.wallets[0].decisions.length,1);assert.ok(Math.abs(state.wallets[0].balance-99.98604721)<1e-9);}finally{await restarted.close();}
});
test('fails closed on future candles, capture failure and expired decision',async t=>{
 const s=await setup(t);const c=await post(s,'/api/context',{frame:'15m'});s.advance(240001);
 const d={contextId:c.body.id,frame:'15m',action:'HOLD',method:'AI',reason:'No edge',invalidation:'Breakout'};
 assert.equal((await post(s,'/api/decision',d)).status,422);
 s.market.capture=async()=>({serverTime:s.clock(),closedThrough:start+900000,symbols:[]});
 assert.equal((await post(s,'/api/context',{frame:'1h'})).status,422);
 assert.equal((await (await fetch(s.base+'/api/state')).json()).wallets[0].balance,100);
});
test('single writer and corrupt storage cannot silently reset wallet funds',async t=>{
 const s=await setup(t);await assert.rejects(()=>createRuntime({directory:s.dir,market:s.market,clock:s.clock}),/locked/i);
 await s.rt.close();await fs.writeFile(path.join(s.dir,'state.json'),'broken');await assert.rejects(()=>createRuntime({directory:s.dir,market:s.market,clock:s.clock}),/corrupt/i);
});
test('tick settles trade, writes funding once, persists it and reports errors rather than fabricated prices',async t=>{
 const s=await setup(t);const c=(await post(s,'/api/context',{frame:'15m'})).body;
 const d={contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Support break'};
 assert.equal((await post(s,'/api/decision',d)).status,200);s.advance(2000);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1500}],complete:true,through:s.clock()});s.market.funding=async()=>[{fundingTime:start+1000,fundingRate:'.001',markPrice:'100'}];
 await s.rt.tick();await s.rt.tick();const state=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8'));const w=state.wallets[0];
 assert.equal(w.trades[0].status,'SL');assert.equal(w.trades[0].fundingEvents.length,1);assert.ok(Math.abs(w.balance-(100+w.trades[0].pnl))<1e-9);
 s.market.quote=async()=>{throw Error('network down');};await s.rt.tick();const view=await (await fetch(s.base+'/api/state')).json();assert.match(view.worker.error,/network down/);
});
test('a first-touch closure during incomplete replay releases the wallet risk block',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1000}],complete:false,through:start+1000});await s.rt.tick();
 const view=await (await fetch(s.base+'/api/state')).json();assert.equal(view.wallets[0].trades[0].status,'SL');assert.equal(view.wallets[0].blocked,null);
});
test('funding published after closure is reconciled exactly once in a later tick',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1500}],complete:true,through:s.clock()});await s.rt.tick();
 const before=(await (await fetch(s.base+'/api/state')).json()).wallets[0].balance;
 s.market.funding=async()=>[{fundingTime:start+1000,fundingRate:'.001',markPrice:'100'}];s.advance(300001);await s.rt.tick();await s.rt.tick();
 const w=(await (await fetch(s.base+'/api/state')).json()).wallets[0];assert.ok(w.balance<before);assert.equal(w.trades[0].fundingEvents.length,1);assert.ok(Math.abs(w.balance-(100+w.trades[0].pnl))<1e-9);
});
test('concurrent HTTP readers cannot observe a settlement that funding failure rolls back',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 let entered,release;const waiting=new Promise(r=>entered=r),gate=new Promise(r=>release=r);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1500}],complete:true,through:s.clock()});s.market.funding=async()=>{entered();await gate;throw Error('Funding offline');};
 const ticking=s.rt.tick();await waiting;const response=fetch(s.base+'/api/state');
 const early=await Promise.race([response.then(()=>true),new Promise(r=>setTimeout(()=>r(false),50))]);release();await ticking;
 const view=await (await response).json();assert.equal(early,false);assert.equal(view.wallets[0].trades[0].status,'OPEN');
});
test('short paper entry checks executable bids without depending on opposite-side ask size',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 s.market.quote=async symbol=>({symbol,bid:99.99,ask:100,bidQty:1,askQty:.001,time:s.clock()});
 const result=await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'SHORT',symbol:'SOLUSDT',allocationPct:.04,sl:105,tp:90,method:'AI',reason:'Resistance',invalidation:'Break'});
 assert.equal(result.status,200);
});
test('a funding rollback does not allow later detached trades to debit balance without an idempotence marker',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1500}],complete:true,through:s.clock()});await s.rt.tick();await s.rt.close();
 const ledger=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')),w=ledger.wallets[0],second=structuredClone(w.trades[0]);second.id='SECOND-CLOSED';w.trades.push(second);w.balance=100+w.trades[0].pnl+second.pnl;const before=w.balance;
 await fs.writeFile(path.join(s.dir,'state.json'),JSON.stringify(ledger));s.advance(300001);
 const rt=await createRuntime({directory:s.dir,market:s.market,clock:s.clock});
 try{
  const event={fundingTime:start+1000,fundingRate:'.001',markPrice:'100'};
  s.market.funding=async trade=>{if(trade.id!=='SECOND-CLOSED')throw Error('First funding failed');return [event];};await rt.tick();
  let current=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')).wallets[0];assert.equal(current.balance,before);assert.equal(current.trades[1].fundingEvents.length,0);
  s.market.funding=async trade=>trade.id==='SECOND-CLOSED'?[event]:[];await rt.tick();await rt.tick();
  current=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')).wallets[0];assert.equal(current.trades[1].fundingEvents.length,1);assert.ok(Math.abs(current.balance-(100+current.trades.reduce((sum,t)=>sum+t.pnl,0)))<1e-9);
 }finally{await rt.close();}
});
test('multiple open trades preserve later settlement and the wallet error after earlier replay rollback',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});await s.rt.close();
 const ledger=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')),w=ledger.wallets[0],first=w.trades[0],second=structuredClone(first);second.id='SECOND-OPEN';w.trades.push(second);w.balance-=second.entryFee;
 await fs.writeFile(path.join(s.dir,'state.json'),JSON.stringify(ledger));s.advance(2000);
 const rt=await createRuntime({directory:s.dir,market:s.market,clock:s.clock});
 try{
  s.market.replay=async trade=>{if(trade.id!=='SECOND-OPEN')throw Error('First trade replay offline');return {events:[{a:10,p:'94',T:start+1500}],complete:true,through:s.clock()};};
  s.market.funding=async()=>[{fundingTime:start+1000,fundingRate:'.001',markPrice:'100'}];await rt.tick();
  let current=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')).wallets[0];
  assert.equal(current.trades[0].status,'OPEN');assert.equal(current.trades[1].status,'SL');assert.equal(current.trades[1].fundingEvents.length,1);assert.match(current.blocked,/First trade replay offline/);
  assert.ok(Math.abs(current.balance-(100-current.trades[0].entryFee+current.trades[1].pnl))<1e-9);
  const balance=current.balance;await rt.tick();current=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')).wallets[0];assert.equal(current.balance,balance);assert.equal(current.trades[1].fundingEvents.length,1);
  s.market.replay=async()=>({events:[],complete:true,through:s.clock()});s.market.funding=async()=>[];await rt.tick();current=JSON.parse(await fs.readFile(path.join(s.dir,'state.json'),'utf8')).wallets[0];assert.equal(current.blocked,null);assert.equal(current.balance,balance);
 }finally{await rt.close();}
});
test('slow monitoring does not queue repeated polls ahead of a waiting state reader',{timeout:35000},async t=>{
 const s=await setup(t);let calls=0,entered,release;
 const busy=new Promise(r=>entered=r),gate=new Promise(r=>release=r);
 s.market.quote=async symbol=>{calls++;if(calls>4&&calls<=8){if(calls===5)entered();await gate;}return {symbol,bid:99.99,ask:100,time:s.clock()};};
 await s.rt.start();
 try{
  await busy;await new Promise(r=>setTimeout(r,10500));
  const reading=fetch(s.base+'/api/state');await new Promise(r=>setTimeout(r,20));release();
  assert.equal((await reading).status,200);assert.equal(calls,8);
 }finally{release();}
});

test('authenticated early exit settles once, persists across restart and supports review/funding reconciliation',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 const entered=await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 const body={frame:'15m',tradeId:entered.body.tradeId,managementId:'close-once',action:'CLOSE',reason:'Momentum failed.'};
 assert.equal((await post(s,'/api/manage',body,'wrong')).status,401);
 assert.equal((await post(s,'/api/manage',body)).status,200);
 let state=await (await fetch(s.base+'/api/state')).json(),w=state.wallets[0],balance=w.balance;assert.equal(w.trades[0].status,'EARLY_EXIT');assert.equal(w.metrics.closedCount,1);assert.ok(Math.abs(balance-(100+w.trades[0].pnl))<1e-9);
 assert.equal((await post(s,'/api/manage',body)).status,200);assert.equal((await (await fetch(s.base+'/api/state')).json()).wallets[0].balance,balance);
 assert.equal((await post(s,'/api/review',{frame:'15m',tradeId:body.tradeId,lesson:'Observed momentum exit; no cause inferred.'})).status,200);
 s.market.funding=async()=>[{fundingTime:start+1000,fundingRate:'.001',markPrice:'100'}];s.advance(300001);await s.rt.tick();await s.rt.tick();
 state=await (await fetch(s.base+'/api/state')).json();w=state.wallets[0];assert.equal(w.trades[0].fundingEvents.length,1);assert.ok(w.balance<balance);await s.rt.close();
 const rt=await createRuntime({directory:s.dir,market:s.market,clock:s.clock});await rt.listen(0);try{const saved=await (await fetch('http://127.0.0.1:'+rt.port+'/api/state')).json();assert.equal(saved.wallets[0].trades[0].managementEvents.length,1);assert.equal(saved.wallets[0].trades[0].status,'EARLY_EXIT');}finally{await rt.close();}
});
test('management cannot evade an existing stop and cannot edit with incomplete replay',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 const entered=await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'AI',reason:'Support',invalidation:'Break'});s.advance(2000);
 const body={frame:'15m',tradeId:entered.body.tradeId,managementId:'move',action:'UPDATE_LEVELS',sl:90,reason:'Reassess support.'};
 s.market.replay=async()=>({events:[],complete:false,through:start+1000});assert.equal((await post(s,'/api/manage',body)).status,422);
 let w=(await (await fetch(s.base+'/api/state')).json()).wallets[0];assert.equal(w.trades[0].sl,95);assert.equal(w.trades[0].managementEvents,undefined);
 s.market.replay=async()=>({events:[{a:10,p:'94',T:start+1000}],complete:true,through:s.clock()});const result=await post(s,'/api/manage',body);assert.equal(result.status,200);assert.equal(result.body.preempted,true);
 w=(await (await fetch(s.base+'/api/state')).json()).wallets[0];assert.equal(w.trades[0].status,'SL');assert.equal(w.trades[0].sl,95);
});
test('level updates are audited without changing entry size and funding failures roll back edits',async t=>{
 const s=await setup(t),c=(await post(s,'/api/context',{frame:'15m'})).body;
 const entered=await post(s,'/api/decision',{contextId:c.id,frame:'15m',action:'SHORT',symbol:'SOLUSDT',allocationPct:.04,sl:105,tp:90,method:'AI',reason:'Resistance',invalidation:'Break'});s.advance(2000);
 const body={frame:'15m',tradeId:entered.body.tradeId,managementId:'level-1',action:'UPDATE_LEVELS',sl:103,tp:92,reason:'Resistance now lower.'};
 s.market.funding=async()=>{throw Error('Funding offline');};assert.equal((await post(s,'/api/manage',body)).status,422);
 let w=(await (await fetch(s.base+'/api/state')).json()).wallets[0];assert.equal(w.trades[0].sl,105);const qty=w.trades[0].qty;
 s.market.funding=async()=>[];assert.equal((await post(s,'/api/manage',body)).status,200);w=(await (await fetch(s.base+'/api/state')).json()).wallets[0];assert.equal(w.trades[0].sl,103);assert.equal(w.trades[0].tp,92);assert.equal(w.trades[0].qty,qty);assert.equal(w.trades[0].managementEvents[0].before.sl,105);
});
