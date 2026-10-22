const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const base = process.env.TH_TEST_BUILD;
const I = require(path.join(base, 'lib/image-upload.js'));
const M = require(path.join(base, 'lib/seat-viewport.js'));
const A = require(path.join(base, 'lib/auth-state.js'));
const {ApiError, api} = require(path.join(base, 'lib/api/client.js'));
const near = (a, b, epsilon=1e-7) => assert.ok(Math.abs(a-b)<epsilon, `${a} != ${b}`);
const pointNear = (a,b) => {near(a.x,b.x);near(a.y,b.y);};
function png(w,h) { const b = new Uint8Array(32); b.set([137,80,78,71,13,10,26,10]); b.set([73,72,68,82],12); const v=new DataView(b.buffer);v.setUint32(16,w);v.setUint32(20,h);return b; }
function jpeg(w,h) { return new Uint8Array([255,216,255,224,0,4,0,0,255,192,0,11,8,h>>8,h&255,w>>8,w&255,1,1,0x11,0,255,217]); }
function sized(bytes, size) {const blob=new Blob([bytes]);return {size,slice:(a,b)=>blob.slice(a,b)};}
const sampleSeat = (id,x,y,sector='A',row='1',number='1') => ({id,x,y,sector,row,number});
const world={width:1000,height:625}, view={width:1000,height:600};
const dense=()=>M.buildSeatModel(Array.from({length:80},(_,i)=>sampleSeat(`s${i}`, .3+(i%20)*.005,.25+Math.floor(i/20)*.008,'A',String(Math.floor(i/20)+1),String(i%20+1))),1.6);

