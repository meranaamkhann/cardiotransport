const f=document.getElementById('f'),site=document.getElementById('site'),prev=document.getElementById('prev'),out=document.getElementById('out');
site.onchange=()=>{if(site.value)prev.value=site.value;else prev.select()};
f.onsubmit=async e=>{e.preventDefault();out.textContent='Calculating...';
 try{const r=await fetch('/predict',{method:'POST',body:new FormData(f)});if(!r.ok)throw 0;show(await r.json())}
 catch{out.textContent='Could not compute. Check that every required field has a number.'}};
const pct=x=>(x*100).toFixed(1)+'%';
function show(d){const mx=Math.max(...d.contributions.map(c=>Math.abs(c.effect)),.01);
 out.innerHTML=`<div class="pair"><div><div class="muted">Adjusted to target population</div><div class="big">${pct(d.adjusted)}</div></div>
 <div><div class="muted">Raw (Cleveland-calibrated)</div><div class="big" style="color:#4d6a6f">${pct(d.raw)}</div></div>
 <div><div class="muted">Random forest (raw)</div><div class="big" style="color:#4d6a6f">${pct(d.rf)}</div></div></div>
 <p class="muted">Model: ${d.model}. Target prevalence ${(d.target_prev*100).toFixed(1)}%.</p>
 <h2>What moved the estimate</h2>${d.contributions.map(c=>`<div class="bar"><span>${c.feature}</span><i style="width:${Math.abs(c.effect)/mx*140}px;background:${c.effect>0?'#b04030':'#0e6b73'}"></i>${c.effect>0?'+':''}${c.effect}</div>`).join('')}
 <p class="muted">Red raises, teal lowers the log-odds.</p>${d.flags.map(x=>`<div class="flag">${x}</div>`).join('')}<p class="muted">${d.disclaimer}</p>`}
