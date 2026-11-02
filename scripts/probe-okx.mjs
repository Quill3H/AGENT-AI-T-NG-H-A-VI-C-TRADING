export async function probeOkx({fetcher=fetch,pause=ms=>new Promise(r=>setTimeout(r,ms))}={}){
 const btc='BTC-USDT-SWAP';
 const specs=[['clock','public/time',{}],...['BTC','ETH','SOL','HYPE'].map(s=>['instrument '+s,'public/instruments',{instType:'SWAP',instId:s+'-USDT-SWAP'}]),
  ['ticker','market/ticker',{instId:btc}],...['15m','1H','4H'].map(bar=>['candles '+bar,'market/candles',{instId:btc,bar,limit:'50'}]),
  ['history candles','market/history-candles',{instId:btc,bar:'1m',limit:'3'}],['funding history','public/funding-rate-history',{instId:btc,limit:'3'}],['trade history','market/history-trades',{instId:btc,limit:'3'}]];
 const checks=[];
 for(const [name,endpoint,params] of specs){
  try{
   const url='https://www.okx.com/api/v5/'+endpoint+'?'+new URLSearchParams(params);
   const r=await fetcher(url,{signal:AbortSignal.timeout(15000)});
   if(!r.ok){checks.push({name,http:r.status,ok:false});if([403,418,429].includes(r.status))break;continue;}
   const data=await r.json(),rows=Array.isArray(data.data)?data.data:[];
   const check={name,http:r.status,code:data.code,rows:rows.length,ok:data.code==='0'&&rows.length>0};
   if(name.startsWith('instrument '))check.contract=rows[0]?Object.fromEntries(['instId','state','ctVal','ctValCcy','lotSz','minSz','tickSz'].map(k=>[k,rows[0][k]])):null;
   if(name.startsWith('candles ')){
    const closed=rows.filter(r=>Array.isArray(r)&&r[8]==='1');check.closedRows=closed.length;check.newestClosedTime=closed.length?Number(closed[0][0]):null;
    check.ok=check.ok&&closed.length>=40;
   }
   checks.push(check);
  }catch{checks.push({name,ok:false,error:'Public endpoint request failed'});}
  await pause(250);
 }
 return {venue:'OKX',authenticated:false,checkedAt:new Date().toISOString(),ok:checks.length===specs.length&&checks.every(c=>c.ok),checks};
}
