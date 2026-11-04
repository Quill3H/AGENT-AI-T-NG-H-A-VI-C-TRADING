// Retry only an explicit unavailable response, never a model result or mutation.
export async function geminiRequest(url,options,{key='',fetcher=fetch,timeoutMs=90000,clock=Date.now,pause=ms=>new Promise(r=>setTimeout(r,ms)),random=Math.random,onAttempt=()=>{}}={}){
 if(!Number.isSafeInteger(timeoutMs)||timeoutMs<=0||timeoutMs>2147483647)throw Error('Invalid Gemini timeout');
 const deadline=clock()+timeoutMs;
 for(let attempt=1;attempt<=3;attempt++){
  const left=deadline-clock();if(left<=0)throw Error('Gemini request deadline reached');
  const started=clock(),response=await fetcher(url,{...options,signal:AbortSignal.timeout(left)});
  if(response.ok){onAttempt({attempt,status:response.status??200,elapsedMs:clock()-started});return response;}
  let detail={};try{detail=(await response.json()).error??{};}catch{}
  const clean=v=>String(v??'').replaceAll(key||'__absent_credential__','[redacted]').replace(/AIza[\w-]{20,}/g,'[redacted]').replace(/[\r\n]/g,' ').slice(0,180);
  const providerStatus=clean(detail.status??detail.code),message=clean(detail.message);
  const error=new Error(`Gemini HTTP ${response.status}${providerStatus?' '+providerStatus:''}${message?': '+message:''}; attempts=${attempt}; no fallback or decision submitted`);
  const retryAfter=response.headers?.get('retry-after');
  const requested=retryAfter?(Number.isFinite(Number(retryAfter))?Math.max(0,Number(retryAfter)*1000):Math.max(0,Date.parse(retryAfter)-clock())):0;
  const delay=Math.max(1000*2**(attempt-1)+Math.floor(random()*250),Number.isFinite(requested)?requested:0);
  const retry=response.status===503&&attempt<3&&delay+100<deadline-clock();
  onAttempt({attempt,status:response.status,providerStatus,elapsedMs:clock()-started,retry,delayMs:retry?delay:0});
  if(!retry)throw error;
  await pause(delay);
 }
}
