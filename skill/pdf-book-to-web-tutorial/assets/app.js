(function(){
  const $ = (s,el=document)=>el.querySelector(s);
  const $$ = (s,el=document)=>Array.from(el.querySelectorAll(s));

  /* ---------- 主题 / 字号 ---------- */
  const root=document.documentElement;
  const lsGet=k=>{try{return localStorage.getItem(k)}catch(e){return null}};
  const lsSet=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
  const savedTheme=lsGet('book-theme');
  if(savedTheme) root.dataset.theme=savedTheme;
  const savedFs=lsGet('book-fs');
  if(savedFs) root.style.setProperty('--fs',savedFs+'px');
  $('#themeBtn').addEventListener('click',()=>{
    const next=root.dataset.theme==='night'?'paper':'night';
    root.dataset.theme=next; lsSet('book-theme',next);
    $('#themeBtn').classList.toggle('on',next==='night');
  });
  if(root.dataset.theme==='night') $('#themeBtn').classList.add('on');
  function bumpFs(d){
    let cur=parseFloat(getComputedStyle(root).getPropertyValue('--fs'))||17;
    cur=Math.min(21,Math.max(14,cur+d));
    root.style.setProperty('--fs',cur+'px'); lsSet('book-fs',cur);
  }
  $('#fontPlus').addEventListener('click',()=>bumpFs(1));
  $('#fontMinus').addEventListener('click',()=>bumpFs(-1));

  /* ---------- 移动端目录 ---------- */
  const menuBtn=$('#menuBtn');
  menuBtn.addEventListener('click',()=>document.body.classList.toggle('nav-open'));
  $$('.nav-link').forEach(a=>a.addEventListener('click',()=>document.body.classList.remove('nav-open')));
  document.addEventListener('click',e=>{
    if(document.body.classList.contains('nav-open') && !e.target.closest('.sidebar') && !e.target.closest('#menuBtn')) document.body.classList.remove('nav-open');
  });

  /* ---------- 进度 / 目录高亮 ---------- */
  const sections=$$('section[id]');
  const navLinks=$$('.nav-link');
  const bar=$('#progressBar'), pct=$('#pct'), pctSide=$('#pctSide'), ringFg=$('#ringFg');
  const CIRC=2*Math.PI*14;
  let scrollTimer=null;
  function updateScroll(){
    const st=window.scrollY||document.documentElement.scrollTop;
    const h=document.documentElement.scrollHeight-window.innerHeight;
    const p=h>0?Math.min(1,Math.max(0,st/h)):0;
    bar.style.width=(p*100)+'%';
    const v=Math.round(p*100)+'%';
    pct.textContent=v; pctSide.textContent=v;
    ringFg.style.strokeDashoffset=String(CIRC*(1-p));
    let active=sections[0]?.id;
    for(const s of sections){
      if(s.getBoundingClientRect().top<=200) active=s.id;
    }
    navLinks.forEach(a=>a.classList.toggle('active',a.dataset.sec===active));
    const activeLink=navLinks.find(a=>a.classList.contains('active'));
    if(activeLink){
      const crumb=$('#crumb');
      const clone=activeLink.cloneNode(true);
      clone.querySelector('.nav-num')?.remove();
      crumb.innerHTML='<b>'+clone.textContent.trim()+'</b>';
    }
  }
  window.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(updateScroll,55);},{passive:true});
  window.addEventListener('scrollend',updateScroll);
  updateScroll();

  /* ---------- 证明展开/收起 ---------- */
  let proofsOpen=false;
  $('#proofBtn').addEventListener('click',()=>{
    proofsOpen=!proofsOpen;
    $$('details.proof').forEach(d=>d.open=proofsOpen);
    $('#proofBtn').classList.toggle('on',proofsOpen);
    toast(proofsOpen?'已展开全部证明':'已收起全部证明');
  });

  /* ---------- 搜索 ---------- */
  const panel=$('#searchPanel'), input=$('#searchInput'), results=$('#searchResults'), hint=$('#searchHint');
  const index=[];
  sections.forEach(sec=>{
    const title=sec.querySelector('h2')?.textContent.trim()||sec.id;
    const chap=sec.querySelector('.sec-label')?.textContent.trim()||'';
    index.push({id:sec.id,title,chap,text:sec.textContent.replace(/\s+/g,' ').trim(),el:sec});
    $$('.thm',sec).forEach(t=>{
      const tt=t.querySelector('.thm-title')?.textContent.trim();
      if(tt) index.push({id:sec.id,title:tt,chap,text:t.textContent.replace(/\s+/g,' ').trim(),el:t});
    });
  });
  let searchTimer=null;
  function doSearch(q){
    q=q.trim();
    results.innerHTML='';
    if(q.length<1){hint.textContent='输入关键词，搜索全书概念、定理与例子';return;}
    const lower=q.toLowerCase();
    const hits=index.filter(it=>it.text.toLowerCase().includes(lower));
    hits.sort((a,b)=>{
      const at=a.title.toLowerCase().includes(lower)?0:1;
      const bt=b.title.toLowerCase().includes(lower)?0:1;
      return at-bt;
    });
    hits.splice(18);
    hint.textContent=hits.length?`找到 ${hits.length} 条相关结果`:'没有找到匹配；试试“定理”“定义”“例子”';
    hits.forEach(it=>{
      const a=document.createElement('a');
      a.className='search-result'; a.href='#'+it.id;
      const i=it.text.toLowerCase().indexOf(lower);
      const start=Math.max(0,i-38), end=Math.min(it.text.length,i+q.length+80);
      let snip=it.text.slice(start,end).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      snip=snip.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),m=>'<mark>'+m+'</mark>');
      a.innerHTML=`<div class="sr-title"><span class="sr-chap">${escapeHtml(it.chap)}</span>${escapeHtml(it.title)}</div><div class="sr-snip">…${snip}…</div>`;
      a.addEventListener('click',e=>{
        e.preventDefault();
        it.el.scrollIntoView({behavior:'smooth',block:'start'});
        panel.classList.remove('open');
        it.el.classList.add('flash');
        setTimeout(()=>it.el.classList.remove('flash'),1400);
      });
      results.appendChild(a);
    });
  }
  function escapeHtml(s){return s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  input.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>doSearch(input.value),120);});
  input.addEventListener('focus',()=>{panel.classList.add('open');doSearch(input.value);});
  document.addEventListener('click',e=>{
    if(!panel.contains(e.target)&&e.target!==input) panel.classList.remove('open');
  });
  document.addEventListener('keydown',e=>{
    if(e.key==='/'&&document.activeElement!==input){e.preventDefault();input.focus();input.select();}
    if(e.key==='Escape'){panel.classList.remove('open');input.blur();document.body.classList.remove('nav-open');}
  });

  /* ---------- 自测 ---------- */
  $$('[data-quiz]').forEach(q=>{
    $$('button',q).forEach(btn=>{
      btn.addEventListener('click',()=>{
        $$('button',q).forEach(b=>b.disabled=true);
        const ok=btn.dataset.correct==='true';
        btn.classList.add(ok?'good':'bad');
        if(!ok){$$('button',q).find(b=>b.dataset.correct==='true')?.classList.add('good');}
        const exp=q.querySelector('.quiz-exp');
        if(exp) exp.classList.add('show');
      });
    });
  });

  /* ---------- 回顶 / toast ---------- */
  $('#topBtn').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
  let toastTimer=null;
  function toast(msg){
    const t=$('#toast'); t.textContent=msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer=setTimeout(()=>t.classList.remove('show'),1600);
  }

  /* ---------- 出现动画 ---------- */
  const io=new IntersectionObserver(entries=>{
    entries.forEach(en=>{if(en.isIntersecting){en.target.classList.add('in');io.unobserve(en.target);}});
  },{rootMargin:'0px 0px -8% 0px',threshold:.05});
  $$('.chapter').forEach(el=>{el.classList.add('reveal');io.observe(el);});
})();
