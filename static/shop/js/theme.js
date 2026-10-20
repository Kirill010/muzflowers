(function(){var r=document.documentElement,b=document.getElementById('th');
try{var t=localStorage.getItem('mzt');if(t)r.dataset.theme=t}catch(e){}
if(b)b.onclick=function(){var d=(r.dataset.theme||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'))==='dark'?'light':'dark';r.dataset.theme=d;try{localStorage.setItem('mzt',d)}catch(e){}}})();
