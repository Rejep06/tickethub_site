/* The browser edits a draft locally. Only Save writes one version-checked batch. */
(() => {
  'use strict';
  const config = JSON.parse(document.getElementById('layout-config').textContent);
  const el = id => document.getElementById(id);
  const canvas = el('le-canvas'), ctx = canvas.getContext('2d'), wrap = el('le-canvas-wrap');
  const token = document.querySelector('#layout-editor [name=csrfmiddlewaretoken]').value;
  let seats = new Map(), baseline = new Map(), selected = new Set(), history = [];
  let localSequence = 0;
  let plan, background = null, busy = false, gesture = null, view = {x: 20, y: 20, scale: 0.5};
  let ghostPoints = [], sectorShapes = [];
  let world = {width: 1600, height: 1000}, drawPending = false;
  const fields = ['sector', 'row', 'number', 'x', 'y', 'adjacency_group', 'adjacency_position'];
  const known = s => Boolean(s.sector && s.row && s.number);
  const editable = s => !s.external_point_key;
  const mutable = () => plan && plan.status === 'DRAFT' && !busy;
  const seatData = s => Object.fromEntries(fields.map(k => [k, s[k]]));
  const round = n => Math.round(n * 1e6) / 1e6;
  const normal = s => ({...s, x: Number(s.x), y: Number(s.y), adjacency_group: s.adjacency_group || '', adjacency_position: s.adjacency_position ?? null});
  const compare = (a, b) => fields.every(k => a[k] === b[k]);

  function message(text, error = false) { el('le-message').textContent = text; el('le-message').dataset.error = String(error); }
  async function api(path, body) {
    const response = await fetch(config.api + path, {method: body === undefined ? 'GET' : 'POST',
      credentials: 'same-origin', headers: {'Accept': 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': token},
      body: body === undefined ? undefined : JSON.stringify(body)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(`${data.code || response.status}: ${data.message || 'Ошибка запроса.'}${data.details && Object.keys(data.details).length ? '\n' + JSON.stringify(data.details) : ''}`);
    return data;
  }
  async function task(fn) {
    if (busy) return;
    busy = true; refresh();
    try { await fn(); } catch (error) { message(error.message, true); }
    finally { busy = false; refresh(); }
  }
  function copyMap(source) { return new Map([...source].map(([k, s]) => [k, {...s}])); }
  function changes() {
    return {
      create: [...seats].filter(([id]) => !baseline.has(id)).map(([, s]) => seatData(s)),
      update: [...seats].filter(([id, s]) => baseline.has(id) && !compare(s, baseline.get(id))).map(([id, s]) => ({id, ...seatData(s)})),
      delete: [...baseline.keys()].filter(id => !seats.has(id))
    };
  }
  function dirtyCount() { const c = changes(); return c.create.length + c.update.length + c.delete.length; }
  function refresh() {
    if (!plan) return;
    const count = dirtyCount();
    el('le-name').textContent = plan.name;
    el('le-state').textContent = `${plan.status === 'DRAFT' ? 'Черновик' : 'Только просмотр'} · v${plan.version}`;
    el('le-count').textContent = `${seats.size} мест (${[...seats.values()].filter(s=>!known(s)).length} без подписи) · масштаб ${Math.round(view.scale * 100)}%`;
    el('le-selection').textContent = `Выбрано: ${selected.size}`;
    el('le-dirty').textContent = count ? `Не сохранено: ${count}` : 'Все изменения сохранены';
    for (const id of ['le-save','le-delete','le-rotate','le-mirror','le-rename','le-publish','le-csv']) el(id).disabled = !mutable();
    el('le-undo').disabled = !mutable() || history.length === 0;
    el('le-clone').disabled = busy;
    for (const element of el('le-generator').elements) element.disabled = !mutable();
    scheduleDraw();
  }
  function filters() {
    const sector = el('le-sector').value, row = el('le-row').value;
    function fill(element, values, previous) {
      element.replaceChildren(new Option('Все', ''));
      [...new Set(values)].sort((a,b) => a.localeCompare(b, 'ru', {numeric:true})).forEach(v => element.add(new Option(v,v)));
      element.value = [...element.options].some(o => o.value === previous) ? previous : '';
    }
    fill(el('le-sector'), [...seats.values()].filter(known).map(s => s.sector), sector);
    fill(el('le-row'), [...seats.values()].filter(s => known(s) && (!el('le-sector').value || s.sector === el('le-sector').value)).map(s => s.row), row);
  }
  function apply(entries) {
    if (!mutable()) return;
    if (entries.size > 2000) throw new Error('Выберите не более 2000 мест за одну операцию.');
    const candidate = new Map(seats), before = new Map();
    for (const [id, s] of entries) {
      if(seats.has(id) && !editable(seats.get(id))) throw new Error('Координаты источника защищены. Для правок создайте ручную копию схемы.');
      before.set(id, seats.has(id) ? {...seats.get(id)} : null);
      if (s === null) candidate.delete(id);
      else {
        if (!Number.isFinite(s.x) || !Number.isFinite(s.y) || s.x < 0 || s.y < 0 || s.x > 1 || s.y > 1) throw new Error('Некоторые места выходят за границы холста.');
        candidate.set(id, {...s, x:round(s.x), y:round(s.y)});
      }
    }
    if (candidate.size > 50000) throw new Error('В одной схеме допустимо до 50 000 мест.');
    const labels = new Set();
    for (const s of candidate.values()) {
      if(!known(s)) continue;
      const key = JSON.stringify([s.sector,s.row,s.number]);
      if (labels.has(key)) throw new Error(`Место ${s.sector} / ${s.row} / ${s.number} уже существует. Измените начало нумерации или сектор.`);
      labels.add(key);
    }
    seats = candidate; history.push(before); if (history.length > 20) history.shift();
    selected = new Set([...selected].filter(id => seats.has(id))); filters(); refresh();
  }
  function add(nodes) {
    const entries = new Map(nodes.map(s => { const id = 'new-' + (++localSequence); return [id, normal({...s, id})]; }));
    apply(entries); selected = new Set(entries.keys()); refresh();
  }
  function transformSelected(transform) {
    if (!selected.size) throw new Error('Сначала выделите места.');
    const values = [...selected].map(id => seats.get(id));
    const center = {x:values.reduce((a,s) => a+s.x,0)/values.length, y:values.reduce((a,s) => a+s.y,0)/values.length};
    apply(new Map(values.map(s => [s.id, transform({...s}, center)])));
  }
  const safe = fn => () => { try { fn(); } catch(e) { message(e.message,true); } finally { scheduleDraw(); } };

  function fit() {
    const width = wrap.clientWidth, height = wrap.clientHeight;
    view.scale = Math.min((width - 40)/world.width,(height - 40)/world.height);
    view.x = (width-world.width*view.scale)/2; view.y=(height-world.height*view.scale)/2; refresh();
  }
  function position(event) {
    const r=canvas.getBoundingClientRect(); return {x:event.clientX-r.left,y:event.clientY-r.top};
  }
  const toWorld = p => ({x:(p.x-view.x)/view.scale/world.width, y:(p.y-view.y)/view.scale/world.height});
  const toScreen = s => ({x:view.x+s.x*world.width*view.scale,y:view.y+s.y*world.height*view.scale});
  function hit(p) {
    let result = null, best=100;
    for (const s of seats.values()) { const sp=toScreen(s), d=(p.x-sp.x)**2+(p.y-sp.y)**2; if(d<best){best=d;result=s;} }
    return result;
  }
  function scheduleDraw() { if(!drawPending) { drawPending=true;requestAnimationFrame(draw); } }
  function draw() {
    drawPending=false;
    const w=wrap.clientWidth,h=wrap.clientHeight,dpr=window.devicePixelRatio||1;
    if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
    ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
    ctx.save();ctx.translate(view.x,view.y);ctx.scale(view.scale,view.scale);
    ctx.fillStyle='#ffffff';ctx.fillRect(0,0,world.width,world.height);
    if(background){ctx.globalAlpha=Number(el('le-opacity').value)/100;ctx.drawImage(background,0,0,world.width,world.height);ctx.globalAlpha=1;}
    if(sectorShapes.length && typeof Path2D !== 'undefined'){
      ctx.fillStyle='rgba(49,108,194,.035)';ctx.strokeStyle='rgba(49,108,194,.22)';ctx.lineWidth=Math.max(1,1/view.scale);
      for(const sector of sectorShapes){if(!sector.path)continue;try{const path=new Path2D(sector.path);ctx.fill(path);ctx.stroke(path);}catch(_){}}
    }
    if(ghostPoints.length){ctx.fillStyle='rgba(80,95,110,.32)';const r=Math.max(1.4,2.2/view.scale);
      for(const point of ghostPoints){ctx.beginPath();ctx.arc(point[0]*world.width,point[1]*world.height,r,0,Math.PI*2);ctx.fill();}}
    if(el('le-grid').checked){ctx.strokeStyle='#e0e7ef';ctx.lineWidth=1/view.scale;ctx.beginPath();
      for(let i=0;i<=20;i++){ctx.moveTo(i*world.width/20,0);ctx.lineTo(i*world.width/20,world.height);ctx.moveTo(0,i*world.height/20);ctx.lineTo(world.width,i*world.height/20);}ctx.stroke();}
    ctx.restore();
    for(const s of seats.values()){
      let p=toScreen(s);
      if(gesture?.type==='move'&&selected.has(s.id)){p.x+=gesture.dx*world.width*view.scale;p.y+=gesture.dy*world.height*view.scale;}
      if(p.x < -20 || p.x>w+20 || p.y< -20 || p.y>h+20)continue;
      const radius=Math.max(2.2,Math.min(16,6*view.scale));ctx.beginPath();ctx.arc(p.x,p.y,radius,0,Math.PI*2);
      ctx.fillStyle=selected.has(s.id)?'#ea7a24':(!known(s)?'#a5adb7':(baseline.has(s.id)?'#316cc2':'#19936a'));ctx.fill();
      if(radius>=7){ctx.fillStyle='#fff';ctx.font=`${Math.min(11,radius+1)}px system-ui`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(s.number,p.x,p.y,radius*1.8);}
    }
    if(gesture?.type==='box'){ctx.fillStyle='rgba(49,108,194,.12)';ctx.strokeStyle='#316cc2';let g=gesture;
      ctx.fillRect(g.start.x,g.start.y,g.end.x-g.start.x,g.end.y-g.start.y);ctx.strokeRect(g.start.x,g.start.y,g.end.x-g.start.x,g.end.y-g.start.y);}
  }
  async function load() {
    const data=await api('preview/');plan=data.plan;seats=new Map(data.seats.map(s=>[s.id,normal(s)]));baseline=copyMap(seats);history=[];selected.clear();
    const represented=new Set([...seats.values()].map(s=>`${round(s.x)},${round(s.y)}`));
    ghostPoints=(Array.isArray(plan.external_geometry)?plan.external_geometry:[]).filter(p=>!represented.has(`${round(p[0])},${round(p[1])}`));
    sectorShapes=Array.isArray(plan.external_sectors)?plan.external_sectors:[];
    if(plan.external_width&&plan.external_height)world={width:Number(plan.external_width),height:Number(plan.external_height)};
    const source=plan.image||plan.external_background_url;
    background=null;
    if(source){const image=new Image();image.onload=()=>{background=image;if(!plan.external_width||!plan.external_height)world={width:image.naturalWidth,height:image.naturalHeight};fit();};
      image.onerror=()=>message('Места и геометрия загружены, фон недоступен. Работаем на нейтральном холсте.');image.src=source;}
    filters();fit();message(plan.status==='DRAFT'?'Все точки схемы загружены. Серые места: источник не сообщил номер; они не продаются. Синие: подпись известна, но цвет не означает наличие. Импортированная геометрия защищена; для правок создайте копию.':'Опубликованная схема защищена от изменений. Для редактирования создайте копию.');refresh();
  }
  el('le-generator').addEventListener('submit',event=>{
    event.preventDefault();if(!mutable())return;
    // Keep network busy state separate from local apply(), which must run after it.
    const values=Object.fromEntries(new FormData(event.target));
    Object.keys(values).filter(k=>!['sector','aisles_after'].includes(k)).forEach(k=>values[k]=Number(values[k]));
    ['x','y','width','row_spacing','curve'].forEach(k=>values[k]/=100);
    values.aisles_after=values.aisles_after.trim()?values.aisles_after.split(',').map(s=>Number(s.trim())):[];
    task(async()=>{const data=await api('block-preview/',values);busy=false;add(data.seats);busy=true;message(`Добавлено в черновик ${data.count} мест. Изменения ещё не сохранены.`);});
  });
  el('le-save').onclick=()=>task(async()=>{
    const data=changes();if(!data.create.length&&!data.update.length&&!data.delete.length){message('Нет изменений.');return;}
    if(data.create.length+data.update.length+data.delete.length>2000)throw new Error('За одно сохранение допустимо до 2000 изменений. Отмените лишние действия, сохраните и продолжите.');
    await api('bulk-edit/',{expected_version:plan.version,...data});await load();message('Схема сохранена.');
  });
  el('le-undo').onclick=safe(()=>{if(!mutable()||!history.length)return;for(const [id,s]of history.pop()){if(s===null)seats.delete(id);else seats.set(id,s);}selected.clear();filters();refresh();});
  el('le-fit').onclick=fit;
  el('le-clear').onclick=()=>{selected.clear();refresh();};
  el('le-sector').onchange=filters;
  el('le-select').onclick=()=>{selected=new Set([...seats].filter(([,s])=>editable(s)&&(!el('le-sector').value||s.sector===el('le-sector').value)&&(!el('le-row').value||s.row===el('le-row').value)).map(([id])=>id));refresh();};
  el('le-delete').onclick=safe(()=>{if(selected.size&&confirm(`Удалить ${selected.size} мест из черновика?`))apply(new Map([...selected].map(id=>[id,null])));});
  el('le-rotate').onclick=safe(()=>{const a=Number(el('le-rotation').value)*Math.PI/180;transformSelected((s,c)=>{const x=(s.x-c.x)*world.width,y=(s.y-c.y)*world.height;return{...s,x:c.x+(x*Math.cos(a)-y*Math.sin(a))/world.width,y:c.y+(x*Math.sin(a)+y*Math.cos(a))/world.height};});});
  el('le-mirror').onclick=safe(()=>transformSelected((s,c)=>({...s,x:2*c.x-s.x})));
  el('le-rename').onclick=safe(()=>{const sector=el('le-new-sector').value.trim();if(!sector)throw new Error('Укажите новое имя сектора.');transformSelected(s=>({...s,sector,adjacency_group:'',adjacency_position:null}));});
  el('le-clone').onclick=()=>task(async()=>{if(dirtyCount()&&!confirm('Копия будет создана из сохранённой версии. Продолжить?'))return;
    const result=await api('clone-version/',{});window.location.assign(config.editor_base+result.id+'/editor/');});
  el('le-publish').onclick=()=>task(async()=>{if(dirtyCount())throw new Error('Сначала сохраните изменения.');if(!confirm('После публикации изменение мест возможно только в новой копии. Опубликовать?'))return;
    await api('publish/',{expected_version:plan.version});await load();});
  el('le-opacity').oninput=scheduleDraw;el('le-grid').onchange=scheduleDraw;
  el('le-csv').onchange=()=>task(async()=>{const file=el('le-csv').files[0];if(!file)return;if(file.size>512*1024)throw new Error('Максимум 512 КБ.');
    const data=await api('csv-preview/',{text:await file.text()});busy=false;add(data.seats);busy=true;el('le-csv').value='';message(`Из CSV добавлено ${data.count} мест в черновик.`);});
  el('le-export').onclick=()=>{
    const quote=v=>'"'+String(v).replaceAll('"','""')+'"';
    // Prefix formula-like labels for spreadsheet safety; do not alter the database.
    const safeLabel=v=>/^[=+\-@\t\r]/.test(String(v))?"'"+v:v;
    const text='\uFEFFsector,row,number,x,y\r\n'+[...seats.values()].filter(known).map(s=>[safeLabel(s.sector),safeLabel(s.row),safeLabel(s.number),s.x,s.y].map(quote).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([text],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download='seating-plan.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  canvas.addEventListener('wheel',event=>{event.preventDefault();const p=position(event),prev=view.scale,next=Math.max(.02,Math.min(10,prev*Math.exp(-event.deltaY*.001)));
    view.x=p.x-(p.x-view.x)*next/prev;view.y=p.y-(p.y-view.y)*next/prev;view.scale=next;refresh();},{passive:false});
  canvas.addEventListener('pointerdown',event=>{
    if(busy)return;canvas.setPointerCapture(event.pointerId);canvas.focus();const p=position(event),s=hit(p);
    if(event.button===1||event.altKey){gesture={type:'pan',start:p,x:view.x,y:view.y};return;}
    if(event.button!==0)return;
    if(s){if(event.shiftKey){if(selected.has(s.id))selected.delete(s.id);else selected.add(s.id);}
      else if(!selected.has(s.id))selected=new Set([s.id]);
      if(mutable()&&editable(s)&&selected.has(s.id))gesture={type:'move',start:toWorld(p),dx:0,dy:0};
    }else{gesture={type:'box',start:p,end:p,previous:event.shiftKey?new Set(selected):new Set()};if(!event.shiftKey)selected.clear();}refresh();
  });
  canvas.addEventListener('pointermove',event=>{
    const p=position(event);if(!gesture){const s=hit(p),tip=el('le-tooltip');tip.hidden=!s;if(s){tip.textContent=known(s)?`${s.sector} · ряд ${s.row} · место ${s.number}`:'Источник не сообщил сектор/ряд/номер. Продажа недоступна.';tip.style.left=Math.min(p.x+14,wrap.clientWidth-220)+'px';tip.style.top=Math.max(0,p.y-38)+'px';}return;}
    el('le-tooltip').hidden=true;
    if(gesture.type==='pan'){view.x=gesture.x+p.x-gesture.start.x;view.y=gesture.y+p.y-gesture.start.y;}
    if(gesture.type==='move'){const q=toWorld(p);gesture.dx=q.x-gesture.start.x;gesture.dy=q.y-gesture.start.y;}
    if(gesture.type==='box')gesture.end=p;scheduleDraw();
  });
  canvas.addEventListener('pointerup',safe(()=>{
    if(!gesture)return;const g=gesture;gesture=null;
    if(g.type==='move'&&(Math.abs(g.dx)+Math.abs(g.dy)>1e-7))transformSelected(s=>({...s,x:s.x+g.dx,y:s.y+g.dy}));
    if(g.type==='box'){selected=g.previous;for(const s of seats.values()){const p=toScreen(s);if(editable(s)&&p.x>=Math.min(g.start.x,g.end.x)&&p.x<=Math.max(g.start.x,g.end.x)&&p.y>=Math.min(g.start.y,g.end.y)&&p.y<=Math.max(g.start.y,g.end.y))selected.add(s.id);}}refresh();
  }));
  canvas.addEventListener('pointercancel',()=>{gesture=null;refresh();});
  canvas.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='z'){event.preventDefault();el('le-undo').click();}if(event.key==='Escape'){gesture=null;selected.clear();refresh();}});
  window.addEventListener('beforeunload',event=>{if(dirtyCount()){event.preventDefault();event.returnValue='';}});
  new ResizeObserver(scheduleDraw).observe(wrap);
  task(load);
})();
