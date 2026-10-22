import fs from 'node:fs';
import path from 'node:path';
const root=process.cwd();
const ru=JSON.parse(fs.readFileSync('src/messages/ru.json','utf8'));
const en=JSON.parse(fs.readFileSync('src/messages/en.json','utf8'));
let errors=[];const keys=[...new Set([...Object.keys(ru),...Object.keys(en)])];
const placeholders=s=>[...new Set([...s.matchAll(/\{(\w+)(?:\}|,)/g)].map(m=>m[1]))].sort().join(',');
for(const key of keys){if(typeof ru[key]!=='string'||typeof en[key]!=='string')errors.push(`Missing translation: ${key}`);else if(placeholders(ru[key])!==placeholders(en[key]))errors.push(`Mismatched parameters: ${key}`);}
function walk(dir){for(const name of fs.readdirSync(dir)){const file=path.join(dir,name);if(fs.statSync(file).isDirectory())walk(file);else if(/\.(tsx?|jsx?)$/.test(file)){const source=fs.readFileSync(file,'utf8');for(const match of source.matchAll(/\bt\(['"]([^'"]+)['"]\s*(?=[,)])/g)){if(!(match[1] in ru))errors.push(`${file}: missing ${match[1]}`);}}}}
walk(path.join(root,'src'));
if(errors.length){console.error(errors.join('\n'));process.exit(1);}
console.log(`RU/EN: ${keys.length} matching keys, matching ICU parameter names, all literal t() keys present.`);
