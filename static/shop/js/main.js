document.documentElement.classList.add('js');
const $=s=>document.querySelector(s),R=n=>n.toLocaleString('ru-RU')+' ₽';
const P=JSON.parse(document.getElementById('mz-products').textContent),CFG=JSON.parse(document.getElementById('mz-config').textContent);
const fl=(a,b,k,c)=>{let s='';for(let i=0;i<k;i++)s+=`<ellipse cx="50" cy="26" rx="10" ry="23" fill="${esc(i%2?a:b)}" opacity=".92" transform="rotate(${i*360/k} 50 50)"/>`;return `<svg viewBox="0 0 100 100" ${c?'class="hf"':''} aria-hidden="true">${s}<circle cx="50" cy="50" r="9" fill="#f6c94c"/></svg>`};
let cart={},cat='Все',q='',so='pop',promo=false,pct=0,code='';
try{cart=JSON.parse(localStorage.getItem('mz')||'{}')}catch(e){}
Object.keys(cart).forEach(i=>{if(!P.some(p=>p.id==i))delete cart[i]});
const ck=n=>(document.cookie.match('(^|;)\\s*'+n+'=([^;]+)')||[])[2],esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
post=(u,b)=>fetch(u,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':ck('csrftoken')},body:JSON.stringify(b)}).then(r=>r.json()),
pic=p=>p.img?`<img src="${esc(p.img)}" alt="${esc(p.n)}" loading="lazy">`:fl(p.a,p.b,p.k);
const save=()=>{try{localStorage.setItem('mz',JSON.stringify(cart))}catch(e){}};
const toast=m=>{const t=$('#ts');t.textContent=m;t.classList.add('on');clearTimeout(toast.h);toast.h=setTimeout(()=>t.classList.remove('on'),1800)};

$('#hf').innerHTML=fl('#ff9ebb','#e0587c',16,1);
for(let i=0;i<14;i++){const s=document.createElement('span'),z=10+Math.random()*16;s.className='pt';s.style.cssText=`left:${Math.random()*100}%;width:${z}px;height:${z}px;animation-duration:${9+Math.random()*10}s;animation-delay:-${Math.random()*15}s`;$('#pts').append(s)}

const cats=['Все',...new Set(P.map(p=>p.c))];
$('#chips').innerHTML=cats.map(c=>`<button class="ch" aria-pressed="${c==='Все'}">${esc(c)}</button>`).join('')+
'<input id="sq" type="search" placeholder="Поиск букета" aria-label="Поиск"><select id="so" aria-label="Сортировка"><option value="pop">Популярные</option><option value="lo">Сначала дешевле</option><option value="hi">Сначала дороже</option></select>';
$('#chips').addEventListener('click',e=>{const b=e.target.closest('.ch');if(!b)return;cat=b.textContent;document.querySelectorAll('.ch').forEach(x=>x.setAttribute('aria-pressed',x===b));grid()});
$('#sq').oninput=e=>{q=e.target.value.toLowerCase();grid()};$('#so').onchange=e=>{so=e.target.value;grid()};

function grid(){let l=P.filter(p=>(cat==='Все'||p.c===cat)&&(p.n+p.d).toLowerCase().includes(q));
if(so==='lo')l.sort((a,b)=>a.p-b.p);if(so==='hi')l.sort((a,b)=>b.p-a.p);
$('#gr').innerHTML=l.length?l.map((p,i)=>`<article class="cd" style="animation-delay:${i*60}ms"><div class="ph" style="--a:${esc(p.a)}">${p.t?`<span class="bd">${esc(p.t)}</span>`:''}${pic(p)}</div><div class="cb"><h3>${esc(p.n)}</h3><p>${esc(p.d)}</p><div class="pr"><b>${R(p.p)}</b><button class="btn sm" data-id="${p.id}">В корзину</button></div></div></article>`).join(''):'<p class="em">Ничего не нашли — попробуйте другой запрос 🌱</p>'}
$('#gr').addEventListener('click',e=>{const b=e.target.closest('[data-id]');if(!b)return;const id=b.dataset.id;cart[id]=(cart[id]||0)+1;save();draw();toast('Добавлено в корзину 💐')});

const FREE=CFG.free,DEL=CFG.delivery;
function draw(){const ids=Object.keys(cart).filter(i=>cart[i]>0),n=ids.reduce((s,i)=>s+cart[i],0);
$('#cc').textContent=n;$('#cc').classList.remove('bp');void $('#cc').offsetWidth;$('#cc').classList.add('bp');
const has=ids.length>0;$('#sum').hidden=$('#fm').hidden=!has;
$('#items').innerHTML=has?ids.map(i=>{const p=P.find(x=>x.id==i);return `<div class="it">${pic(p)}<div>${esc(p.n)}<small>${R(p.p)}</small></div><div class="q"><button data-m="${i}" aria-label="Меньше">−</button>${cart[i]}<button data-p="${i}" aria-label="Больше">+</button></div></div>`}).join(''):'<p class="em">Корзина пуста. Самое время выбрать букет 🌸</p>';
if(!has)return;
const sub=ids.reduce((s,i)=>s+P.find(x=>x.id==i).p*cart[i],0),ds=promo?Math.round(sub*pct/100):0,dl=sub-ds>=FREE?0:DEL,left=FREE-(sub-ds);
$('#sum').innerHTML=`<div>${left>0?`До бесплатной доставки <b>${R(left)}</b>`:'🎉 Доставка бесплатная'}</div><div class="bar"><i style="width:${Math.min(100,(sub-ds)/FREE*100)}%"></i></div>
<div class="pc"><input id="pi" placeholder="Промокод" value="${promo?code:''}" aria-label="Промокод"><button class="btn gh sm" id="pa">Применить</button></div>
<div class="ln"><span>Товары</span><span>${R(sub)}</span></div>${ds?`<div class="ln"><span>Скидка ${pct}%</span><span>−${R(ds)}</span></div>`:''}
<div class="ln"><span>Доставка</span><span>${dl?R(dl):'бесплатно'}</span></div><div class="ln t"><span>Итого</span><span>${R(sub-ds+dl)}</span></div>`;
$('#pa').onclick=async()=>{const c=$('#pi').value.trim(),r=await post(CFG.promoUrl,{code:c}).catch(()=>({}));promo=!!r.ok;pct=r.percent||0;code=promo?c.toUpperCase():'';toast(promo?'Промокод применён ✨':'Такого промокода нет');draw()}}
$('#items').addEventListener('click',e=>{const m=e.target.dataset.m,p=e.target.dataset.p;if(m)cart[m]=Math.max(0,cart[m]-1);if(p)cart[p]++;if(m||p){save();draw()}});

const dr=$('#dr'),ov=$('#ov'),open=v=>{dr.classList.toggle('on',v);ov.classList.toggle('on',v)};
$('#cb').onclick=()=>open(1);$('#cx').onclick=ov.onclick=()=>open(0);addEventListener('keydown',e=>e.key==='Escape'&&open(0));
$('#dt').min=new Date().toISOString().slice(0,10);
$('#fm').onsubmit=async e=>{e.preventDefault();const f=e.target,btn=f.querySelector('button');btn.disabled=true;
try{const r=await post(CFG.orderUrl,{name:$('#nm').value,phone:$('#ph').value,address:$('#ad').value,date:$('#dt').value,slot:$('#tm').value,note:$('#nt').value,consent:$('#cs').checked,promo:promo?code:'',items:Object.keys(cart).filter(i=>cart[i]>0).map(i=>({id:+i,qty:cart[i]}))});
if(!r.ok)throw new Error(r.error);
$('#ok').innerHTML=`<span>💐</span><h3>Спасибо, ${esc($('#nm').value)}!</h3><p>Заказ №${r.number} принят. Мы позвоним для подтверждения и пришлём фото букета перед доставкой.</p><button class="btn" id="ob">Отлично</button>`;
cart={};promo=false;pct=0;code='';save();draw();$('#items').hidden=true;$('#ok').hidden=false;f.reset();
$('#ob').onclick=()=>{$('#ok').hidden=true;$('#items').hidden=false;open(0)}}
catch(err){toast(err.message||'Не удалось отправить заказ. Попробуйте ещё раз')}finally{btn.disabled=false}};

const root=document.documentElement;
try{const t=localStorage.getItem('mzt');if(t)root.dataset.theme=t}catch(e){}
$('#th').onclick=()=>{const d=(root.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'))==='dark'?'light':'dark';root.dataset.theme=d;try{localStorage.setItem('mzt',d)}catch(e){}};

const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}}),{threshold:.15});
document.querySelectorAll('.r').forEach(el=>io.observe(el));
grid();draw();
