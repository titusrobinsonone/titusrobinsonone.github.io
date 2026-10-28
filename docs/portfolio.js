import {mountDemo} from './demos.js';

export const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const href = value => {const u=new URL(value || '#',location.href); return ['http:','https:'].includes(u.protocol)?esc(value || '#'):'#';};
const $ = id => document.getElementById(id);
const external = (url,text,cls='') => `<a class="${cls}" href="${href(url)}" target="_blank" rel="noopener noreferrer">${esc(text)} <span aria-hidden="true">↗</span></a>`;
const list = items => (items || []).map(x=>`<li>${esc(x)}</li>`).join('');

async function readJSON(path){const r=await fetch(path);if(!r.ok)throw new Error(`Could not load ${path}`);return r.json();}

function chrome(site){
  $('site-header').innerHTML=`<div class="site-top wrap"><a class="identity" href="index.html" aria-label="${esc(site.name)} portfolio home"><span class="monogram" aria-hidden="true">TR</span><span><strong>${esc(site.name)}</strong><small>${esc(site.label)}</small></span></a><span class="top-note">AN INDEPENDENT DATA PORTFOLIO</span></div><nav class="navigation" aria-label="Main navigation"><div class="nav-inner wrap"><div class="nav-links"><a href="index.html#work">Selected work</a><a href="index.html#method">Approach</a><a href="index.html#about">About</a><a href="index.html#contact">Contact</a></div><div class="social-links">${external(site.github,'GitHub')}${external(site.linkedin,'LinkedIn')}</div></div></nav>`;
  $('site-footer').innerHTML=`<div class="footer-inner wrap"><span>© ${esc(site.year)} ${esc(site.name)} · Independent portfolio projects</span><span>Synthetic datasets · Transparent methods · ${external(site.github,'Source on GitHub')}</span></div>`;
}

function gallery(site,projects){
  for(const [id,value] of Object.entries({'profile-role':site.role,'headline':site.headline,'intro-copy':site.intro,'location':site.location,'about-copy':site.about,'contact-heading':site.contactHeading,'contact-copy':site.contactText})) $(id).textContent=value;
  for(const id of ['contact-link','about-link']) $(id).href=site.linkedin;
  const categories=['All work',...new Set(projects.map(p=>p.category))];let category='All work';
  $('filters').innerHTML=categories.map(c=>`<button class="filter" type="button" aria-pressed="${c===category}" data-category="${esc(c)}">${esc(c)}</button>`).join('');
  function render(){
    const query=$('project-search').value.toLowerCase().trim();
    const visible=projects.filter(p=>(category==='All work'||p.category===category)&&[p.name,p.title,p.summary,...p.tags].join(' ').toLowerCase().includes(query));
    $('gallery').innerHTML=visible.map(p=>{const url=`project.html?id=${encodeURIComponent(p.id)}`;return `<article class="project-card"><a class="project-image" href="${url}" aria-label="Explore ${esc(p.name)}"><img src="${href(p.thumbnail)}" alt="${esc(p.name)} analytical preview" width="760" height="500" loading="lazy"></a><div class="card-topline"><span>${esc(p.category)}</span><span>${esc(p.number)}</span></div><h3><a href="${url}">${esc(p.title)}</a></h3><p class="summary">${esc(p.summary)}</p><div class="tags">${p.tags.map(t=>`<span>${esc(t)}</span>`).join('')}</div><a class="card-bottom" href="${url}"><span>Explore ${esc(p.name)}</span><span aria-hidden="true">↗</span></a><p class="card-proof">${esc(p.proof)}</p></article>`;}).join('');
    $('project-count').textContent=`${visible.length} ${visible.length===1?'project':'projects'} shown`;$('no-results').hidden=!!visible.length;
    document.querySelectorAll('.filter').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.category===category)));
  }
  $('filters').addEventListener('click',e=>{const b=e.target.closest('button[data-category]');if(b){category=b.dataset.category;render();}});
  $('project-search').addEventListener('input',render);render();
}