test('Image limits exactly match the supplied October backend contract',()=>{
 assert.equal(I.MAX_IMAGE_BYTES,104857600);assert.equal(I.MAX_SVG_BYTES,10485760);assert.equal(I.MAX_IMAGE_SIDE,20000);assert.equal(I.MAX_IMAGE_PIXELS,300000000);
});
for(const [w,h] of [[20000,15000],[15000,20000],[8001,5000],[20000,1]])test(`Image dimension boundary accepts ${w} × ${h}`,()=>I.checkImageDimensions(w,h));
for(const [w,h] of [[20000,15001],[15001,20000],[20000,20000],[1,20001],[Infinity,1]])test(`Side AND area limits reject ${w} × ${h}`,()=>assert.throws(()=>I.checkImageDimensions(w,h),e=>e.code==='VALIDATION_ERROR'&&!!e.details.image));
test('100 MiB raster allowed, next byte rejected before reading',async()=>{
 assert.equal(await I.checkImageHeader(sized(png(100,100),I.MAX_IMAGE_BYTES)),'image/png');
 await assert.rejects(()=>I.checkImageHeader({size:I.MAX_IMAGE_BYTES+1,slice(){throw new Error('Must not read oversized input');}}),e=>e.details.image[0].includes('100'));
});
test('10 MiB SVG allowed, next byte rejected, independent of raster limit',async()=>{
 const text='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20000 15000"></svg>';
 assert.equal(await I.checkImageHeader(sized(text,I.MAX_SVG_BYTES)),'image/svg+xml');
 await assert.rejects(()=>I.checkImageHeader(sized(text,I.MAX_SVG_BYTES+1)),e=>e.details.image[0].includes('10 МиБ'));
});
test('BOM, XML declaration and comments before SVG root are recognised',async()=>{
 const file=new File(['\ufeff<?xml version="1.0"?>\n<!-- exported -->\n<svg xmlns="http://www.w3.org/2000/svg"/>'],'plan.svg');
 assert.equal((await I.inspectImage(file)).type,'image/svg+xml');
});
test('SVG is never locally rendered, even if it contains a script: server must sanitize',async()=>{
 const result=await I.inspectImage(new File(['<svg><script>alert(1)</script></svg>'],'plan.svg'));
 assert.equal(result.previewSafe,false);assert.equal(result.width,null);
});
test('HTML with an embedded SVG is not treated as a direct image',async()=>{
 await assert.rejects(()=>I.checkImageHeader(new Blob(['<html><svg></svg></html>'])),e=>!!e.details.image);
});
for(const [type,bytes] of [['image/png',png(20000,15000)],['image/jpeg',jpeg(20000,15000)]])test(`Reads 300 MP ${type} metadata without allocating pixels`,async()=>{
 const file=new File([bytes],'large');const size=await I.rasterDimensions(file,type);assert.deepEqual(size,{width:20000,height:15000});
 const info=await I.inspectImage(file);assert.equal(info.previewSafe,false);assert.equal(info.width,20000);
});
test('Header preflight rejects a 400 MP PNG before upload',async()=>assert.rejects(()=>I.inspectImage(new File([png(20000,20000)],'too-big.png')),e=>e.details.image[0].includes('300')));
test('Small raster is eligible for a preview, pixel data remains untouched',async()=>{
 const file=new File([png(1600,900)],'poster.png');const bytes=await file.arrayBuffer();assert.equal((await I.inspectImage(file)).previewSafe,true);assert.deepEqual(await file.arrayBuffer(),bytes);
});
test('WebP VP8X dimensions are read from its 24-bit header',async()=>{
 const b=new Uint8Array(30);b.set([82,73,70,70,0,0,0,0,87,69,66,80,86,80,56,88]);
 for(const [offset,n] of [[24,19999],[27,14999]]){b[offset]=n&255;b[offset+1]=(n>>8)&255;b[offset+2]=(n>>16)&255;}
 assert.deepEqual(await I.rasterDimensions(new Blob([b]),'image/webp'),{width:20000,height:15000});
});
test('Truncated JPEG returns no dimensions, rather than attempting pixel decode',async()=>{
 assert.equal(await I.rasterDimensions(new Blob([[255,216,255].toString()]),'image/jpeg'),null);
});
const urlSelection = () => ({mode:'url',imageUrl:' https://cdn.example.test/a.svg?token=abc ',rightsSource:' Организатор ',rightsConfirmed:true});
test('URL payload contains ONLY image_url and the three existing control fields',()=>{
 assert.deepEqual(I.imageRequestBody(urlSelection(),9),{image_url:'https://cdn.example.test/a.svg?token=abc',expected_version:9,rights_source:'Организатор',rights_confirmed:true});
});
for(const value of ['http://example.test/a.png','javascript:alert(1)','data:image/png;base64,A','https://user:password@example.test/a.png','https://example.test/a.png#x','https://example.test/a\\b','https://example.test/a b','relative.png',''])test(`URL preflight rejects unsupported address ${value}`,()=>assert.throws(()=>I.imageUrl(value),e=>!!e.details.image_url));
test('File mode never includes image_url; URL mode cannot be passed to multipart function',()=>{
 const file=new File([png(20,20)],'small.png');const form=I.imageRequestBody({file,rightsSource:'Фото',rightsConfirmed:true},4);
 assert.ok(form instanceof FormData);assert.equal(form.has('image_url'),false);assert.equal(form.get('image'),file);
 assert.throws(()=>I.imageFormData(urlSelection(),4));
});
test('JSON image import uses CSRF and a canonical slash path, without a file field',async()=>{
 const original=global.fetch, calls=[];
 global.fetch=async(url,init)=>{calls.push({url,init});return new Response(JSON.stringify(url.endsWith('/csrf/')?{csrf_token:'fresh'}:{version:10}),{status:200,headers:{'Content-Type':'application/json'}});};
 try {await api('staff/events/e/image/',{method:'POST',body:I.imageRequestBody(urlSelection(),9),timeoutMs:I.IMAGE_UPLOAD_TIMEOUT_MS});
 assert.equal(calls[0].url,'/api/v1/auth/csrf/');assert.equal(calls[1].url,'/api/v1/staff/events/e/image/?lang=ru');
 assert.equal(calls[1].init.headers.get('X-CSRFToken'),'fresh');assert.equal(calls[1].init.headers.get('Content-Type'),'application/json');assert.equal(calls[1].init.credentials,'include');
 assert.equal(JSON.parse(calls[1].init.body).image_url,'https://cdn.example.test/a.svg?token=abc');} finally {global.fetch=original;}
});

