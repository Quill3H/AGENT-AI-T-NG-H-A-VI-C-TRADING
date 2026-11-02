import {FRAMES,SYMBOLS} from './engine.mjs';
const ROOT='https://www.okx.com';
const positive=n=>Number.isFinite(n)&&n>0;
const wireTime=v=>typeof v==='string'&&/^\d+$/.test(v)&&Number.isSafeInteger(Number(v))&&Number(v)>0;
export class OkxMarket {
 constructor({fetcher=fetch,clock=Date.now,pause=ms=>new Promise(r=>setTimeout(r,ms)),allowEstimatedFunding=false}={}){
  this.venue='OKX';this.fetcher=fetcher;this.clock=clock;this.pause=pause;this.allowEstimatedFunding=allowEstimatedFunding;
  this.queue=Promise.resolve();this.lastRequest=0;this.blockedUntil=0;this.instruments=new Map();this.fundingCache=new Map();this.replayCache=new Map();
 }
 instId(symbol){if(!SYMBOLS.includes(symbol))throw Error('Unknown OKX symbol');return symbol.replace('USDT','-USDT-SWAP');}
 async get(endpoint,params={}){
  const request=async()=>{
   if(this.clock()<this.blockedUntil)throw Error('OKX public API cooldown; wait until '+this.blockedUntil);
   await this.pause(Math.max(0,250-(this.clock()-this.lastRequest)));this.lastRequest=this.clock();
   const r=await this.fetcher(ROOT+endpoint+'?'+new URLSearchParams(params),{signal:AbortSignal.timeout(15000)});
   if(!r.ok){if([418,429].includes(r.status))this.blockedUntil=this.clock()+Math.max(60000,(Number(r.headers?.get('retry-after'))||0)*1000);throw Error('OKX HTTP '+r.status+': '+endpoint);}
   const body=await r.json();if(body.code!=='0'||!Array.isArray(body.data))throw Error('OKX API '+String(body.code)+': '+endpoint);return body.data;
  };
  const result=this.queue.then(request);this.queue=result.catch(()=>{});return result;
 }
 async instrument(symbol){
  const cached=this.instruments.get(symbol);if(cached&&this.clock()-cached.time<3600000)return cached.value;
  const rows=await this.get('/api/v5/public/instruments',{instType:'SWAP',instId:this.instId(symbol)}),s=rows[0];
  if(!s||s.instId!==this.instId(symbol)||s.state!=='live'||s.ctType!=='linear'||s.settleCcy!=='USDT'||s.ctValCcy!==symbol.replace('USDT',''))throw Error('Invalid OKX linear USDT instrument');
  const unit=Number(s.ctVal)*Number(s.ctMult||1);
  if(![unit,Number(s.lotSz),Number(s.minSz),Number(s.maxMktSz),Number(s.tickSz)].every(positive))throw Error('Invalid OKX contract specifications');
  const value={...s,unit};this.instruments.set(symbol,{time:this.clock(),value});return value;
 }
 async rules(symbol){
  const s=await this.instrument(symbol);
  return {venue:'OKX',instId:s.instId,quantityUnit:'BASE_COIN',contractSize:s.unit,tickSize:Number(s.tickSz),stepSize:Number(s.lotSz)*s.unit,minQty:Number(s.minSz)*s.unit,maxQty:Number(s.maxMktSz)*s.unit,minNotional:0,notionalRule:'CONTRACT_LOT_ONLY'};
 }
 async quote(symbol){
  const s=await this.instrument(symbol),rows=await this.get('/api/v5/market/ticker',{instId:s.instId}),q=rows[0];
  const result={venue:'OKX',instId:s.instId,symbol,bid:Number(q?.bidPx),ask:Number(q?.askPx),bidQty:Number(q?.bidSz)*s.unit,askQty:Number(q?.askSz)*s.unit,time:Number(q?.ts),fetchedAt:this.clock(),source:ROOT+'/api/v5/market/ticker?instId='+s.instId};
  if(![result.bid,result.ask,result.bidQty,result.askQty].every(positive)||result.ask<result.bid||!Number.isSafeInteger(result.time)||result.time>this.clock()||this.clock()-result.time>15000)throw Error('Stale/invalid OKX quote');return result;
 }
 async capture(frame,cutoff){
  const interval=FRAMES[frame];if(!interval)throw Error('Invalid OKX frame');
  const server=await this.get('/api/v5/public/time');if(!Number.isSafeInteger(Number(server[0]?.ts))||Math.abs(Number(server[0]?.ts)-this.clock())>10000)throw Error('Clock differs from OKX');
  const symbols=[];
  for(const symbol of SYMBOLS){
   const instId=this.instId(symbol),raw=await this.get('/api/v5/market/candles',{instId,bar:{'15m':'15m','1h':'1H','4h':'4H'}[frame],limit:'81',after:String(cutoff)});
   const candles=raw.filter(b=>b[8]==='1'&&Number(b[0])+interval<=cutoff).map(b=>({openTime:Number(b[0]),closeTime:Number(b[0])+interval-1,o:Number(b[1]),h:Number(b[2]),l:Number(b[3]),c:Number(b[4]),v:Number(b[6]),quoteVolume:Number(b[7])})).sort((a,b)=>a.openTime-b.openTime);
   if(candles.length<40||candles.at(-1).closeTime!==cutoff-1)throw Error('Missing OKX closed candle coverage '+symbol);
   for(let i=0;i<candles.length;i++){
    const b=candles[i];if(!['o','h','l','c'].every(k=>positive(b[k]))||![b.v,b.quoteVolume].every(v=>Number.isFinite(v)&&v>=0)||b.h<Math.max(b.o,b.c,b.l)||b.l>Math.min(b.o,b.c,b.h)||b.openTime%interval!==0||(i&&b.openTime-candles[i-1].openTime!==interval))throw Error('Malformed/gapped OKX candles');
   }
   const funding=await this.get('/api/v5/public/funding-rate',{instId});
   symbols.push({symbol,venue:'OKX',instId,quote:await this.quote(symbol),rules:await this.rules(symbol),premium:{...funding[0],fundingRateIsForecast:true},candles,source:ROOT+'/api/v5/market/candles?instId='+instId});
  }
  // Quotes are refreshed after slow multi-symbol capture to retain the original stale gates.
  for(const s of symbols)s.quote=await this.quote(s.symbol);
  return {venue:'OKX',frame,serverTime:Number(server[0].ts),closedThrough:cutoff-1,capturedAt:this.clock(),symbols};
 }
 requireTrade(trade){if(trade.venue!=='OKX'||trade.instId!==this.instId(trade.symbol))throw Error('OKX venue mismatch; refuse foreign position');}
 async replay(trade,cutoff){
  this.requireTrade(trade);
  const from=trade.replayTime??trade.openedAt;
  if(cutoff<from||cutoff-from>89*86400000)throw Error('OKX replay outside retained public history');
  if(cutoff===from)return {events:[],complete:true,through:cutoff};
  const target=Math.min(cutoff,from+60000),cache=this.replayCache.get(trade.symbol);
  let rows;
  if(cache&&cache.from<=from&&cache.through>=target)rows=cache.rows;
  else{
   const found=new Map();let after=String(target+1),type='2',covered=false,previousOldest=null;
   for(let page=0;page<128;page++){
    const batch=await this.get('/api/v5/market/history-trades',{instId:trade.instId,type,after,limit:'100'});
    if(!batch.length)throw Error('OKX replay cannot prove coverage');
    for(const r of batch){if(typeof r.tradeId!=='string'||!/^\d+$/.test(r.tradeId)||!wireTime(r.ts)||!positive(Number(r.px)))throw Error('Malformed OKX public trade');found.set(r.tradeId,r);}
    const sorted=[...batch].sort((a,b)=>BigInt(a.tradeId)<BigInt(b.tradeId)?-1:BigInt(a.tradeId)>BigInt(b.tradeId)?1:0),oldest=sorted[0];
    if(previousOldest!==null&&BigInt(oldest.tradeId)>=BigInt(previousOldest))throw Error('OKX replay pagination stalled');previousOldest=oldest.tradeId;
    if(Number(oldest.ts)<=from){covered=true;break;}
    after=oldest.tradeId;type='1';
   }
   if(!covered)throw Error('OKX one-minute replay exceeded bounded page coverage');
   rows=[...found.values()];this.replayCache.set(trade.symbol,{from,through:target,rows});
  }
  const selected=rows.filter(r=>Number(r.ts)>from&&Number(r.ts)<=target).sort((a,b)=>BigInt(a.tradeId)<BigInt(b.tradeId)?-1:BigInt(a.tradeId)>BigInt(b.tradeId)?1:0);
  let lastTime=from,sequence=trade.lastAggId??0;
  const events=selected.map(r=>{const time=Number(r.ts);if(time<lastTime)throw Error('Noncausal OKX trade ID order');lastTime=time;return {a:++sequence,venueId:r.tradeId,p:r.px,T:time,source:ROOT+'/api/v5/market/history-trades',venue:'OKX'};});
  return {events,complete:target===cutoff,through:target};
 }
 async funding(trade,cutoff){
  this.requireTrade(trade);const until=Math.min(cutoff,trade.closedAt??cutoff),from=trade.openedAt;
  if(until-from>89*86400000)throw Error('OKX funding outside public retention');
  const cached=this.fundingCache.get(trade.symbol);
  let rates;
  if(cached&&cached.from<=from&&cached.until>=until&&this.clock()-cached.checkedAt<60000)rates=cached.rows;
  else{
   rates=[];let after=String(until+1),complete=false;
   for(let page=0;page<24;page++){
    const rows=await this.get('/api/v5/public/funding-rate-history',{instId:trade.instId,after,limit:'400'});
    for(const r of rows)if(!wireTime(r.fundingTime))throw Error('Invalid OKX funding timestamp');rates.push(...rows);
    if(!rows.length||rows.length<400||Math.min(...rows.map(r=>Number(r.fundingTime)))<=from){complete=true;break;}
    const next=String(Math.min(...rows.map(r=>Number(r.fundingTime))));if(BigInt(next)>=BigInt(after))throw Error('OKX funding pagination stalled');after=next;
   }
   if(!complete)throw Error('OKX funding history incomplete');
   this.fundingCache.set(trade.symbol,{from,until,checkedAt:this.clock(),rows:rates});
  }
  const events=[];
  for(const r of rates.filter(r=>Number(r.fundingTime)>from&&Number(r.fundingTime)<=until)){
   const time=Number(r.fundingTime);if(trade.fundingEvents.some(e=>e.time===time))continue;
   if(!this.allowEstimatedFunding)throw Error('OKX funding mark estimate not approved');
   if(typeof r.realizedRate!=='string'||!r.realizedRate.trim()||!Number.isFinite(Number(r.realizedRate)))throw Error('Missing realized OKX funding rate');
   const bars=await this.get('/api/v5/market/history-mark-price-candles',{instId:trade.instId,bar:'1m',after:String(time),limit:'1'}),bar=bars.find(b=>Number(b[0])===time-60000&&b[5]==='1');
   if(!bar||!positive(Number(bar[4])))throw Error('Missing pre-event OKX mark candle');
   events.push({venue:'OKX',fundingTime:time,fundingRate:r.realizedRate,markPrice:bar[4],estimated:true,priceMethod:'MARK_1M_PRE_EVENT_PROXY',priceWindow:{openTime:time-60000,closeTime:time-1},source:ROOT+'/api/v5/public/funding-rate-history',priceSource:ROOT+'/api/v5/market/history-mark-price-candles'});
  }
  return events.sort((a,b)=>a.fundingTime-b.fundingTime);
 }
}
