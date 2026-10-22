"""Optional AUTHORING test using an already-installed Playwright + Chromium.
Not a runtime project dependency. fetch is stubbed; this is not Django/HTTP/DB
verification and the test data is not a PortalBilet fixture.
"""
import sys, json, re, shutil, os, uuid
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from venues.geometry import generate_block
api='/api/v1/staff/plans/11111111-1111-1111-1111-111111111111/'
config={'api':api,'editor_base':'/ops/venues/seatingplan/','change_url':'/ops/venues/seatingplan/test/change/'}
html=(root/'backend/venues/templates/admin/venues/editor.html').read_text()
html=html.replace('{{ editor_config|json_script:"layout-config" }}',f'<script id="layout-config" type="application/json">{json.dumps(config)}</script>')
html=html.replace('{% csrf_token %}','<input name="csrfmiddlewaretoken" type="hidden" value="ui-test-token">')
html=html.replace("{% static 'venues/editor.css' %}",'/static/venues/editor.css').replace("{% static 'venues/editor.js' %}",'/static/venues/editor.js')
html=html.replace('{{ plan.name }}','Тестовая схема').replace('{{ editor_config.change_url }}',config['change_url']).replace('{{ block.super }}','')
html=re.sub(r'{%.*?%}','',html)
html='<html><head><meta charset="utf-8"><title>UI smoke test — simulated API, not Django</title><style>body{font-family:system-ui;margin:22px;color:#243447}h1{font-size:22px}a{color:#225cc7}</style></head><body><h1>Tickethub · Редактор схемы</h1><p>Проверка интерфейса в Chromium. Тестовый HTTP API, не сервер Django.</p>'+html+'</body></html>'
preview_nodes=generate_block(sector='A',rows=8,seats_per_row=16,curve=.06)
mock="""<script>
window.testState = {plan: {id:'11111111-1111-1111-1111-111111111111',name:'Тестовая схема · без фоновой картинки',status:'DRAFT',version:1,image:null},seats:[]};
window.testRequests=[];window.testPreview=PREVIEW;let testSequence=0;
window.fetch=async(path,options={})=>{
  let data=options.body?JSON.parse(options.body):null;
  if(data)window.testRequests.push({path,body:data,csrf:options.headers['X-CSRFToken']});
  let result;
  if(path.endsWith('/preview/'))result=window.testState;
  else if(path.endsWith('/block-preview/'))result={seats:window.testPreview,count:window.testPreview.length,saved:false};
  else if(path.endsWith('/bulk-edit/')){
    if(data.expected_version!==window.testState.plan.version)throw new Error('stale version');
    let map=new Map(window.testState.seats.map(s=>[s.id,s]));
    for(const id of data.delete)map.delete(id);
    for(const s of data.update)map.set(s.id,s);
    for(const s of data.create){const id='00000000-0000-4000-8000-'+String(++testSequence).padStart(12,'0');map.set(id,{id,...s});}
    window.testState.seats=[...map.values()];window.testState.plan.version++;
    result={version:window.testState.plan.version};
  } else throw new Error('Unknown UI-test endpoint: '+path);
  return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(result))};
};</script>""".replace('PREVIEW',json.dumps(preview_nodes,default=str))
html=html.replace('<link rel="stylesheet" href="/static/venues/editor.css">','<style>'+(root/'backend/venues/static/venues/editor.css').read_text()+'</style>')
html=html.replace('<script src="/static/venues/editor.js" defer></script>',mock+'<script>'+(root/'backend/venues/static/venues/editor.js').read_text()+'</script>')
html=html.replace('Тестовый HTTP API, не сервер Django.','Тестовые ответы API, не сервер Django.')
checks=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BINARY') or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
 errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
 page.set_content(html)
 page.wait_for_function("document.getElementById('le-state').textContent.includes('v1')")
 checks.append('editor loaded without JavaScript exceptions')
 page.locator('[name=rows]').fill('8');page.locator('[name=seats_per_row]').fill('16');page.locator('[name=curve]').fill('6')
 page.locator('#le-generator button[type=submit]').click()
 page.wait_for_function("document.getElementById('le-selection').textContent.includes('128')")
 assert page.evaluate('window.testState.seats.length')==0;checks.append('generation preview creates 128 local seats without saving')
 page.locator('#le-save').click()
 page.wait_for_function("document.getElementById('le-state').textContent.includes('v2')")
 assert page.evaluate('window.testState.seats.length')==128;checks.append('Save constructs one versioned batch with 128 seats and a CSRF header (stubbed fetch)')
 page.locator('#le-sector').select_option('A');page.locator('#le-row').select_option('3');page.locator('#le-select').click()
 assert page.locator('#le-selection').inner_text()=='Выбрано: 16';checks.append('sector/row filter selects 16 seats')
 page.locator('#le-new-sector').fill('B');page.locator('#le-rename').click()
 assert page.locator('#le-dirty').inner_text()=='Не сохранено: 16';checks.append('rename changes only selected seats locally')
 page.locator('#le-undo').click()
 assert page.locator('#le-dirty').inner_text()=='Все изменения сохранены';checks.append('undo restores saved labels')
 page.locator('#le-select').click()
 before_zoom=page.locator('#le-count').inner_text()
 page.locator('#le-canvas').hover();page.mouse.wheel(0,-250)
 page.wait_for_timeout(100)
 assert before_zoom != page.locator('#le-count').inner_text()
 checks.append('canvas zoom works')
 page.locator('#le-row').select_option('3');page.locator('#le-select').click()
 page.evaluate("document.querySelector('.le-sidebar').scrollTop=0")
 page.screenshot(path=str(root/'docs/assets/editor-ui-smoke.png'),full_page=True)
 assert not errors,errors
 assert page.evaluate('window.testRequests.every(r => r.path.endsWith("/") && r.csrf === "ui-test-token")')
 checks.append('all mutation paths retain trailing slash and CSRF header')
 browser.close()
report={'scope':'Real Chromium UI with stubbed fetch responses, NOT Django/HTTP/DB verification', 'checks':checks,'passed':len(checks),'javascript_errors':errors}
(root/'docs/verification/additions/browser-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
