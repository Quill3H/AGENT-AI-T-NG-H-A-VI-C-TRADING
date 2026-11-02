import http from 'node:http';
// Fixed read-only probes only; never expose a generic URL fetcher or credentials.
http.createServer(async(req,res)=>{
 res.setHeader('Content-Type','application/json');res.setHeader('Cache-Control','no-store');
 if(req.url==='/health'){res.end(JSON.stringify({ok:true,mode:'CONNECTIVITY_CHECK_ONLY'}));return;}
 if(req.url!=='/probe'||req.method!=='GET'){res.writeHead(404);res.end('{}');return;}
 try{
  const r=await fetch('https://fapi.binance.com/fapi/v1/time',{signal:AbortSignal.timeout(15000)});
  const result={mode:'CONNECTIVITY_CHECK_ONLY',source:'Binance USD-M Futures public clock',status:r.status,ok:r.ok,checkedAt:new Date().toISOString()};
  if(r.ok){const data=await r.json();result.validClock=Number.isSafeInteger(data.serverTime);result.ok=result.validClock;}
  res.end(JSON.stringify(result));
 }catch{res.writeHead(502);res.end(JSON.stringify({ok:false,error:'Public clock request failed'}));}
}).listen(Number(process.env.PORT??10000),'0.0.0.0',()=>console.log('Read-only connectivity probe ready'));
