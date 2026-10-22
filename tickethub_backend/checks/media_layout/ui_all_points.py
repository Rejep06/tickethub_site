"""Optional local Playwright smoke check. Uses captured geometry and STUBBED API responses."""
import json
import re
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
from external_events.normalization import normalize_layout,normalize_assigned_tickets

root=Path(__file__).resolve().parents[2]
# Accept an explicit capture path for authoring, not a runtime dependency.
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--capture',type=Path,required=True)
args=parser.parse_args()
layout=normalize_layout(json.loads((args.capture/'coordinates.json').read_text()),expected_layout_id='3513')
decoded=normalize_assigned_tickets(json.loads((args.capture/'tickets-402328.json').read_text()),event_date_id='402328',layout=layout)
labels={(s['x'],s['y']):s for s in decoded['seats']}
seats=[]
for i,(x,y) in enumerate(layout['points']):
    info=labels.get((x,y),{})
    seats.append({'id':str(i),'plan':'test','x':x,'y':y,'sector':info.get('sector',''),
        'row':info.get('row',''),'number':info.get('number',''),
        'labels_known':bool(info),'external_point_key':'ui-only-'+str(i)})
state={'plan':{'id':'test','name':'Все места из capture PortalBilet','status':'DRAFT','version':1,
    'image':None,'external_width':layout['width'],'external_height':layout['height'],
    'external_geometry':layout['points'],'external_sectors':[]},'seats':seats}
config={'api':'/api/v1/staff/plans/test/','editor_base':'/ops/venues/seatingplan/','change_url':'#'}
html=(root/'backend/venues/templates/admin/venues/editor.html').read_text()
html=html.replace('{{ editor_config|json_script:"layout-config" }}',f'<script id="layout-config" type="application/json">{json.dumps(config)}</script>')
html=html.replace('{% csrf_token %}','<input name="csrfmiddlewaretoken" type="hidden" value="test">')
html=html.replace("{% static 'venues/editor.css' %}",'ui.css').replace("{% static 'venues/editor.js' %}",'ui.js')
html=html.replace('{{ block.super }}','').replace('{{ plan.name }}','PortalBilet capture').replace('{{ editor_config.change_url }}','#')
html=re.sub(r'{%.*?%}','',html)
html=html.replace('<link rel="stylesheet" href="ui.css">','<style>'+(root/'backend/venues/static/venues/editor.css').read_text()+'</style>')
mock='<script>window.testState='+json.dumps(state,ensure_ascii=False)+';window.fetch=async()=>({ok:true,json:async()=>window.testState});'
mock+='let arc=CanvasRenderingContext2D.prototype.arc,clear=CanvasRenderingContext2D.prototype.clearRect;window.arcCount=0;CanvasRenderingContext2D.prototype.arc=function(...a){window.arcCount++;return arc.apply(this,a)};CanvasRenderingContext2D.prototype.clearRect=function(...a){window.arcCount=0;return clear.apply(this,a)};</script>'
html=html.replace('<script src="ui.js" defer></script>',mock+'<script>'+(root/'backend/venues/static/venues/editor.js').read_text()+'</script>')
checks=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1500,'height':1050})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_content('<html><head><meta charset="utf-8"></head><body>'+html+'</body></html>')
    page.wait_for_function("document.getElementById('le-count').textContent.includes('12075')")
    page.wait_for_timeout(150)
    text=page.locator('#le-count').inner_text()
    assert '9966' in text,text
    checks.append('All 12,075 points and 9,966 unknown labels displayed in editor counter')
    assert page.evaluate('window.arcCount')==12075,page.evaluate('window.arcCount')
    checks.append('Exactly 12,075 point circles drawn, no duplicate ghost layer')
    page.locator('#le-select').click()
    assert page.locator('#le-selection').inner_text()=='Выбрано: 0'
    checks.append('Provider geometry excluded from accidental group edits')
    assert not errors,errors
    checks.append('No browser JavaScript exceptions')
    out=root/'docs/verification/media-layout';out.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(out/'all-points-smoke.png'),full_page=True)
    browser.close()
    result={'scope':'Real Chromium canvas, captured coordinates, mocked API, NOT Django/PostgreSQL test',
        'checks':checks,'passed':len(checks),'javascript_errors':errors}
    (out/'all-points-browser.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
