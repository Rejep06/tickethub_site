/** Build an OFFLINE test view from the actual renderer and CSS. No Next/API server. */
import fs from 'node:fs';
import path from 'node:path';
import {loadTypeScript} from './typescript-runtime.mjs';
const ts=loadTypeScript();
const root=process.cwd();
let html=fs.readFileSync(path.join(root,'tests/fixtures/seat-renderer.html'),'utf8');
for(const name of ['tokens','foundation','experience','usability-update']){
 html=html.replace(`<link rel="stylesheet" href="/src/styles/${name}.css">`,`<style>${fs.readFileSync(path.join(root,`src/styles/${name}.css`),'utf8')}</style>`);
}
const source=fs.readFileSync(path.join(root,'src/lib/seat-viewport.ts'),'utf8');
const transpiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const exports=[...transpiled.matchAll(/export (?:function|const) (\w+)/g)].map(match=>match[1]);
const script=`const M=(()=>{${transpiled.replaceAll('export ','')};return {${exports.join(',')}};})();`;
html=html.replace("import * as M from './seat-viewport.js';",script).replace('<script type="module">','<script>');
fs.mkdirSync(path.join(root,'.test-build'),{recursive:true});
const output=path.join(root,'.test-build/map-preview.html');fs.writeFileSync(output,html);
console.log(output);console.log('Synthetic geometry; actual Canvas renderer. NOT a React/Next/Django end-to-end test.');
