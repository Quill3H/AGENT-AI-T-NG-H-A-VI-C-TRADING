export const SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT','HYPEUSDT'];
export const FRAMES={'15m':900000,'1h':3600000,'4h':14400000};
export const LEVERAGE=Object.freeze({BTCUSDT:15,ETHUSDT:10,SOLUSDT:7,HYPEUSDT:5});
export const FEE=.0005, SLIPPAGE=.0002;
const requireValue=(condition,message)=>{if(!condition)throw Error(message);};
const finite=(n)=>typeof n==='number'&&Number.isFinite(n);
export function newState(now=Date.now()){
 return {version:1,mode:'PAPER_ONLY',createdAt:now,updatedAt:now,wallets:Object.keys(FRAMES).map(frame=>({frame,initial:100,balance:100,enabled:true,trades:[],decisions:[],reviews:[],curve:[{time:now,value:100}]})),contexts:[],rejections:[],worker:{startedAt:now,lastTick:null,lastSuccess:null,error:null},quotes:{}};
}
export function cycleFor(frame,now){requireValue(FRAMES[frame]&&finite(now),'Invalid frame or time');return Math.floor(now/FRAMES[frame])*FRAMES[frame];}
export function acceptDecision(state,d,c,q,r,now){
 requireValue(d&&c&&d.contextId===c.id&&d.frame===c.frame,'Context mismatch');
 requireValue(finite(now)&&now>=c.capturedAt&&now<=c.expiresAt&&c.cycleAt<=c.capturedAt,'Expired or future context');
 const wallet=state.wallets.find(w=>w.frame===d.frame);requireValue(wallet,'Unknown wallet');
 requireValue(!wallet.decisions.some(x=>x.cycleAt===c.cycleAt),'Duplicate cycle');
 requireValue(['LONG','SHORT'].includes(d.action),'Mandatory entry requires LONG or SHORT; log technical failures as NOT_EXECUTED');
 for(const key of ['method','reason','invalidation'])requireValue(typeof d[key]==='string'&&d[key].trim().length>0&&d[key].length<=6000,'Missing or oversized '+key);
 const record={...d,cycleAt:c.cycleAt,decidedAt:now,capturedAt:c.capturedAt};
 requireValue(wallet.enabled&&!wallet.blocked,'Wallet blocked or paused');
 requireValue(!wallet.trades.some(t=>t.status==='UNVERIFIED'),'An unverified trade requires review');
 requireValue(SYMBOLS.includes(d.symbol),'Unknown symbol');
 requireValue(finite(d.allocationPct)&&d.allocationPct>=.03&&d.allocationPct<=.05,'Allocation must be 3–5% of booked balance');
 requireValue(d.riskPct===undefined&&d.riskBudgetPct===undefined,'Use allocationPct, not the previous SL-risk fields');
 requireValue(finite(wallet.balance)&&wallet.balance>0,'Nonpositive booked balance; new entries blocked');
 requireValue(q&&q.symbol===d.symbol&&finite(q.bid)&&finite(q.ask)&&q.bid>0&&q.ask>=q.bid&&finite(q.time)&&now-q.time>=0&&now-q.time<=15000,'Stale or invalid quote');
 requireValue(r&&['tickSize','stepSize','minQty','maxQty','minNotional'].every(k=>finite(r[k])&&r[k]>0),'Invalid exchange rules');
 const sign=d.action==='LONG'?1:-1,entry=(sign>0?q.ask:q.bid)*(1+sign*SLIPPAGE);
 requireValue(finite(d.sl)&&finite(d.tp)&&d.sl>0&&d.tp>0&&sign*(entry-d.sl)>0&&sign*(d.tp-entry)>0,'Invalid TP/SL direction');
 for(const price of [d.sl,d.tp])requireValue(Math.abs(price/r.tickSize-Math.round(price/r.tickSize))<.000001,'TP/SL must match tick size');
 const stopExit=d.sl*(1-sign*SLIPPAGE),stopCost=sign*(entry-stopExit)+FEE*(entry+stopExit);
 const leverage=LEVERAGE[d.symbol];
 const qty=Number((Math.floor((wallet.balance*d.allocationPct*leverage/entry+1e-12)/r.stepSize)*r.stepSize).toPrecision(12));
 requireValue(qty>=r.minQty&&qty<=r.maxQty,'Quantity outside Binance limits');
 const notional=entry*qty,entryFee=notional*FEE,plannedLoss=qty*stopCost,initialMargin=notional/leverage;
 requireValue(initialMargin+entryFee<=wallet.balance+1e-9,'Insufficient per-trade capital for initial margin plus entry fee');
 requireValue(notional>=r.minNotional,'Below minimum notional');
 requireValue(initialMargin/wallet.balance>=.03-1e-10&&initialMargin/wallet.balance<=d.allocationPct+1e-10,'Rounded allocation outside 3–5% per-trade limit');
 const freshQuotes=Object.fromEntries(Object.entries(state.quotes??{}).filter(([,v])=>now-v.time>=0&&now-v.time<=30000));freshQuotes[q.symbol]=q;
 const trade={id:`AI-${d.frame}-${c.cycleAt}`,frame:d.frame,symbol:d.symbol,side:d.action,entry,sl:d.sl,tp:d.tp,qty,notional,entryFee,plannedLoss,riskPct:plannedLoss/wallet.balance,allocationRequested:d.allocationPct,allocationPct:initialMargin/wallet.balance,leverage,initialMargin,riskPolicy:'MARGIN_ALLOCATION_PER_TRADE_CUMULATIVE',riskBasis:'BOOKED_BALANCE_BEFORE_ENTRY',balanceAtEntry:wallet.balance,equityAtEntry:walletMetrics(wallet,freshQuotes).equity,openedAt:now,status:'OPEN',method:d.method,reason:d.reason,invalidation:d.invalidation,contextId:c.id,quote:{...q},rules:{...r},lastAggId:null,replayTime:now,funding:0,fundingEvents:[]};
 wallet.balance-=entryFee;wallet.trades.push(trade);record.tradeId=trade.id;wallet.decisions.push(record);return record;
}
function settleTrade(wallet,trade,exit,status,time,triggerPrice,bookedAt){
 const sign=trade.side==='LONG'?1:-1;
 trade.status=status;trade.closedAt=time;trade.triggerPrice=triggerPrice;trade.exit=exit;trade.exitFee=exit*trade.qty*FEE;
 const gross=trade.qty*sign*(exit-trade.entry);
 trade.pnl=gross-trade.entryFee-trade.exitFee+trade.funding;trade.r=trade.pnl/trade.plannedLoss;wallet.balance+=gross-trade.exitFee;
 wallet.curve.push({time:bookedAt,eventTime:time,value:wallet.balance,tradeId:trade.id});
}
export function manageTrade(wallet,trade,body,q,r,now){
 requireValue(typeof body.managementId==='string'&&body.managementId.length>0&&body.managementId.length<=128,'Missing managementId');
 const duplicate=trade.managementEvents?.find(e=>e.id===body.managementId);if(duplicate)return duplicate;
 requireValue(trade.status==='OPEN'&&!trade.replayBehind,'Trade is not verified open');
 requireValue(['UPDATE_LEVELS','CLOSE'].includes(body.action),'Invalid management action');
 requireValue(typeof body.reason==='string'&&body.reason.trim().length>0&&body.reason.length<=6000,'Missing management reason');
 requireValue(q&&q.symbol===trade.symbol&&finite(q.bid)&&finite(q.ask)&&q.bid>0&&q.ask>=q.bid&&finite(q.time)&&now>=q.time&&now-q.time<=15000&&q.time>trade.openedAt&&trade.replayTime===q.time,'Fresh quote and complete replay required');
 const sign=trade.side==='LONG'?1:-1,price=sign>0?q.bid:q.ask;
 const event={id:body.managementId,action:body.action,time:q.time,recordedAt:now,reason:body.reason,before:{tp:trade.tp,sl:trade.sl},quote:{...q}};
 if(body.action==='UPDATE_LEVELS'){
  const tp=body.tp??trade.tp,sl=body.sl??trade.sl;
  requireValue(body.tp!==undefined||body.sl!==undefined,'Provide TP or SL');
  requireValue(r&&finite(r.tickSize)&&r.tickSize>0,'Invalid tick size');
  for(const p of [tp,sl])requireValue(finite(p)&&p>0&&Math.abs(p/r.tickSize-Math.round(p/r.tickSize))<.000001,'Levels must match tick size');
  requireValue(sign*(price-sl)>0&&sign*(tp-price)>0,'Levels must bracket current executable price; use CLOSE for immediate exit');
  requireValue(tp!==trade.tp||sl!==trade.sl,'Levels unchanged');
  const stopExit=sl*(1-sign*SLIPPAGE),planned=Math.max(0,trade.qty*(sign*(trade.entry-stopExit)+FEE*(trade.entry+stopExit)));
  event.after={tp,sl};event.plannedLossBefore=trade.currentPlannedLoss??trade.plannedLoss;event.plannedLossAfter=planned;
  trade.tp=tp;trade.sl=sl;trade.currentPlannedLoss=planned;
 }else{
  const available=sign>0?q.bidQty:q.askQty;
  requireValue(available===undefined||finite(available)&&available>=trade.qty,'Insufficient executable-side top-of-book size for early exit');
  settleTrade(wallet,trade,price*(1-sign*SLIPPAGE),'EARLY_EXIT',q.time,price,now);event.exit=trade.exit;
 }
 (trade.managementEvents??=[]).push(event);return event;
}
export function replayTrades(wallet,trade,events,bookedAt){
 if(trade.status!=='OPEN')return;
 const ordered=[...events].sort((a,b)=>a.a-b.a);
 for(const e of ordered){
  const price=Number(e.p),time=e.T;
  requireValue(Number.isSafeInteger(e.a)&&finite(price)&&price>0&&Number.isSafeInteger(time),'Malformed aggregate trade');
  if(time<=trade.openedAt||trade.lastAggId!==null&&e.a<=trade.lastAggId)continue;
  if(trade.lastAggId!==null&&e.a!==trade.lastAggId+1)throw Error('Gap in aggregate trade replay');
  trade.lastAggId=e.a;trade.replayTime=time;
  const changes=(trade.managementEvents??[]).filter(e=>e.action==='UPDATE_LEVELS');
  let levels=changes[0]?.before??trade;
  for(const change of changes)if(time>change.time)levels=change.after;
  const sign=trade.side==='LONG'?1:-1,tp=sign*(price-levels.tp)>=0,sl=sign*(price-levels.sl)<=0;
  if(!tp&&!sl)continue;
  const base=tp?levels.tp:price;
  settleTrade(wallet,trade,base*(1-sign*SLIPPAGE),tp?'TP':'SL',time,price,bookedAt??time);return;
 }
}
export function applyFunding(wallet,trade,events,through=Date.now(),bookedAt=through){
 const until=Math.min(through,trade.closedAt??through);
 for(const e of [...events].sort((a,b)=>a.fundingTime-b.fundingTime)){
  const time=e.fundingTime,rate=Number(e.fundingRate),price=Number(e.markPrice);
  requireValue(Number.isSafeInteger(time)&&finite(rate)&&finite(price)&&price>0,'Invalid funding event');
  if(time<=trade.openedAt||time>until||trade.fundingEvents.some(x=>x.time===time))continue;
  const amount=-(trade.side==='LONG'?1:-1)*trade.qty*price*rate;
  trade.fundingEvents.push({time,rate,price,amount});trade.funding+=amount;wallet.balance+=amount;
  if(trade.pnl!==undefined){trade.pnl+=amount;trade.r=trade.pnl/trade.plannedLoss;wallet.curve.push({time:bookedAt,eventTime:time,value:wallet.balance,reason:'Funding reconciliation',tradeId:trade.id});}
 }
}
export function walletMetrics(wallet,quote){
 const open=wallet.trades.filter(t=>t.status==='OPEN'||t.status==='UNVERIFIED');
 let equity=wallet.balance,priced=true;
 for(const t of open){
  const q=quote?.[t.symbol]??quote;
  if(!q||!finite(q.bid)||!finite(q.ask)){priced=false;continue;}
  const sign=t.side==='LONG'?1:-1,exit=(sign>0?q.bid:q.ask)*(1-sign*SLIPPAGE);
  equity+=t.qty*sign*(exit-t.entry)-t.qty*exit*FEE;
 }
 const closed=wallet.trades.filter(t=>['TP','SL','EARLY_EXIT'].includes(t.status)),wins=closed.filter(t=>t.pnl>0).length;
 const openRisk=open.reduce((s,t)=>s+(t.currentPlannedLoss??t.plannedLoss),0),notional=open.reduce((s,t)=>s+t.notional,0);
 return {equity:priced?equity:null,balance:wallet.balance,openCount:open.length,openRisk,openRiskPct:wallet.balance>0?openRisk/wallet.balance:null,notional,grossExposureMultiple:wallet.balance>0?notional/wallet.balance:null,closedCount:closed.length,wins,winRate:closed.length?wins/closed.length:null,netRealized:closed.reduce((s,t)=>s+t.pnl,0)};
}
