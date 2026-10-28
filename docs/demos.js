const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(v);
const count=v=>new Intl.NumberFormat('en-US',{maximumFractionDigits:0}).format(v);
const pct=(v,d=1)=>`${(v*100).toFixed(d)}%`;
const pp=v=>`${v>=0?'+':''}${(v*100).toFixed(2)} pp`;
const metric=(label,value,note='')=>`<div class="metric"><small>${esc(label)}</small><strong>${esc(value)}</strong><em>${esc(note)}</em></div>`;
const select=(id,label,values,chosen)=>`<label>${esc(label)}<select id="${id}">${values.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(chosen)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;
const table=(heads,rows,cls='')=>`<div class="table-scroll"><table class="${cls}"><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map((v,i)=>`<td class="${i?'num':''}">${esc(v)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
const chart=(label,content,h=280)=>`<svg viewBox="0 0 900 ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${content}</svg>`;
const label=(x,y,text,anchor='middle')=>`<text class="chart-label" x="${x}" y="${y}" text-anchor="${anchor}">${esc(text)}</text>`;
const line=(x1,y1,x2,y2,color='#dce3d9',dash='')=>`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" ${dash?`stroke-dasharray="${dash}"`:''}/>`;

function seriesChart(rows,keys,colors,formatY=count){
  const max=Math.max(1,...rows.flatMap(r=>keys.map(k=>r[k])))*1.12;
  const x=i=>60+i/Math.max(1,rows.length-1)*810,y=v=>225-v/max*195;
  let svg='';
  for(let i=0;i<=4;i++){const v=max*i/4;svg+=line(60,y(v),870,y(v))+label(50,y(v)+4,formatY(v),'end');}
  keys.forEach((key,j)=>{svg+=`<polyline points="${rows.map((r,i)=>`${x(i)},${y(r[key])}`).join(' ')}" fill="none" stroke="${colors[j]}" stroke-width="2.5" stroke-linejoin="round"/>`;});
  [0,Math.floor(rows.length/2),rows.length-1].forEach(i=>{if(rows[i])svg+=label(x(i),250,rows[i].date||rows[i].month);});
  return chart('Time series: '+keys.join(' and '),svg,270);
}

function inventory(root,data){
  root.innerHTML=`<div class="demo-controls">${select('inv-policy','Forecast policy',[['seasonal','Weekday + recent trend'],['rolling','28-day rolling mean']],'seasonal')}${select('inv-lead','Lead time',[['3','3 days'],['7','7 days'],['14','14 days']],'7')}${select('inv-buffer','Safety multiplier',[['0','0 · no buffer'],['1','1.000'],['1.645','1.645'],['2.326','2.326']],'1.645')}${select('inv-sku','Demand chart SKU',data.scenarios[0].skus.map(s=>[s.sku,s.sku]),'SKU-01')}</div><div id="inv-results" aria-live="polite"></div>`;
  const el=id=>root.querySelector('#'+id);
  function render(){
    const lead=+el('inv-lead').value,buffer=+el('inv-buffer').value,policy=el('inv-policy').value;
    const s=data.scenarios.find(x=>x.leadDays===lead&&x.buffer===buffer&&x.policy===policy);
    const choices=data.scenarios.filter(x=>x.leadDays===lead);const sku=s.skus.find(x=>x.sku===el('inv-sku').value);
    const minX=Math.min(...choices.map(x=>x.averageInventoryValue))*.9,maxX=Math.max(...choices.map(x=>x.averageInventoryValue))*1.07;
    const minY=Math.max(0,Math.min(...choices.map(x=>x.fillRate))-.004),maxY=1;
    const x=v=>75+(v-minX)/(maxX-minX)*770,y=v=>225-(v-minY)/(maxY-minY)*185;
    let svg='';for(let i=0;i<=4;i++){const vy=minY+(maxY-minY)*i/4,vx=minX+(maxX-minX)*i/4;svg+=line(75,y(vy),845,y(vy))+label(63,y(vy)+4,pct(vy,1),'end')+label(x(vx),247,money(vx));}
    for(const key of ['rolling','seasonal']){const values=choices.filter(c=>c.policy===key).sort((a,b)=>a.buffer-b.buffer);svg+=`<polyline points="${values.map(c=>`${x(c.averageInventoryValue)},${y(c.fillRate)}`).join(' ')}" fill="none" stroke="${key==='seasonal'?'#3e6656':'#ae9364'}" stroke-width="2" opacity=".6"/>`;}
    for(const c of choices){svg+=`<circle cx="${x(c.averageInventoryValue)}" cy="${y(c.fillRate)}" r="${c.id===s.id?7:4.5}" fill="${c.policy==='seasonal'?'#3e6656':'#ae9364'}" stroke="${c.id===s.id?'#152c22':'#fff'}" stroke-width="${c.id===s.id?2:1}"><title>${esc(c.policy)} / buffer ${c.buffer}: ${pct(c.fillRate,2)} fill, ${money(c.averageInventoryValue)} inventory</title></circle>`;}
    svg+=label(460,276,'Average end-of-day inventory value · USD')+label(76,20,'Unit fill rate','start');
    const traces=sku.trace.slice(-42);
    el('inv-results').innerHTML=`<div class="metrics">${metric('Unit fill rate',pct(s.fillRate,2),'All 12 SKUs · fulfilled / demand')}${metric('Average stock value',money(s.averageInventoryValue),'Average end-of-day inventory')}${metric('Unfulfilled demand',count(s.lost),'Units lost during the test window')}${metric('Illustrative decision cost',money(s.totalCost),'Holding cost + lost unit margin')}</div><div class="chart-box"><h3>How much inventory buys the next increment of service?</h3><p>Each point is one policy and buffer at the selected lead time. The outlined point is your selection. Vertical scale is shown on the axis.</p>${chart('Inventory value versus unit fill rate for eight scenarios',svg,292)}<div class="legend"><span><i></i> Weekday + trend</span><span><i class="alt"></i> Rolling mean</span></div></div>
    <div class="chart-box"><h3>${esc(sku.sku)} · observed demand and one-day-ahead forecast</h3><p>Last 42 evaluation days. The SKU selector changes this chart; headline results cover all 12 SKUs.</p>${seriesChart(traces,['demand','forecast'],['#3e6656','#ae9364'])}<div class="legend"><span><i></i> Observed demand</span><span><i class="alt"></i> Forecast</span></div></div>
    <p class="audit-pass">✓ ${data.meta.testDays} chronological test days · ${data.meta.warmupDays} warm-up days · ${count(s.demand)} demand units = ${count(s.fulfilled)} fulfilled + ${count(s.lost)} lost</p>
    <details><summary>Inspect all eight policies at this lead time</summary>${table(['Policy / buffer','Fill rate','Stock value','Holding cost','Lost margin','Forecast WAPE'],choices.map(c=>[`${c.policy} / ${c.buffer}`,pct(c.fillRate,2),money(c.averageInventoryValue),money(c.holdingCost),money(c.lostMargin),pct(c.wape,2)]))}</details>
    <details><summary>Inspect ${esc(sku.sku)} stock ledger · last 14 days</summary>${table(['Date','Opening','Received','Demand','Sold','Lost','Closing','Ordered'],sku.trace.slice(-14).map(r=>[r.date,r.opening,r.arrivals,r.demand,r.sold,r.lost,r.closing,r.ordered]))}</details>
    <p class="demo-note">Model assumptions: daily review, deterministic lead time, unlimited replenishment, lost sales, no substitution. Holding cost uses 25% of inventory value per year; lost margin uses each SKU’s synthetic unit margin. WAPE = total absolute one-day forecast error / total demand. The buffer multiplier is not a guaranteed service level.</p>`;
  }
  root.querySelectorAll('select').forEach(e=>e.addEventListener('change',render));render();
}

const addMonth=(month,n)=>{const [y,m]=month.split('-').map(Number);const t=y*12+m-1+n;return `${Math.floor(t/12)}-${String(t%12+1).padStart(2,'0')}`;};
function revenue(root,data){
  const months=[...new Set(data.bridges.map(r=>r.month))];
  root.innerHTML=`<div class="demo-controls">${select('rev-month','Reporting month',months.map(m=>[m,m]),months.at(-1))}${select('rev-segment','Customer segment',[['All','All segments'],['SMB','SMB'],['Mid-market','Mid-market']],'All')}</div><div id="rev-results" aria-live="polite"></div>`;
  function render(){
    const month=root.querySelector('#rev-month').value,segment=root.querySelector('#rev-segment').value;
    const selected=data.bridges.filter(r=>r.month===month&&(segment==='All'||r.segment===segment));
    const sum=k=>selected.reduce((a,r)=>a+r[k],0);const b=Object.fromEntries(['opening','new','reactivation','expansion','contraction','churn','closing','active','residual'].map(k=>[k,sum(k)]));
    const nrr=b.opening?(b.opening+b.expansion-b.contraction-b.churn)/b.opening:null;
    const deltas=[['New',b.new],['Reactivated',b.reactivation],['Expansion',b.expansion],['Contraction',-b.contraction],['Churn',-b.churn]];
    let running=0;const bars=deltas.map(([name,v])=>{const start=running;running+=v;return {name,start,end:running,value:v};});bars.push({name:'Net change',start:0,end:running,value:running});
    const lo=Math.min(0,...bars.flatMap(c=>[c.start,c.end])),hi=Math.max(1,...bars.flatMap(c=>[c.start,c.end]));const range=hi-lo||1;
    const y=v=>225-(v-lo+range*.08)/(range*1.25)*185;let svg='';
    for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;svg+=line(70,y(v),860,y(v))+label(60,y(v)+4,money(v/100),'end');}
    bars.forEach((c,i)=>{const bx=95+i*128,top=Math.min(y(c.start),y(c.end)),height=Math.max(2,Math.abs(y(c.start)-y(c.end)));svg+=`<rect x="${bx}" y="${top}" width="78" height="${height}" rx="2" fill="${i===5?'#263f34':c.value>=0?'#6a8a70':'#b48777'}"/>`+label(bx+39,top-10,`${c.value>=0?'+':''}${money(c.value/100)}`)+label(bx+39,250,c.name);if(i<4)svg+=line(bx+78,y(c.end),bx+128,y(c.end),'#9ba99c','3 3');});
    const cohortRows=data.cohorts.filter(r=>r.month<=month&&(segment==='All'||r.segment===segment));
    const cohorts=[...new Set(cohortRows.map(r=>r.cohort))].sort().slice(-12);
    let heat=`<div class="table-scroll"><table class="heatmap"><thead><tr><th>Cohort</th><th>Accounts</th>${Array.from({length:12},(_,i)=>`<th>M${i}</th>`).join('')}</tr></thead><tbody>`;
    for(const cohort of cohorts){const base=cohortRows.filter(r=>r.cohort===cohort&&r.month===cohort).reduce((n,r)=>n+r.original_customers,0);heat+=`<tr><td>${cohort}</td><td>${base}</td>`;for(let i=0;i<12;i++){const m=addMonth(cohort,i);const rows=cohortRows.filter(r=>r.cohort===cohort&&r.month===m);if(!rows.length){heat+='<td>—</td>';continue;}const active=rows.reduce((n,r)=>n+r.active_customers,0),rate=base?active/base:0;heat+=`<td style="background:rgba(62,102,86,${.08+rate*.82});color:${rate>.55?'white':'#233e30'}" title="${active} active of ${base} original accounts">${pct(rate,0)}</td>`;}heat+='</tr>';}
    heat+='</tbody></table></div>';
    const allTrend=months.filter(m=>m<=month).map(m=>({date:m,MRR:data.bridges.filter(r=>r.month===m&&(segment==='All'||r.segment===segment)).reduce((n,r)=>n+r.closing/100,0)}));
    root.querySelector('#rev-results').innerHTML=`<div class="metrics">${metric('Closing monthly recurring revenue',money(b.closing/100),'End-of-month contracted value')}${metric('Net MRR movement',`${b.closing-b.opening>=0?'+':''}${money((b.closing-b.opening)/100)}`,'Closing minus opening MRR')}${metric('Net revenue retention',nrr===null?'—':pct(nrr,1),'Opening base; excludes new + reactivated')}${metric('Active accounts',count(b.active),'Positive closing MRR')}</div>
    <div class="chart-box"><h3>What drove the change?</h3><p>${month} · ${esc(segment)} · cumulative change in USD. Opening and closing totals are reconciled below.</p>${chart('Waterfall of monthly recurring revenue movements',svg,275)}</div>
    <p class="audit-pass">✓ ${money(b.opening/100)} opening + ${money((b.new+b.reactivation+b.expansion)/100)} additions − ${money((b.contraction+b.churn)/100)} losses = ${money(b.closing/100)} closing. Residual: ${b.residual} cents.</p>
    <details><summary>Inspect the revenue bridge and monthly trend</summary>${table(['Movement','USD'],[['Opening',money(b.opening/100)],...deltas.map(([k,v])=>[k,money(v/100)]),['Closing',money(b.closing/100)],['Reconciliation residual',`${b.residual} cents`]])}${seriesChart(allTrend,['MRR'],['#3e6656'],money)}</details>
    <div class="chart-box" style="margin-top:25px"><h3>Do customers stay active?</h3><p>Active-customer retention by acquisition cohort · M0 is the acquisition month. Most recent 12 available cohorts, first 12 ages. Reactivated accounts count as active.</p>${heat}</div>
    <details><summary>Data-quality audit · ${data.meta.rejectedEvents} isolated events</summary>${table(['Check','Events'],[['Input',data.meta.inputEvents],['Accepted',data.meta.acceptedEvents],...Object.entries(data.meta.rejectionReasons)])}<p class="demo-note"><a class="text-link" href="assets/revenue-rejected.csv" download>Download rejected events ↓</a></p></details>
    <details><summary>Inspect a 12-account ledger sample at this month</summary>${table(['Account','Segment','Opening','New','Expansion','Contraction','Churn','Reactivated','Closing'],data.ledger.filter(r=>r.month===month&&(segment==='All'||r.segment===segment)).map(r=>[r.customer_id,r.segment,...['opening_cents','new_cents','expansion_cents','contraction_cents','churn_cents','reactivation_cents','mrr_cents'].map(k=>money(r[k]/100))]))}</details>
    <p class="demo-note">MRR is a contracted monthly run rate, not recognized revenue or cash. NRR = (opening + expansion − contraction − churn) / opening. Cohort denominators are original acquired accounts. All calculations use integer cents. <a class="text-link" href="assets/revenue-bridge.csv" download>Download full bridge ↓</a></p>`;
  }
  root.querySelectorAll('select').forEach(e=>e.addEventListener('change',render));render();
}

