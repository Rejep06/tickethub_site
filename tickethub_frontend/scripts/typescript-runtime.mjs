import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
const require=createRequire(import.meta.url);
export function loadTypeScript(){
  try{return require('typescript');}
  catch{
    try{return require(path.join(execFileSync('npm',['root','-g'],{encoding:'utf8'}).trim(),'typescript'));}
    catch{throw new Error('TypeScript is required. Run npm install before running this script.');}
  }
}
