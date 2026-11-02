import {SYMBOLS,FRAMES} from './engine.mjs';
const ROOT='https://fapi.binance.com';
export class BinanceMarket {
 constructor(){this.exchange=null;this.fundingCache=new Map();}
 async get(endpoint,params={}){
  const url=ROOT+endpoint+'?'+new URLSearchParams(params);
  const response=await fetch(url,{signal:AbortSignal.timeout(15000)});
  if(!response.ok)throw Error(`Binance HTTP ${response.status}: ${endpoint}`);
  return response.json();
 }
 async quote(symbol){
  const q=await this.get('/fapi/v1/ticker/bookTicker',{symbol});
  return {symbol,bid:Number(q.bidPrice),ask:Number(q.askPrice),bidQty:Number(q.bidQty),askQty:Number(q.askQty),time:Number(q.time),fetchedAt:Date.now(),source:ROOT+'/fapi/v1/ticker/bookTicker'};
 }
 async rules(symbol){
  if(!this.exchange||Date.now()-this.exchange.time>3600000)this.exchange={time:Date.now(),data:await this.get('/fapi/v1/exchangeInfo')};
  const s=this.exchange.data.symbols.find(x=>x.symbol===symbol);
  if(!s||s.status!=='TRADING'||s.contractType!=='PERPETUAL')throw Error('Symbol not trading perpetual');
  const f=Object.fromEntries(s.filters.map(x=>[x.filterType,x]));
  const lot=f.MARKET_LOT_SIZE??f.LOT_SIZE;
  return {tickSize:Number(f.PRICE_FILTER.tickSize),stepSize:Number(lot.stepSize),minQty:Number(lot.minQty),maxQty:Number(lot.maxQty),minNotional:Number(f.MIN_NOTIONAL.notional)};
 }
 async capture(frame,cutoff){
  const server=await this.get('/fapi/v1/time');
  if(Math.abs(server.serverTime-Date.now())>10000)throw Error('System clock differs from Binance by >10 seconds');
  const symbols=await Promise.all(SYMBOLS.map(async symbol=>{
   const [raw,quote,rules,premium]=await Promise.all([this.get('/fapi/v1/klines',{symbol,interval:frame,limit:81,endTime:cutoff-1}),this.quote(symbol),this.rules(symbol),this.get('/fapi/v1/premiumIndex',{symbol})]);
   const candles=raw.filter(b=>b[6]<cutoff).map(b=>({openTime:b[0],closeTime:b[6],o:Number(b[1]),h:Number(b[2]),l:Number(b[3]),c:Number(b[4]),v:Number(b[5]),quoteVolume:Number(b[7]),trades:b[8]}));
   if(candles.length<40||candles.at(-1).closeTime!==cutoff-1)throw Error('Missing current closed candles '+symbol+' '+frame);
   for(let i=1;i<candles.length;i++)if(candles[i].openTime-candles[i-1].openTime!==FRAMES[frame])throw Error('Candle gap '+symbol);
   return {symbol,quote,rules,premium,candles,source:ROOT+'/fapi/v1/klines?symbol='+symbol+'&interval='+frame+'&endTime='+(cutoff-1)};
  }));
  return {frame,serverTime:server.serverTime,closedThrough:cutoff-1,capturedAt:Date.now(),symbols};
 }
 async replay(trade,cutoff){
  // Binance only guarantees aggTrades for the last 48h; never invent a recovery beyond that window.
  if(cutoff-(trade.replayTime??trade.openedAt)>47*3600000)throw Error('REVIEW_REQUIRED: replay gap exceeds available 48-hour trade history');
  let cursor=trade.lastAggId,fromTime=Math.max(trade.replayTime??trade.openedAt,trade.openedAt+1),events=[];
  for(let page=0;page<8;page++){
   const endTime=Math.min(cutoff,fromTime+3599000);
   const query=cursor===null?{symbol:trade.symbol,startTime:fromTime,endTime,limit:1000}:{symbol:trade.symbol,fromId:cursor+1,limit:1000};
   const rows=await this.get('/fapi/v1/aggTrades',query);
   if(!Array.isArray(rows))throw Error('Malformed aggregate trade response');
   const valid=rows.filter(e=>e.T<=cutoff&&e.T>=trade.openedAt&&(cursor===null||e.a>cursor));
   events.push(...valid);
   if(valid.length){cursor=valid.at(-1).a;fromTime=valid.at(-1).T;}
   if(rows.some(e=>e.T>cutoff))return {events,complete:true,through:cutoff};
   if(rows.length<1000){
    if(query.fromId!==undefined||endTime===cutoff)return {events,complete:true,through:cutoff};
    fromTime=endTime+1;cursor=null;
   }
  }
  return {events,complete:false,through:fromTime};
 }
 async funding(trade,cutoff){
  const until=Math.min(cutoff,trade.closedAt??cutoff),cached=this.fundingCache.get(trade.symbol),now=Date.now();
  if(cached&&cached.from<=trade.openedAt+1&&cached.through>=until&&now-cached.checkedAt<60000)return cached.events.filter(e=>e.fundingTime>trade.openedAt&&e.fundingTime<=until);
  const events=[],from=Math.min(trade.openedAt+1,cached?.from??Infinity),end=Math.max(until,now);
  let cursor=from;
  while(cursor<=end){
   const rows=await this.get('/fapi/v1/fundingRate',{symbol:trade.symbol,startTime:cursor,endTime:end,limit:1000});
   if(!Array.isArray(rows))throw Error('Malformed funding response');events.push(...rows);
   if(rows.length<1000)break;const next=Number(rows.at(-1).fundingTime)+1;if(next<=cursor)throw Error('Funding pagination stalled');cursor=next;
  }
  this.fundingCache.set(trade.symbol,{from,through:end,checkedAt:now,events});return events.filter(e=>e.fundingTime>trade.openedAt&&e.fundingTime<=until);
 }
}