export function experimentDecision(result,minimumLift=.002,maximumErrorIncrease=.005){
  if(!result.allocation.passed)return 'Investigate allocation';
  if(!result.conversion.largeCounts||!result.errors.largeCounts)return 'Insufficient data';
  if(result.errors.lower>maximumErrorIncrease)return 'Stop: guardrail regression';
  if(result.errors.upperOneSided>maximumErrorIncrease)return 'Inconclusive: guardrail risk';
  if(result.conversion.upper<0)return 'Stop: conversion harm';
  if(result.conversion.lower>=minimumLift)return 'Ship candidate';
  return 'Inconclusive: practical lift';
}

function experiment(root,data){
  root.innerHTML=`<div class="demo-controls">${select('exp-scenario','Experiment scenario',[['balanced','Balanced experiment'],['guardrail-regression','Product-error regression'],['logging-loss','Treatment telemetry loss']],'balanced')}<label for="exp-threshold">Minimum practical lift: <output id="exp-threshold-value">0.20 pp</output><input type="range" id="exp-threshold" min="0" max="1.5" value="0.2" step="0.05"></label></div><div id="exp-results" aria-live="polite"></div>`;
  const pvalue=v=>v<.0001?'< 0.0001':v.toFixed(4);
  function render(){
    const s=data.scenarios.find(x=>x.id===root.querySelector('#exp-scenario').value),threshold=+root.querySelector('#exp-threshold').value/100;
    root.querySelector('#exp-threshold-value').textContent=`${(threshold*100).toFixed(2)} pp`;
    const decision=experimentDecision(s,threshold),v=s.conversion,error=s.errors;
    const status=decision==='Ship candidate'?'':decision.startsWith('Stop')||!s.allocation.passed?'stop':'warn';
    const reason=!s.allocation.passed?'The observed user split fails the allocation check. Treat the effect estimates as diagnostic only.':decision==='Ship candidate'?'The lower conversion bound clears the selected practical threshold and the error-rate upper bound stays below the guardrail.':decision.includes('guardrail')?'The product-error guardrail does not support shipping, regardless of the conversion improvement.':'The data do not establish the selected minimum practical improvement. A positive point estimate is not enough.';
    const lo=Math.min(-.005,v.lower-.003),hi=Math.max(.02,v.upper+.003,threshold+.003),x=n=>75+(n-lo)/(hi-lo)*760;let svg='';
    for(let i=0;i<=5;i++){const t=lo+(hi-lo)*i/5;svg+=line(x(t),30,x(t),145)+label(x(t),167,`${(t*100).toFixed(1)} pp`);}
    svg+=line(x(0),22,x(0),150,'#263d32')+line(x(threshold),22,x(threshold),150,'#b99555','5 4');
    svg+=`<line x1="${x(v.lower)}" y1="86" x2="${x(v.upper)}" y2="86" stroke="#5e6686" stroke-width="5"/><circle cx="${x(v.delta)}" cy="86" r="8" fill="#4b5377"/>`+line(x(v.lower),74,x(v.lower),98,'#4b5377')+line(x(v.upper),74,x(v.upper),98,'#4b5377')+label(x(v.delta),63,pp(v.delta))+label(75,205,'Treatment minus control conversion · percentage points','start');
    root.querySelector('#exp-results').innerHTML=`<div class="decision ${status}"><div><h3>${esc(decision)}</h3><p>${esc(reason)}</p></div><small>Fixed-horizon decision</small></div><div class="metrics">${metric('Control conversion',pct(v.controlRate,2),`${count(s.counts.control)} users`)}${metric('Treatment conversion',pct(v.treatmentRate,2),`${count(s.counts.treatment)} users`)}${metric('Observed difference',pp(v.delta),'Absolute percentage points')}${metric('Allocation check',s.allocation.passed?'Passed':'Failed',`SRM p-value ${pvalue(s.allocation.pValue)}`)}</div>
    <div class="chart-box"><h3>Is the improvement large enough to matter?</h3><p>Two-sided 95% confidence interval. Solid vertical line: no effect. Dashed line: selected practical threshold.</p>${chart('95 percent interval for the conversion rate difference',svg,220)}<p>Interval: ${pp(v.lower)} to ${pp(v.upper)}. Two-sided pooled z-test p-value: ${pvalue(v.pValue)}.</p></div>
    ${table(['Decision gate','Observed evidence','Rule','Outcome'],[
      ['Allocation',`${pct(s.allocation.actualTreatment,2)} treatment`, `SRM p ≥ ${data.meta.srmAlpha}`,s.allocation.passed?'Pass':'Block'],
      ['Practical lift',`Lower 95% bound ${pp(v.lower)}`,`At least ${pp(threshold)}`,!s.allocation.passed?'Diagnostic only':v.lower>=threshold?'Pass':'Not established'],
      ['Product errors',`Upper one-sided 95% bound ${pp(error.upperOneSided)}`,`At most +0.50 pp`,!s.allocation.passed?'Diagnostic only':error.upperOneSided<=.005?'Pass':'Block'],
      ['Approximation', '≥10 successes and failures per arm', 'Both binary metrics',v.largeCounts&&error.largeCounts?'Pass':'Insufficient']])}
    <details><summary>Inspect descriptive device slices</summary>${table(['Device','Variant','Users','Conversions','Conversion','Errors'],s.segments.map(r=>[r.device,r.variant,count(r.users),count(r.converted),r.users?pct(r.converted/r.users,2):'—',count(r.errors)]))}<p class="demo-note">These slices are descriptive. No independent winner claims or multiple-comparison-adjusted tests are made for them.</p></details>
    <p class="demo-note">This slider is sensitivity analysis, not permission to choose a threshold after seeing a real test. Pre-specify the decision rule and sample horizon. The synthetic scenarios contain independent users; repeated peeking and clustered observations require different methods. Error-rate guardrail: treatment minus control ≤ +0.50 percentage points using a one-sided 95% upper bound.</p>`;
  }
  root.querySelector('#exp-scenario').addEventListener('change',render);root.querySelector('#exp-threshold').addEventListener('input',render);render();
}

export async function mountDemo(type,root,data){
  if(type==='inventory')inventory(root,data);
  else if(type==='revenue')revenue(root,data);
  else if(type==='experiment')experiment(root,data);
  else throw new Error('Unknown analytical demo');
}
