import {createHash} from 'node:crypto';
const intervals={'15m':900000,'1h':3600000,'4h':14400000};
const pick=(value,keys)=>Object.fromEntries(keys.filter(k=>value[k]!==undefined).map(k=>[k,value[k]]));
export function packContext(c,sourceText){
 const interval=intervals[c.frame];
 if(!interval||c.market?.frame!==c.frame||c.market.closedThrough!==c.cycleAt-1||!c.market.symbols?.length)throw Error('Invalid frame or candle coverage');
 const symbols=c.market.symbols.map(s=>{
  const bars=s.candles;
  if(!Array.isArray(bars)||bars.length<40||bars.at(-1).closeTime!==c.cycleAt-1)throw Error('Need40 complete candles');
  bars.forEach((b,i)=>{if(!['o','h','l','c','v'].every(k=>Number.isFinite(b[k]))||!Number.isSafeInteger(b.openTime)||b.closeTime!==b.openTime+interval-1||b.closeTime>=c.cycleAt||(i&&b.openTime!==bars[i-1].openTime+interval))throw Error('Malformed, future or gapped candle');});
  const mean=n=>bars.length<n?null:bars.slice(-n).reduce((sum,b)=>sum+b.c,0)/n;
  const ranges=bars.slice(1).map((b,i)=>Math.max(b.h-b.l,Math.abs(b.h-bars[i].c),Math.abs(b.l-bars[i].c)));
  return {symbol:s.symbol,quote:s.quote,rules:s.rules,premium:s.premium,source:s.source,firstOpenTime:bars.at(-40).openTime,rows:bars.slice(-40).map(b=>[b.o,b.h,b.l,b.c,b.v]),indicators:{sma20:mean(20),sma50:mean(50),atr14:ranges.slice(-14).reduce((a,b)=>a+b,0)/14}};
 });
 const w=c.wallet,unreviewed=w.trades.filter(t=>['TP','SL','EARLY_EXIT'].includes(t.status)&&!w.reviews.some(r=>r.tradeId===t.id));
 return {...pick(c,['id','frame','cycleAt','capturedAt','expiresAt','bootstrap','policy']),source:{path:c.snapshotPath,sha256:createHash('sha256').update(sourceText).digest('hex'),bytes:Buffer.byteLength(sourceText)},
  market:{...pick(c.market,['venue','serverTime','closedThrough','capturedAt']),intervalMs:interval,columns:['open','high','low','close','volume'],timeRule:'row i openTime=firstOpenTime+i*intervalMs; closeTime=openTime+intervalMs-1',indicatorRule:'SMA on available source closes; ATR14 is simple mean of last14 true ranges, not Wilder smoothing; descriptive only',symbols},
  wallet:{...pick(w,['frame','balance','initial','enabled','blocked']),open:w.trades.filter(t=>['OPEN','UNVERIFIED'].includes(t.status)).map(t=>pick(t,['status','id','symbol','side','entry','qty','currentPlannedLoss','managementEvents','notional','leverage','initialMargin','allocationPct','plannedLoss','riskPct','tp','sl','openedAt','replayTime','replayBehind'])),unreviewedTradeIds:unreviewed.map(t=>t.id),recentLessons:w.reviews.slice(-3)},
  lowerFrame:c.lowerFrame?{frame:c.lowerFrame.frame,decisions:c.lowerFrame.decisions.map(d=>pick(d,['cycleAt','action','symbol','allocationPct','riskPct','sl','tp','method','tradeId'])),closed:c.lowerFrame.closed.map(t=>pick(t,['id','symbol','side','status','pnl','closedAt']))}:null};
}
export function nextFrame(state){
 const now=state.serverTime;if(!Number.isFinite(now))throw Error('Missing server clock');
 if(!state.worker?.healthy)return {frame:null,status:'WORKER_ERROR',error:state.worker?.error??'Worker not healthy'};
 const skipped=[];let nextBoundary=Infinity;
 for(const [frame,ms] of Object.entries(intervals)){
  const w=state.wallets.find(w=>w.frame===frame),cycleAt=Math.floor(now/ms)*ms;nextBoundary=Math.min(nextBoundary,cycleAt+ms);
  let reason=null;
  if(!w||!w.enabled)reason='DISABLED';else if(w.blocked||!(w.balance>0))reason=w.blocked??'NONPOSITIVE_BALANCE';
  else if(w.decisions.some(d=>d.cycleAt>=cycleAt))reason='ALREADY_DECIDED';else if(now-cycleAt>600000)reason='MISSED_CYCLE';
  if(reason){skipped.push({frame,cycleAt,reason});continue;}
  return {frame,cycleAt,status:'DUE',skipped};
 }
 return {frame:null,status:'NO_DUE_CYCLES',skipped,nextBoundary,waitMs:nextBoundary-now};
}
