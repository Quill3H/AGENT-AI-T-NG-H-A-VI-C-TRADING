import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {runCycle} from './gemini-paper.mjs';
import {newState,acceptDecision,FRAMES} from '../paper-bot-studio/engine.mjs';

const start=Date.UTC(2026,10,1,12),rules={stepSize:.001,minQty:.001,maxQty:10000,minNotional:5,tickSize:.01};
const entry={action:'LONG',symbol:'SOLUSDT',allocationPct:.04,sl:95,tp:110,method:'Fixture',reason:'1. Observed support.\n2. Entry at support.\n3. Stop below support.',invalidation:'Support fails'};
async function fixture(t,{oldTrade=false,higher=false}={}){
 const testRoot=path.join(path.dirname(fileURLToPath(import.meta.url)),'.test-data');await fs.mkdir(testRoot,{recursive:true});
 const directory=await fs.mkdtemp(path.join(testRoot,'gemini-integration-'));
 t.after(()=>{if(path.dirname(directory)!==testRoot)throw Error('Unexpected cleanup path');return fs.rm(directory,{recursive:true,force:true});});
 let now=start+1000;
 const state=newState(start-900000);
 state.wallets[1].enabled=higher;state.wallets[2].enabled=false;
 if(oldTrade){
  const c={id:'old-context',frame:'15m',cycleAt:start-900000,capturedAt:start-900000,expiresAt:start-660000};
  acceptDecision(state,{...entry,contextId:c.id,frame:'15m'},c,{symbol:'SOLUSDT',bid:99.99,ask:100,time:c.capturedAt},rules,c.capturedAt);
 }
 await fs.writeFile(path.join(directory,'state.json'),JSON.stringify(state));
 const market={
  async quote(symbol){return {symbol,bid:99.99,ask:100,time:now};},async rules(){return rules;},
  async replay(){return {events:[],complete:true,through:now};},async funding(){return [];},
  async capture(frame,cutoff){const ms=FRAMES[frame];return {frame,serverTime:now,closedThrough:cutoff-1,capturedAt:now,symbols:[{symbol:'SOLUSDT',quote:await this.quote('SOLUSDT'),rules,premium:{},candles:Array.from({length:80},(_,i)=>({openTime:cutoff-(80-i)*ms,closeTime:cutoff-(79-i)*ms-1,o:100,h:102,l:98,c:100,v:1000}))}]};}
 };
 return {directory,market,clock:()=>now,advance:n=>now+=n,read:async()=>JSON.parse(await fs.readFile(path.join(directory,'state.json'),'utf8'))};
}
const result=value=>({value,modelVersion:'fixture-model'});
test('management then entry persists audit, balance and original context',async t=>{
 const f=await fixture(t,{oldTrade:true});
 await runCycle({...f,analyze:async p=>result({management:[{tradeId:p.context.wallet.open[0].id,action:'UPDATE_LEVELS',sl:96,reason:'Observed support moved higher.'}],entry})});
 const w=(await f.read()).wallets[0];
 assert.equal(w.trades.length,2);assert.equal(w.trades[0].sl,96);assert.equal(w.trades[0].managementEvents.length,1);
 assert.equal(w.decisions.at(-1).cycleAt,start);assert.equal(w.decisions.at(-1).modelVersion,'fixture-model');
 assert.equal(w.trades[1].contextId,w.decisions.at(-1).contextId);assert.ok(w.balance<100);
});
test('API failure after first frame preserves that entry across restart and retry',async t=>{
 const f=await fixture(t,{higher:true});let calls=0;
 await assert.rejects(runCycle({...f,analyze:async()=>{if(++calls===2)throw Error('Fixture API 429');return result({entry});}}),/429/);
 assert.equal((await f.read()).wallets[0].trades.length,1);
 await runCycle({...f,analyze:async p=>{assert.equal(p.context.frame,'1h');return result({entry});}});
 const s=await f.read();assert.equal(s.wallets[0].trades.length,1);assert.equal(s.wallets[1].trades.length,1);
});
test('partial management survives rejected entry and retry cannot repeat it',async t=>{
 const f=await fixture(t,{oldTrade:true});
 await assert.rejects(runCycle({...f,analyze:async p=>result({management:[{tradeId:p.context.wallet.open[0].id,action:'UPDATE_LEVELS',sl:96,reason:'Support moved higher.'}],entry:{...entry,tp:90}})}),/TP\/SL direction/);
 const before=await f.read();assert.equal(before.wallets[0].trades[0].managementEvents.length,1);assert.equal(before.wallets[0].trades.length,1);
 await assert.rejects(runCycle({...f,analyze:async()=>assert.fail('Retry must not call model or manage again')}),/manual reconciliation/);
 const after=await f.read();assert.equal(after.wallets[0].trades[0].managementEvents.length,1);assert.equal(after.wallets[0].balance,before.wallets[0].balance);
});
test('slow model output cannot renew expired original analysis',async t=>{
 const f=await fixture(t);
 await assert.rejects(runCycle({...f,analyze:async()=>{f.advance(240001);return result({entry});}}),/Expired or future context/);
 const s=await f.read();assert.equal(s.wallets[0].trades.length,0);assert.equal(s.wallets[0].balance,100);assert.equal(s.contexts.length,1);
});
test('application deadline rejects slow analysis before mutations and releases worker lock',async t=>{
 const f=await fixture(t);let elapsed=0;
 await assert.rejects(runCycle({...f,maxRunMs:1000,wallClock:()=>elapsed,analyze:async(_,options)=>{
  assert.equal(options.timeoutMs,1000);elapsed=1001;return result({entry});
 }}),/Application deadline/);
 assert.equal((await f.read()).wallets[0].trades.length,0);
 await assert.rejects(fs.access(path.join(f.directory,'worker.lock')),/ENOENT/);
 await runCycle({...f,analyze:async()=>result({entry})});
 assert.equal((await f.read()).wallets[0].trades.length,1);
});
test('bounded catch-up finishes incomplete replay before calling model',async t=>{
 const f=await fixture(t,{oldTrade:true});let replayCalls=0;
 f.market.replay=async()=>({events:[],complete:++replayCalls>1,through:f.clock()});
 await runCycle({...f,analyze:async()=>{assert.ok(replayCalls>=2);return result({entry});}});
 const w=(await f.read()).wallets[0];assert.equal(w.trades.length,2);assert.equal(w.trades[0].replayBehind,false);
});
test('genuine quote failure aborts without catch-up retry or model call',async t=>{
 const f=await fixture(t,{oldTrade:true});let quotes=0;
 f.market.quote=async()=>{quotes++;throw Error('Fixture quote unavailable');};
 await assert.rejects(runCycle({...f,analyze:async()=>assert.fail('Model must not run')}),/quote unavailable/);
 assert.equal(quotes,4);assert.equal((await f.read()).wallets[0].trades.length,1);
});
test('funding failure during incomplete replay is not retried as catch-up',async t=>{
 const f=await fixture(t,{oldTrade:true});let replays=0;
 f.market.replay=async()=>{replays++;return {events:[],complete:false,through:f.clock()};};
 f.market.funding=async()=>{throw Error('Fixture funding unavailable');};
 await assert.rejects(runCycle({...f,analyze:async()=>assert.fail('Model must not run')}),/funding unavailable/);
 assert.equal(replays,1);
});
test('persistent incomplete replay stops at bounded limit without new entry',async t=>{
 const f=await fixture(t,{oldTrade:true});let replays=0;
 f.market.replay=async()=>{replays++;return {events:[],complete:false,through:f.clock()};};
 await assert.rejects(runCycle({...f,analyze:async()=>assert.fail('Model must not run')}),/catch-up limit/);
 assert.equal(replays,16);const w=(await f.read()).wallets[0];assert.equal(w.trades.length,1);assert.equal(w.trades[0].replayBehind,true);
});
