(() => {
  'use strict';
  const config=JSON.parse(document.getElementById('pb-config').textContent);
  const el=id=>document.getElementById(id);
  let busy=false;
  async function run(preview) {
    if(busy||!el('pb-form').reportValidity())return;
    busy=true;el('pb-preview').disabled=true;el('pb-import').disabled=true;
    el('pb-status').textContent='Получение данных источника…';el('pb-result').replaceChildren();
    try {
      const response=await fetch(preview?config.preview_url:config.import_url,{
        method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json',
          'X-CSRFToken':document.querySelector('#pb-form [name=csrfmiddlewaretoken]').value},
        body:JSON.stringify({provider:'portalbilet',url:el('pb-url').value,mode:'IMPORT_ONLY'})
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(`${data.code||response.status}: ${data.message||'Ошибка импорта'}`);
      el('pb-status').textContent=preview?'Предпросмотр получен.':data.status==='PARTIAL'?'Частичный импорт. Прочитайте ограничения ниже.':`Результат: ${data.status}`;
      if(data.title){const heading=document.createElement('h2');heading.textContent=data.title;el('pb-result').append(heading);}
      for(const id of data.created?.events||[]){const p=document.createElement('p'),a=document.createElement('a');
        a.href=config.event_admin_base+encodeURIComponent(id)+'/change/';a.textContent='Открыть созданный черновик события';p.append(a);el('pb-result').append(p);}
      for(const warning of data.warnings||[]){const p=document.createElement('p');p.textContent=`${warning.code}: ${warning.message}`;el('pb-result').append(p);}
      const details=document.createElement('details'),summary=document.createElement('summary'),pre=document.createElement('pre');
      summary.textContent='Полный результат';pre.textContent=JSON.stringify(data,null,2);pre.style.overflow='auto';details.append(summary,pre);el('pb-result').append(details);
    } catch(error){el('pb-status').textContent=error.message;}
    finally{busy=false;el('pb-preview').disabled=false;el('pb-import').disabled=false;}
  }
  el('pb-form').addEventListener('submit',e=>{e.preventDefault();run(true);});
  el('pb-import').addEventListener('click',()=>run(false));
})();
