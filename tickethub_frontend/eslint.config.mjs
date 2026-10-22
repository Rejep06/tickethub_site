import {defineConfig,globalIgnores} from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';
export default defineConfig([
 ...nextVitals,...nextTypescript,
 {rules:{
  '@typescript-eslint/no-explicit-any':'error',
  '@typescript-eslint/no-unused-vars':['error',{argsIgnorePattern:'^_',varsIgnorePattern:'^_'}],
  // Draft restoration, native dialog synchronization and URL filter hydration intentionally use effects.
  // No React Compiler is configured; classic hooks rules remain enabled.
  'react-hooks/set-state-in-effect':'off',
  'react-hooks/purity':'off'
 }},
 {files:['tests/unit/**/*.cjs'],rules:{'@typescript-eslint/no-require-imports':'off'}},
 globalIgnores(['.next/**','.test-build/**','node_modules/**','docs/**','test-results/**','playwright-report/**','coverage/**','next-env.d.ts'])
]);
