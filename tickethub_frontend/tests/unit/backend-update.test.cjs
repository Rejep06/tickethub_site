const {test,beforeEach,after}=require('node:test');
const assert=require('node:assert/strict');
const {lib,json}=require('./helpers.cjs');
const {api,readResponse}=lib('api/client');
const errors=lib('api/error-details'), E=lib('seat-editor'), images=lib('image-upload');
const {editorApi}=lib('api/editor');
const {externalEventsApi,portalBiletUrl}=lib('api/external-events');
const realFetch=global.fetch;
beforeEach(()=>{ global.document={documentElement:{lang:'ru'}}; });
after(()=>{global.fetch=realFetch;delete global.document;});
const saved=(id='seat-1', patch={})=>({id,plan:'plan-1',sector:'A',row:'1',number:'1',x:'0.200000',y:'0.300000',adjacency_group:'',adjacency_position:null,...patch});
const original=()=>E.seatDrafts([saved()]);

test('Django array validation details survive error normalization',async()=>{
 await assert.rejects(()=>readResponse(json({code:'VALIDATION_ERROR',message:'Invalid',details:['Изображение слишком большое.']},400)),e=>e.details.non_field_errors[0]==='Изображение слишком большое.');
});
test('Nested field errors are visible without printing raw objects',()=>{
 assert.deepEqual(errors.errorDetails({image:['Bad PNG'],create:[{x:['Out of bounds']}] }),[{field:'image',message:'Bad PNG'},{field:'create.1.x',message:'Out of bounds'}]);
 assert.equal(errors.fieldError({rights_source:['Required']},'rights_source'),'Required');
 assert.equal(errors.errorFieldLabel('image','ru'),'Изображение');
});
test('Unknown validation data is bounded and empty objects are not errors',()=>{
 assert.deepEqual(errors.errorDetails({}),[]); assert.deepEqual(errors.normalizeDetails(null),{});
 assert.equal(errors.errorDetails({a:Array(100).fill('x')}).length,40);
});
test('5xx responses never expose backend details or tracebacks',async()=>{
 await assert.rejects(()=>readResponse(json({code:'INTERNAL_ERROR',message:'SECRET',details:{trace:['SECRET']}},500)),e=>e.message==='API_UNAVAILABLE'&&Object.keys(e.details).length===0);
});
test('413 upload errors have a meaningful error code even for an HTML proxy response',async()=>{
 await assert.rejects(()=>readResponse(new Response('too large',{status:413})),e=>e.code==='REQUEST_TOO_LARGE');
});
test('Request id can also come from the HTTP header',async()=>{
 await assert.rejects(()=>readResponse(json({},400,{'X-Request-ID':'from-header'})),e=>e.requestId==='from-header');
});
for(const [name,bytes,type] of [
 ['png',[137,80,78,71,13,10,26,10],'image/png'],['jpeg',[255,216,255,224],'image/jpeg'],
 ['webp',[82,73,70,70,0,0,0,0,87,69,66,80],'image/webp']
])test(`Image signature recognises ${name}, independent of extension`,async()=>{assert.equal(await images.checkImageHeader(new Blob([new Uint8Array(bytes)])),type);});
test('Static SVG is detected from contents even with a PNG extension',async()=>{
 const file=new File(['<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'],'renamed.png',{type:'image/png'});
 assert.equal(await images.checkImageHeader(file),'image/svg+xml');
});
test('Rejects zero-length and oversized image files',async()=>{
 await assert.rejects(()=>images.checkImageHeader(new Blob([])),e=>!!e.details.image);
 await assert.rejects(()=>images.checkImageHeader({size:images.MAX_IMAGE_BYTES+1}),e=>e.details.image[0].includes('100 МиБ'));
});
test('Unknown binary image formats are not sent as renamed PNGs',async()=>{await assert.rejects(()=>images.checkImageHeader(new Blob(['GIF89a'])),e=>!!e.details.image);});
for(const [w,h] of [[20001,100],[20000,20000],[0,10],[NaN,5],[-2,2]])test(`Image bounds reject ${w} x ${h}`,()=>{assert.throws(()=>images.checkImageDimensions(w,h));});
test('Exact server image dimensions limit is accepted',()=>{images.checkImageDimensions(20000,15000);});
const selection=()=>({file:new File([new Uint8Array([137,80,78,71,13,10,26,10])],'cover.png',{type:'image/png'}),rightsSource:' My photo ',rightsConfirmed:true});
test('Multipart cover upload has exactly the four backend fields',()=>{
 const form=images.imageFormData(selection(),7);assert.deepEqual([...form.keys()],['image','rights_source','rights_confirmed','expected_version']);
 assert.equal(form.get('rights_source'),'My photo');assert.equal(form.get('rights_confirmed'),'true');assert.equal(form.get('expected_version'),'7');assert.ok(form.get('image') instanceof File);
});
for(const patch of [{rightsSource:''},{rightsConfirmed:false},{rightsSource:'x'.repeat(501)}])test('Cover upload validates required rights fields',()=>{assert.throws(()=>images.imageFormData({...selection(),...patch},7));});
test('Cover upload rejects unknown/invalid record version',()=>{assert.throws(()=>images.imageFormData(selection(),NaN));assert.throws(()=>images.imageFormData(selection(),0));});
test('Read and write normalized coordinates do not create false edits',()=>{
 const old=original(),next=old.map(seat=>({...seat,x:'0.2',y:'0.30'}));assert.equal(E.changeCount(E.planChanges(old,next,2)),0);
});
test('Bulk edit contains exact expected version, creates, updates, deletes',()=>{
 const old=E.seatDrafts([saved(),saved('seat-2',{number:'2'})]);const add=E.newSeatDrafts([{sector:'B',row:'2',number:'3',x:.5,y:.5}],()=> 'new');
 const diff=E.planChanges(old,[{...old[0],number:'7'},...add],8);
 assert.equal(diff.expected_version,8);assert.equal(diff.update[0].id,'seat-1');assert.deepEqual(diff.delete,['seat-2']);assert.equal(diff.create.length,1);
 assert.equal('id' in diff.create[0],false);assert.equal('plan' in diff.create[0],false);assert.equal('key' in diff.create[0],false);
});
test('Unknown seat ids cannot be included in a bulk mutation',()=>{assert.throws(()=>E.planChanges(original(),[{...original()[0],id:'foreign'}],1),/INVALID_SEAT_ID/);});
test('Duplicate place identities are rejected before a save',()=>{const a=E.newSeatDrafts([{sector:'A',row:'1',number:'1',x:.2,y:.2},{sector:'A',row:'1',number:'1',x:.3,y:.3}],(()=>{let i=0;return()=>String(i++);})());assert.throws(()=>E.validateSeats(a),/DUPLICATE_SEAT/);});
test('Whitespace-only labels and non-finite coordinates are rejected',()=>{assert.throws(()=>E.normalizeSeat({sector:' ',row:'1',number:'1',x:.5,y:.5}));assert.throws(()=>E.coordinate(Infinity));assert.throws(()=>E.coordinate(''));});
test('Plan size is capped at 50,000 seats',()=>{assert.throws(()=>E.validateSeats(Array(50001).fill(original()[0])),/PLAN_LIMIT/);});
test('Bulk save count boundary and no-op are checked',()=>{
 const diff={expected_version:1,create:Array(2000).fill({}),update:[],delete:[]};E.assertBatch(diff);assert.throws(()=>E.assertBatch({...diff,create:Array(2001).fill({})}),/BATCH_LIMIT/);assert.throws(()=>E.assertBatch({...diff,create:[]}),/BATCH_LIMIT/);
});
test('Geometry changes clear all affected adjacency groups, not just the moved seat',()=>{
 const old=E.seatDrafts([saved('a',{adjacency_group:'g',adjacency_position:0}),saved('b',{number:'2',adjacency_group:'g',adjacency_position:1})]);
 const next=E.clearAffectedAdjacency(old,[{...old[0],x:'0.4'},old[1]]);assert.ok(next.every(seat=>seat.adjacency_group===''&&seat.adjacency_position===null));
});
test('Deleting a seat clears the surviving adjacency group',()=>{
 const old=E.seatDrafts([saved('a',{adjacency_group:'g',adjacency_position:0}),saved('b',{number:'2',adjacency_group:'g',adjacency_position:1})]);assert.equal(E.clearAffectedAdjacency(old,[old[1]])[0].adjacency_group,'');
});
test('Transforms do not mutate originals or silently clamp out-of-bounds seats',()=>{
 const old=original(),next=E.transformSeats(old,new Set(['seat-1']),{dx:.1,dy:.1});assert.equal(next[0].x,'0.300000');assert.equal(old[0].x,'0.200000');assert.throws(()=>E.transformSeats(old,new Set(['seat-1']),{dx:1}),/INVALID_GEOMETRY/);
});
test('Horizontal mirroring preserves center and swaps x positions',()=>{
 const old=E.seatDrafts([saved('a'),saved('b',{number:'2',x:'.8'})]);const next=E.transformSeats(old,new Set(['a','b']),{flipX:true});assert.equal(next[0].x,'0.800000');assert.equal(next[1].x,'0.200000');
});
test('Rotation accounts for canvas aspect ratio',()=>{
 const old=E.seatDrafts([saved('a',{x:'.4',y:'.5'}),saved('b',{number:'2',x:'.6',y:'.5'})]);const next=E.transformSeats(old,new Set(['a','b']),{angle:90,aspect:1.6});assert.equal(next[0].x,'0.500000');assert.equal(next[0].y,'0.340000');assert.equal(next[1].y,'0.660000');
});
test('Rectangle selection works in either drag direction',()=>{const s=original();assert.deepEqual(E.selectRectangle(s,{x:.3,y:.4},{x:.1,y:.2}),['seat-1']);});
test('CSV exports real geometry, escaped delimiters, and neutralizes formulas',()=>{
 const csv=E.seatsCsv([{...original()[0],sector:'=RUN()',row:'A,"B"'}]);assert.ok(csv.startsWith('\uFEFFsector,row,number,x,y'));assert.ok(csv.includes('"\'=RUN()"'));assert.ok(csv.includes('"A,""B"""'));assert.ok(csv.includes('"0.200000"'));
});
for(const url of ['https://portalbilet.ru/sochi/my-event','https://www.portalbilet.ru/sochi/my_event?utm=x#top'])test(`Provider URL accepts supported form ${url}`,()=>{assert.match(portalBiletUrl(url),/^https:\/\/portalbilet.ru\/sochi\/my[-_]event$/);});
for(const url of ['http://portalbilet.ru/a/b','https://evil.test/a/b','https://portalbilet.ru.evil.test/a/b','https://user@portalbilet.ru/a/b','https://portalbilet.ru/a/b/c','https://portalbilet.ru/a/%62','https://portalbilet.ru/a/b\\c','https://portalbilet.ru/a/../b'])test(`Provider URL rejects unsupported form ${url}`,()=>{assert.equal(portalBiletUrl(url),null);});
for(const [call,path,body] of [
 [(id)=>editorApi.blockPreview(id,{sector:'A',rows:2,seats_per_row:3}),'block-preview',{sector:'A',rows:2,seats_per_row:3}],
 [(id)=>editorApi.csvPreview(id,'sector,row,number,x,y'),'csv-preview',{text:'sector,row,number,x,y'}],
 [(id)=>editorApi.save(id,{expected_version:9,create:[],update:[],delete:['a']}),'bulk-edit',{expected_version:9,create:[],update:[],delete:['a']}]
])test(`New editor ${path} sends CSRF, slash and the original body`,async()=>{
 let seen;global.fetch=async(url,init)=>{if(url.endsWith('/csrf/'))return json({csrf_token:'fresh'});seen={url,init};return json({});};await call('p');assert.equal(seen.url,`/api/v1/staff/plans/p/${path}/?lang=ru`);assert.equal(seen.init.headers.get('X-CSRFToken'),'fresh');assert.deepEqual(JSON.parse(seen.init.body),body);
});
test('Import sends IMPORT_ONLY, never MIRROR or a pretend live sale',async()=>{
 let seen;global.fetch=async(url,init)=>{if(url.endsWith('/csrf/'))return json({csrf_token:'fresh'});seen={url,init};return json({status:'PARTIAL',created:{events:[],seats:0,ticket_units:0}});};
 const report=await externalEventsApi.import('https://portalbilet.ru/a/b');assert.equal(report.status,'PARTIAL');assert.deepEqual(JSON.parse(seen.init.body),{provider:'portalbilet',mode:'IMPORT_ONLY',url:'https://portalbilet.ru/a/b'});assert.equal(seen.url,'/api/v1/staff/external-events/import/?lang=ru');
});
test('Sync sends an empty JSON object and canonical path',async()=>{
 let seen;global.fetch=async(url,init)=>{if(url.endsWith('/csrf/'))return json({csrf_token:'fresh'});seen={url,init};return json({});};await externalEventsApi.sync('source');assert.equal(seen.url,'/api/v1/staff/external-events/source/sync/?lang=ru');assert.equal(seen.init.body,'{}');
});
test('Import failure is not automatically retried',async()=>{
 let calls=0;global.fetch=async(url)=>{if(url.endsWith('/csrf/'))return json({csrf_token:'fresh'});calls++;throw new TypeError('offline');};await assert.rejects(()=>externalEventsApi.import('https://portalbilet.ru/a/b'),e=>e.code==='NETWORK_ERROR');assert.equal(calls,1);
});
test('API operation timers are bounded',async()=>{await assert.rejects(()=>api('me/',{timeoutMs:Infinity}));await assert.rejects(()=>api('me/',{timeoutMs:0}));});
