import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {loadTypeScript} from './typescript-runtime.mjs';
const ts=loadTypeScript();
const root=process.cwd();
const modules=['promotions','checkout-policy','money','datetime','safe','drafts','catalog','consents','geometry','order-actions','pending-hold','theme','api/url','api/generated','api/client','api/attempts','api/endpoints','api/editor','api/external-events','api/error-details','seat-editor','image-upload','auth-state','seat-viewport','analytics-preference'];
const output=path.join(root,'.test-build');fs.rmSync(output,{recursive:true,force:true});
const program=ts.createProgram(modules.map(m=>path.join(root,'src/lib/'+m+'.ts')),{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,moduleResolution:ts.ModuleResolutionKind.Node10,strict:true,skipLibCheck:true,types:[],lib:['lib.es2022.d.ts','lib.dom.d.ts','lib.dom.iterable.d.ts'],rootDir:path.join(root,'src'),outDir:output});
const diagnostics=ts.getPreEmitDiagnostics(program);
if(diagnostics.length){console.error(ts.formatDiagnosticsWithColorAndContext(diagnostics,{getCanonicalFileName:f=>f,getCurrentDirectory:()=>root,getNewLine:()=> '\n'}));process.exit(1);}
program.emit();
console.log(`Strict domain-module type check passed (${modules.length} modules; TypeScript ${ts.version}). This is NOT an application build.`);
const files=fs.readdirSync(path.join(root,'tests/unit')).filter(f=>f.endsWith('.test.cjs')).map(f=>path.join(root,'tests/unit',f));
if(!files.length)throw new Error('No unit tests were found.');
const result=spawnSync(process.execPath,['--test',...files],{stdio:'inherit',env:{...process.env,TH_TEST_BUILD:output}});
process.exit(result.status??1);
