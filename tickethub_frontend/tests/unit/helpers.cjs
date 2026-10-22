const path=require('node:path');
exports.lib=name=>require(path.join(process.env.TH_TEST_BUILD,'lib',name));
exports.MemoryStore=class MemoryStore{
 getItem(key){return Object.hasOwn(this,key)?this[key]:null;}
 setItem(key,value){Object.defineProperty(this,key,{value:String(value),writable:true,configurable:true,enumerable:true});}
 removeItem(key){delete this[key];}
};
exports.json=(data,status=200,headers={})=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json',...headers}});
exports.ids={event:'10000000-0000-4000-8000-000000000001',offer:'10000000-0000-4000-8000-000000000002',seat:'10000000-0000-4000-8000-000000000003',hold:'10000000-0000-4000-8000-000000000004',order:'10000000-0000-4000-8000-000000000005'};