test('Guest authentication and CSRF failures are not conflated',()=>{
 assert.equal(A.isAuthRequired(new ApiError(401,'AUTH_REQUIRED','')) ,true);
 assert.equal(A.isAuthRequired(new ApiError(403,'AUTH_REQUIRED','')),true);
 assert.equal(A.isAuthRequired(new ApiError(403,'CSRF_FAILED','')),false);
 assert.equal(A.isAuthRequired(new ApiError(403,'FORBIDDEN','')),false);
 assert.equal(A.isAuthRequired(new TypeError('offline')),false);
});
test('Validation and guest errors do not expose a support UUID',()=>{
 assert.equal(A.supportReference(new ApiError(400,'VALIDATION_ERROR','',{},'uuid')),null);
 assert.equal(A.supportReference(new ApiError(401,'AUTH_REQUIRED','',{},'uuid')),null);
});
test('Unexpected error reference stays available for the collapsed support panel',()=>{
 assert.equal(A.supportReference(new ApiError(503,'API_UNAVAILABLE','',{},'2e6362b4-3e56-4473-bb75-5f37d56d4240')),'2e6362b4-3e56-4473-bb75-5f37d56d4240');
 assert.equal(A.supportReference(new ApiError(500,'API_UNAVAILABLE','',{},'<script>bad</script>')),null);
 assert.equal(A.supportReference(new Error('raw error')),null);
});

