import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveAutoSso } from '../lib/auto-sso.ts';
const response=(body,status=200)=>new Response(JSON.stringify(body),{status});
const memory=()=>{const values=new Map();return {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v)};};
test('enabled anonymous visit starts once, back/refresh does not loop',async()=>{
 const store=memory();const fetcher=async u=>response(u.includes('site-config')?{auto_sso_login:true}:{enabled:true});
 assert.equal(await resolveAutoSso('https://community.test/',null,store,fetcher,()=>{}),'sso');
 assert.equal(await resolveAutoSso('https://community.test/',null,store,()=>assert.fail('no retry'),()=>{}),'stay');
});
test('disabled default never probes IAM',async()=>{
 let calls=0;assert.equal(await resolveAutoSso('https://community.test/',null,memory(),async()=>{calls++;return response({});},()=>{}),'stay');assert.equal(calls,1);
});
test('manual, error, callback, and explicit entry paths bypass automation',async()=>{
 for(const p of ['/login?local=1','/login?sso_error=1','/login?sso_ok=1','/sso-entry'])
  assert.equal(await resolveAutoSso('https://community.test'+p,null,memory(),()=>assert.fail('no fetch'),()=>{}),'stay');
});
test('manual login bypass persists across navigation',async()=>{
 const s=memory();await resolveAutoSso('https://community.test/login?local=1',null,s,()=>assert.fail(),()=>{});
 assert.equal(await resolveAutoSso('https://community.test/',null,s,()=>assert.fail(),()=>{}),'stay');
});
test('valid local token skips SSO, expired token clears before SSO',async()=>{
 for(const status of [200,401]){
  let cleared=false;
  const result=await resolveAutoSso('https://community.test/','token',memory(),async u=>u.endsWith('/me')?response({id:7},status):response(u.includes('site-config')?{auto_sso_login:true}:{enabled:true}),()=>{cleared=true;});
  assert.equal(result,status===200?'stay':'sso');assert.equal(cleared,status===401);
 }
});
test('network/service failures and storage denial preserve login form and token',async()=>{
 for(const fetcher of [async()=>{throw Error('offline')},async()=>response({},503)])
  assert.equal(await resolveAutoSso('https://community.test/','token',memory(),fetcher,()=>assert.fail('keep token')),'stay');
 assert.equal(await resolveAutoSso('https://community.test/',null,{getItem(){throw Error('denied')}},()=>assert.fail(),()=>{}),'stay');
});