async function caseStudy(site,projects){
  const id=new URLSearchParams(location.search).get('id'); const p=projects.find(x=>x.id===id);
  if(!p){$('case-root').innerHTML='<div class="loading"><h1>Project not found.</h1><p>This project may have moved. <a class="text-link" href="index.html#work">Explore the portfolio →</a></p></div>';return;}
  document.title=`${p.name} | ${site.name}`;
  const next=projects[(projects.indexOf(p)+1)%projects.length];
  $('case-root').innerHTML=`<a class="back-link" href="index.html#work">← Back to selected work</a><section class="case-hero"><div><p class="eyebrow">PROJECT ${esc(p.number)} / ${esc(p.category)}</p><h1>${esc(p.title)}</h1><p class="question">${esc(p.question)}</p><div class="tags">${p.tags.map(t=>`<span>${esc(t)}</span>`).join('')}</div><p class="case-owner">${esc(site.name)} · Independent portfolio project · Synthetic data</p><div class="case-actions"><a class="button primary" href="${p.demoType?'#interactive':href(p.demo||p.source)}">${p.demoType?'Try the analysis':'Open the demo'} <span aria-hidden="true">↗</span></a>${external(p.source,'View source','button')}</div></div><img src="${href(p.thumbnail)}" alt="${esc(p.name)} preview" width="760" height="500"></section>
  <nav class="case-nav" aria-label="Case study sections"><a href="#question">The question</a>${p.demoType?'<a href="#interactive">Interactive analysis</a>':''}<a href="#methodology">Method</a><a href="#validation">Validation</a><a href="#reproduce">Reproduce</a></nav>
  <section class="case-story" id="question"><h2>The question.</h2><div><p>${esc(p.problem)}</p></div></section>
  <aside class="finding"><p class="eyebrow">WHAT THE EXAMPLE SHOWS</p><p>${esc(p.finding)}</p></aside>
  ${p.demoType?`<section class="demo" id="interactive" aria-label="${esc(p.name)} interactive analysis"><div class="demo-top"><p class="eyebrow">EXPLORE THE DECISION</p><h2>${esc(p.name)}</h2><p>Adjust the controls. Inspect the trade-offs. All figures below come from the reproducible synthetic example.</p></div><div class="demo-body" id="demo-mount"><p class="loading">Loading analysis…</p></div></section>`:''}
  <section class="case-story" id="methodology"><h2>The method.</h2><div><ol>${list(p.approach)}</ol>${p.methods?.length?`<div class="method-links">${p.methods.map(m=>external(m.url,m.label)).join('')}</div>`:''}</div></section>
  <section class="case-story" id="validation"><h2>Evidence you<br>can inspect.</h2><div><ul>${list(p.validation)}</ul><p style="margin-top:20px">The source includes runnable logic and checks. These are demonstration results, not measured improvements at an employer.</p></div></section>
  <section class="case-story"><h2>Where the<br>model stops.</h2><p>${esc(p.limitations)}</p></section>
  <section class="case-story" id="reproduce"><h2>Run it yourself.</h2><div><p>Clone the repository and run from its root with Python 3.10 or later. The analytical pipelines use the standard library.</p><div class="code-box"><code id="run-command">${esc(p.run)}</code><button class="copy-button" id="copy-command" type="button">Copy</button></div><div class="case-actions">${external(p.source,'Inspect source','button')}<a class="button" href="${href(p.download)}" download>Download ${p.download.endsWith('.pdf')?'PDF':'project bundle'} ↓</a></div><p id="copy-status" aria-live="polite"></p></div></section>
  <div class="case-end"><a href="index.html#work">← All projects</a><a href="project.html?id=${encodeURIComponent(next.id)}">Next: ${esc(next.name)} →</a></div>`;
  $('copy-command').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(p.run);$('copy-status').textContent='Command copied.';}catch{$('copy-status').textContent='Select the command above and copy it.';}});
  if(p.demoType){try{await mountDemo(p.demoType,$('demo-mount'),await readJSON(p.data));}catch(error){$('demo-mount').innerHTML=`<p class="loading">The analysis could not load. Please refresh, or <a href="${href(p.source)}">inspect the source on GitHub</a>.</p>`;console.error(error);}}
}

try{const [site,projects]=await Promise.all([readJSON('site.json'),readJSON('projects.json')]);chrome(site);if($('gallery'))gallery(site,projects);else await caseStudy(site,projects);}
catch(error){const root=$('gallery')||$('case-root');if(root)root.innerHTML='<p class="loading">The portfolio could not load. Please refresh or visit <a href="https://github.com/titusrobinsonone/titusrobinsonone.github.io">the GitHub repository</a>.</p>';console.error(error);}