test('Whole-venue fit preserves aspect and fits both viewport dimensions',()=>{
 const camera=M.fitCamera(world,view), a=M.worldToScreen({x:0,y:0},camera), b=M.worldToScreen({x:1000,y:625},camera);
 assert.ok(a.x>=23.9&&a.y>=23.9&&b.x<=view.width-23.9&&b.y<=view.height-23.9);
 near((b.x-a.x)/(b.y-a.y),1.6);
});
test('Camera transform round trip',()=>{const c={x:-373,y:59,scale:3.25};pointNear(M.screenToWorld(M.worldToScreen({x:225,y:390},c),c),{x:225,y:390});});
test('Cursor zoom anchors the same world point, not viewport center',()=>{
 const camera=M.zoomAt(M.fitCamera(world,view),{x:500,y:300},4,world,view), cursor={x:430,y:240};
 const before=M.screenToWorld(cursor,camera), after=M.zoomAt(camera,cursor,1.5,world,view);pointNear(M.screenToWorld(cursor,after),before);
});
test('Zoom clamps to fit and maximum, ignoring invalid factors',()=>{
 const c=M.fitCamera(world,view), center={x:500,y:300};
 near(M.zoomAt(c,center,0.000001,world,view).scale,c.scale);
 near(M.zoomAt(c,center,1e6,world,view).scale,c.scale*M.MAX_MAP_ZOOM);
 assert.equal(M.zoomAt(c,center,NaN,world,view),c);assert.equal(M.zoomAt(c,center,-2,world,view),c);
});
test('Pinch scales AND follows moving midpoint',()=>{
 const camera=M.zoomAt(M.fitCamera(world,view),{x:500,y:300},3,world,view);
 const before=[{x:450,y:300},{x:550,y:300}],now=[{x:430,y:320},{x:630,y:320}];
 const next=M.pinchCamera(camera,before,now,world,view);near(next.scale,camera.scale*2);
 pointNear(M.screenToWorld({x:530,y:320},next),M.screenToWorld({x:500,y:300},camera));
});
test('Coincident touch points cannot create Infinity or NaN scale',()=>{
 const c=M.pinchCamera(M.fitCamera(world,view),[{x:5,y:5},{x:5,y:5}],[{x:10,y:10},{x:15,y:15}],world,view);
 assert.ok(Number.isFinite(c.scale)&&Number.isFinite(c.x)&&Number.isFinite(c.y));
});
test('Resize preserves the world focus and relative zoom when not edge-clamped',()=>{
 const c=M.zoomAt(M.fitCamera(world,view),{x:500,y:300},6,world,view), small={width:390,height:420};
 const after=M.resizeCamera(c,view,small,world);
 pointNear(M.screenToWorld({x:195,y:210},after),M.screenToWorld({x:500,y:300},c));
 near(after.scale/M.fitCamera(world,small).scale,6);
});
test('A resize at overview remains a whole-venue fit',()=>{
 const small={width:390,height:420};assert.deepEqual(M.resizeCamera(M.fitCamera(world,view),view,small,world),M.fitCamera(world,small));
});
test('Sector fit is derived from actual seat coordinates without changing geometry',()=>{
 const model=dense(),snapshot=JSON.stringify(model.seats.map(p=>p.seat));
 const camera=M.fitCamera(model.world,view,model.sectors[0].bounds,60);
 assert.ok(camera.scale>M.fitCamera(model.world,view).scale*3);assert.equal(JSON.stringify(model.seats.map(p=>p.seat)),snapshot);
});
test('Overview dots stay smaller than local spacing; numbers become possible only close up',()=>{
 const model=dense(),c=M.fitCamera(model.world,view),p=model.seats[25];
 assert.ok(M.markerRadius(p,c)<3);assert.ok(M.markerRadius(p,c)*2<p.spacing*c.scale);assert.equal(M.canInspectSeat(p,c),false);
 const close=M.zoomAt(c,M.worldToScreen(p,c),10,model.world,view);assert.ok(M.markerRadius(p,close)>=7);assert.ok(M.canInspectSeat(p,close));
});
test('Expanded target areas select the nearest center, never a random overlapping circle',()=>{
 const model=M.buildSeatModel([sampleSeat('a',.50,.5),sampleSeat('b',.51,.5)]), c={x:-500,y:-300,scale:4};
 const b=M.worldToScreen(model.byId.get('b'),c);assert.equal(M.nearestSeat(model,{x:b.x-4,y:b.y},c,24).seat.id,'b');
});
test('Nearest-seat lookup includes unavailable geometry and honours filters',()=>{
 const model=M.buildSeatModel([sampleSeat('blocked',.5,.5,'A','1'),sampleSeat('other',.52,.5,'B','2')]);
 const c=M.fitCamera(model.world,view), at=M.worldToScreen(model.byId.get('blocked'),c);
 assert.equal(M.nearestSeat(model,at,c,30).seat.id,'blocked');assert.equal(M.nearestSeat(model,at,c,30,'B','2').seat.id,'other');
 assert.equal(M.nearestSeat(model,at,c,30,'C'),null);
});
test('Exact overlapping coordinates are flagged for list selection instead of moving places',()=>{
 const model=M.buildSeatModel([sampleSeat('a',.5,.5),sampleSeat('b',.5,.5)]);assert.ok(model.seats.every(p=>p.coincident));
 assert.equal(M.canInspectSeat(model.seats[0],{x:0,y:0,scale:100}),false);
});
test('Bad geometry is skipped; coordinates of 0 and 1 are valid',()=>{
 const model=M.buildSeatModel([sampleSeat('zero',0,0),sampleSeat('one','1','1'),sampleSeat('empty','','.5'),sampleSeat('outside',2,.5),sampleSeat('nan',NaN,.5)]);
 assert.equal(model.invalidCount,3);assert.deepEqual(model.seats.map(p=>p.seat.id),['zero','one']);
});
test('Empty map has finite camera geometry and no fake seats',()=>{const m=M.buildSeatModel([],0);assert.equal(m.seats.length,0);assert.equal(M.boundsOf([]),null);assert.ok(Number.isFinite(M.fitCamera(m.world,view).scale));});
test('Grid viewport query agrees with a direct geometric filter',()=>{
 const model=dense(),bounds={minX:315,minY:155,maxX:342,maxY:180};
 assert.deepEqual(M.querySeats(model,bounds).map(p=>p.seat.id).sort(),model.seats.filter(p=>p.x>=315&&p.x<=342&&p.y>=155&&p.y<=180).map(p=>p.seat.id).sort());
});
test('Extreme source aspect ratio does not iterate millions of empty cells',()=>{
 const model=M.buildSeatModel([sampleSeat('a',.5,.5)],1/20000);assert.equal(M.querySeats(model,{minX:0,minY:0,maxX:1000,maxY:model.world.height}).length,1);
});
test('Spatial model handles 50,000 test places and culls offscreen positions',()=>{
 const seats=Array.from({length:50000},(_,i)=>sampleSeat(String(i),(i%250)/250,Math.floor(i/250)/200,String(Math.floor(i/5000)),String(Math.floor(i/250))));
 const model=M.buildSeatModel(seats);assert.equal(model.seats.length,50000);assert.equal(model.invalidCount,0);
 const visible=M.querySeats(model,{minX:400,minY:200,maxX:500,maxY:300});assert.ok(visible.length>0&&visible.length<2500);
});
