let state=null;
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>n===null||n===undefined?'Chưa rõ':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2}).format(n);
const price=n=>n===undefined?'—':new Intl.NumberFormat('en-US',{maximumFractionDigits:5}).format(n);
const time=n=>n?new Date(n).toLocaleString('vi-VN',{timeZone:'Asia/Bangkok',hour12:false}):'Chưa có';
const next=(frame,now)=>Math.floor(now/({'15m':900000,'1h':3600000,'4h':14400000}[frame]))*({'15m':900000,'1h':3600000,'4h':14400000}[frame])+({'15m':900000,'1h':3600000,'4h':14400000}[frame]);
const color=n=>n>0?'gain':n<0?'loss':'';
function note(value){const rows=String(value??'').split(/\r?\n/).filter(x=>x.trim());return rows.length>=3&&rows.length<=5&&rows.every(x=>/^\d+[.)]\s/.test(x))?'<ol>'+rows.map(x=>'<li>'+esc(x.replace(/^\d+[.)]\s*/,''))+'</li>').join('')+'</ol>':'<p>'+esc(value)+'</p>';}
function currentRisk(t){return t.currentPlannedLoss===undefined?t.riskPct:t.currentPlannedLoss/(t.balanceAtEntry??t.plannedLoss/t.riskPct);}
function managementLog(t){return (t.managementEvents??[]).map(e=>'<p>'+time(e.recordedAt??e.time)+' · '+(e.action==='CLOSE'?'Chốt sớm @ '+price(e.exit):'TP '+price(e.before.tp)+' → '+price(e.after.tp)+' · SL '+price(e.before.sl)+' → '+price(e.after.sl))+'<br>'+esc(e.reason)+'</p>').join('');}
function render(){
 const expanded=[...document.querySelectorAll('details[data-key][open]')].map(el=>el.dataset.key);
 const now=Date.now(),healthy=state.worker.healthy&&now-state.worker.lastSuccess<(state.venue==='OKX'?1200000:45000);
 const updated=state.cloudUpdatedAt??state.worker.lastSuccess,age=updated?Math.max(0,now-updated):Infinity;
 const status=state.worker.error?'Lỗi xử lý lượt gần nhất':!healthy?'Dữ liệu quá hạn — chưa có lượt cập nhật mới':age>420000?'Đang chờ lượt cập nhật tiếp theo':'Lượt cập nhật gần nhất thành công';
 $('clock').textContent=time(state.serverTime);$('worker-label').textContent=status;
 $('status').textContent=status;
 $('status-detail').textContent=state.worker.error??(state.kronos?.required?'Gemini + Kronos · dự báo nến cho 15m / 1h / 4h · '+Object.entries(state.kronos.frames??{}).map(([f,v])=>f+': '+(v.status==='AVAILABLE'?'đã có dự báo':'chặn entry vì thiếu dự báo')).join(' · '):state.venue==='OKX'?'OKX · AI 15m / 1h / 4h · TP/SL đối soát theo từng lượt cloud.':'AI ra quyết định 15m / 1h / 4h · Worker liên tục theo dõi TP/SL.');
 $('worker-dot').className=$('status-dot').className='dot '+(healthy?'green':'amber');
 $('status-detail').textContent='Sổ cập nhật: '+time(updated)+' · '+(Number.isFinite(age)?Math.floor(age/60000)+' phút trước · ':'')+$('status-detail').textContent;
 $('last-poll').textContent='Sổ cập nhật: '+time(updated);
 $('bots').innerHTML=state.wallets.map((w,i)=>{
  const m=w.metrics,d=w.decisions.at(-1),open=w.trades.find(t=>t.status==='OPEN');
  const lastReject=state.rejections.filter(r=>r.frame===w.frame&&r.time>(d?.decidedAt??0)).at(-1);
  return `<article class="bot bot-${i}"><div class="bot-top"><div class="bot-title"><span class="timeframe">${esc(w.frame)}</span><h3>Ví ${esc(w.frame)}</h3></div><span class="badge ${open?'OPEN':''}">${open?m.openCount+' lệnh mở':w.blocked?'Tạm dừng':'Đang chờ'}</span></div><div class="balance-line"><strong class="balance">${money(m.equity)}</strong><span class="muted">equity</span></div><p class="wallet-balance">Số dư ${money(w.balance)} · gốc $100<br>Giá trị lệnh mở ${money(m.notional)} · ${m.grossExposureMultiple==null?'—':m.grossExposureMultiple.toFixed(2)+'x số dư'}</p><div class="bot-metrics"><div><span>Risk cộng dồn</span><strong>${money(m.openRisk)}</strong><small>${w.balance>0?(m.openRisk/w.balance*100).toFixed(2)+'% số dư':'Chưa rõ tỷ lệ'}</small></div><div><span>Lệnh đã đóng</span><strong>${m.closedCount}</strong></div><div><span>PnL đã chốt</span><strong class="${color(m.netRealized)}">${money(m.netRealized)}</strong></div></div><p class="bot-strategy">${esc(d?d.method:'Chờ lượt phân tích AI đầu tiên.')}</p><div class="bot-foot"><span>AI gần nhất: ${d?time(d.decidedAt):'Chưa có'}</span><span>Chu kỳ kế: ${time(next(w.frame,state.serverTime))}</span>${lastReject?`<span class="loss">Tín hiệu chưa nhận: ${esc(lastReject.error)}</span>`:''}${w.blocked?`<span class="loss">${esc(w.blocked)}</span>`:''}</div></article>`;
 }).join('');
 const total=key=>state.wallets.reduce((sum,w)=>sum+(w.metrics[key]??0),0);
 $('portfolio').innerHTML=`<dl class="portfolio-stats"><div><dt>Equity tổng</dt><dd>${state.wallets.every(w=>w.metrics.equity!==null)?money(total('equity')):'Chưa rõ'}</dd></div><div><dt>Risk cộng dồn đang mở</dt><dd>${money(total('openRisk'))}</dd></div><div><dt>Lệnh đang mở</dt><dd>${total('openCount')}</dd></div><div><dt>PnL đã chốt</dt><dd class="${color(total('netRealized'))}">${money(total('netRealized'))}</dd></div></dl>`;
 const curves=state.wallets.map(w=>w.curve),points=curves.flat();
 if(points.length===3)$('chart').innerHTML='<div class="chart-empty">Chưa có lệnh đóng.<br>Đường vốn bắt đầu từ $100 cho mỗi ví.</div>';
 else{
  const lo=Math.min(98,...points.map(p=>p.value))-1,hi=Math.max(102,...points.map(p=>p.value))+1,t0=Math.min(...points.map(p=>p.time)),t1=Math.max(...points.map(p=>p.time),t0+1);
  $('chart').innerHTML=`<svg viewBox="0 0 600 200" role="img" aria-label="Đường vốn ba ví theo thời gian"><line x1="40" y1="160" x2="590" y2="160" stroke="#d8e1d8"/><text x="0" y="20" font-size="12" fill="#596960">$${hi.toFixed(0)}</text><text x="0" y="170" font-size="12" fill="#596960">$${lo.toFixed(0)}</text>${curves.map((c,i)=>`<polyline fill="none" stroke="${['#216b57','#4269a8','#87603b'][i]}" stroke-width="2" points="${c.map(p=>`${40+(p.time-t0)/(t1-t0)*550},${170-(p.value-lo)/(hi-lo)*150}`).join(' ')}"/>`).join('')}</svg>`;
 }
 const trades=state.wallets.flatMap(w=>w.trades).sort((a,b)=>b.openedAt-a.openedAt),filter=$('filter').value,shown=trades.filter(t=>filter==='all'||t.status===filter);
 $('trade-rows').innerHTML=shown.length?shown.map(t=>`<tr><td>${esc(t.frame)}<small>${time(t.openedAt)}</small></td><td>${esc(t.symbol)}<small>${esc(t.side)} · ${t.leverage??1}x${t.leverage?'':' (cũ)'}</small></td><td>${price(t.entry)}</td><td>${price(t.tp)}<small>${price(t.sl)}</small></td><td>${t.allocationPct===undefined?'Chính sách cũ':(t.allocationPct*100).toFixed(2)+'% · '+money(t.initialMargin)}<small>Risk SL ${(currentRisk(t)*100).toFixed(2)}% · ${money(t.currentPlannedLoss??t.plannedLoss)}</small></td><td class="${color(t.pnl)}">${t.pnl===undefined?'Đang mở':money(t.pnl)}</td><td><span class="badge ${esc(t.status)}">${esc(t.status)}</span></td><td><details class="trade-detail" data-key="${esc(t.id)}"><summary>Vì sao?</summary><strong>${esc(t.method)}</strong>${note(t.reason)}<p>Vô hiệu: ${esc(t.invalidation)}</p><p>Funding: ${money(t.funding)} · Phí vào: ${money(t.entryFee)}</p>${managementLog(t)}<p>ID: ${esc(t.id)}</p></details></td></tr>`).join(''):'<tr><td colspan="8" class="empty">Chưa có lệnh phù hợp bộ lọc. Lượt không thực hiện do lỗi được ghi riêng.</td></tr>';
 $('order-summary').textContent=`${shown.length} lệnh hiển thị / ${trades.length} lệnh trong sổ · không nhập lệnh cũ vào ba ví.`;
 const decisions=state.wallets.flatMap(w=>w.decisions.map(d=>({...d,frame:w.frame}))).sort((a,b)=>b.decidedAt-a.decidedAt).slice(0,9);
 $('decision-list').innerHTML=decisions.length?decisions.map(d=>`<details class="decision" data-key="${esc(d.contextId)}"><summary><strong>${esc(d.frame)} · ${esc(d.action)} ${esc(d.symbol??'')}</strong><small>${time(d.decidedAt)} · ${esc(d.method)}</small></summary>${note(d.reason)}<p>Kronos: ${d.kronos?esc(d.kronos.model)+" · dự báo tạo lúc "+time(d.kronos.generatedAt)+" · kịch bản tham khảo, không phải độ tin cậy đã hiệu chuẩn":"Quyết định cũ chưa có dự báo Kronos"}</p><p>Điều kiện vô hiệu: ${esc(d.invalidation)}</p></details>`).join(''):'<p class="empty-copy">Chờ chu kỳ AI đầu tiên. Mỗi quyết định sẽ lưu phương pháp, lý do và điều kiện vô hiệu.</p>';
 const reviews=state.wallets.flatMap(w=>w.reviews.map(r=>({...r,frame:w.frame}))).sort((a,b)=>b.time-a.time).slice(0,6);
 $('lessons').innerHTML=reviews.length?reviews.map(r=>`<article class="lesson"><h3>${esc(r.frame)} · ${esc(r.tradeId)}</h3><p>${esc(r.lesson)}</p><small>${time(r.time)}</small></article>`).join(''):'<p class="empty-copy">Chưa có bài học từ lệnh đóng. AI sẽ đối chiếu luận điểm với kết quả; dữ liệu ít chưa đủ để kết luận hiệu quả.</p>';
 $('market-rows').innerHTML=Object.values(state.quotes).map(q=>`<div class="market-item"><span>${esc(q.symbol)} · ${state.policy.leverageBySymbol?.[q.symbol]??1}x</span><strong>${price((q.bid+q.ask)/2)}</strong><span>Bid ${price(q.bid)} / Ask ${price(q.ask)}</span><small>${time(q.time)}${now-q.time>30000?' · Giá đã cũ':''}</small></div>`).join('');
 for(const el of document.querySelectorAll('details[data-key]'))if(expanded.includes(el.dataset.key))el.open=true;
 $('errors').textContent=state.rejections.length?'Từ chối gần nhất: '+state.rejections.at(-1).error:'';
}
async function refresh(){try{const response=await fetch('/api/state');if(!response.ok)throw Error('HTTP '+response.status);state=await response.json();render();}catch(e){$('status').textContent='Mất kết nối worker';$('status-detail').textContent='Chưa tải được sổ cloud; thử tải lại và kiểm tra lịch sử chạy trên GitHub. '+e.message;$('worker-label').textContent='Mất kết nối';$('worker-dot').className=$('status-dot').className='dot amber';}}
$('refresh').addEventListener('click',refresh);$('filter').addEventListener('change',()=>state&&render());
$('export').addEventListener('click',()=>{if(!state)return;const url=URL.createObjectURL(new Blob([JSON.stringify(state,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='paper-ai-ledger.json';a.click();URL.revokeObjectURL(url);});
await refresh();setInterval(refresh,5000);
