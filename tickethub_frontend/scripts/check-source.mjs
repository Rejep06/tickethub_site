/** Syntax/local imports only. This does NOT replace tsc, Next build or installed library types. */
import fs from 'node:fs';
import path from 'node:path';
import {loadTypeScript} from './typescript-runtime.mjs';
const ts=loadTypeScript(),root=process.cwd(),files=[];
function walk(dir){for(const item of fs.readdirSync(dir)){const file=path.join(dir,item);if(fs.statSync(file).isDirectory())walk(file);else if(/\.tsx?$/.test(file))files.push(file);}}
walk(path.join(root,'src'));walk(path.join(root,'tests'));
for(const file of ['next.config.ts','vitest.config.ts','playwright.config.ts'])files.push(path.join(root,file));
let errors=0;const exports=new Map();
for(const file of files){
 const source=fs.readFileSync(file,'utf8'),parsed=ts.createSourceFile(file,source,ts.ScriptTarget.Latest,true),names=new Set();
 for(const node of parsed.statements){
  if(node.modifiers?.some(m=>m.kind===ts.SyntaxKind.ExportKeyword)){
   if(node.name)names.add(node.name.text);
   if(node.declarationList)for(const declaration of node.declarationList.declarations)if(declaration.name.text)names.add(declaration.name.text);
  }
  if(ts.isExportDeclaration(node)&&node.exportClause)for(const item of node.exportClause.elements??[])names.add(item.name.text);
 }
 exports.set(file,names);
 const result=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX},reportDiagnostics:true,fileName:file});
 for(const diagnostic of result.diagnostics??[])if(diagnostic.category===ts.DiagnosticCategory.Error){console.error(file,ts.flattenDiagnosticMessageText(diagnostic.messageText,' '));errors++;}
}
for(const file of files){
 const parsed=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true);
 for(const node of parsed.statements){
  if(!ts.isImportDeclaration(node))continue;
  const name=node.moduleSpecifier.text;if(!name.startsWith('@/')&&!name.startsWith('.'))continue;
  const base=name.startsWith('@/')?path.join(root,'src',name.slice(2)):path.resolve(path.dirname(file),name);
  const resolved=[base,base+'.ts',base+'.tsx',base+'.json',base+'/index.ts',base+'/index.tsx'].find(f=>fs.existsSync(f)&&fs.statSync(f).isFile());
  if(!resolved){console.error('Missing local module',file,name);errors++;continue;}
  const names=exports.get(resolved);if(!names)continue;
  for(const item of node.importClause?.namedBindings?.elements??[])if(!names.has((item.propertyName??item.name).text)){console.error('Missing named export',file,name,item.name.text);errors++;}
 }
}
console.log(`${files.length} TypeScript sources: ${errors} syntax/local-import errors. External libraries NOT type-checked.`);
process.exitCode=errors?1:0;
