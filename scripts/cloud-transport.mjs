import {createHmac,timingSafeEqual} from 'node:crypto';
export function sign(key,purpose,time,body){
 if(typeof key!=='string'||!key.trim())throw Error('Missing transport credential');
 const derived=createHmac('sha256',key.trim()).update('paper-studio-cloud-v1').digest();
 return createHmac('sha256',derived).update(`${purpose}\n${time}\n${body}`).digest('hex');
}
export function verify(key,purpose,time,body,signature,now=Date.now(),maxAge=300000){
 if(!Number.isSafeInteger(time)||Math.abs(now-time)>maxAge||!/^\w+$/.test(purpose)||!/^[a-f0-9]{64}$/.test(signature??''))return false;
 const expected=Buffer.from(sign(key,purpose,time,body),'hex'),actual=Buffer.from(signature,'hex');
 return timingSafeEqual(expected,actual);
}
export const safeFile=name=>name==='state.json'||name==='state-view.json'||/^(contexts|decisions)\/[a-zA-Z0-9_-]+\.json$/.test(name);
export function validateState(state){
 if(state?.version!==1||state.mode!=='PAPER_ONLY'||state.wallets?.length!==3||state.wallets.some((w,i)=>w.frame!==['15m','1h','4h'][i]||!Number.isFinite(w.balance)||!Array.isArray(w.trades)||!Array.isArray(w.decisions)||!Array.isArray(w.reviews)))throw Error('Invalid paper ledger');
 return state;
}
