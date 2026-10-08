import test from "node:test";
import assert from "node:assert/strict";
import {applyDecPreset,ssoPayload} from "../lib/sso-config.ts";

test("DEC preset preserves client registration and stays disabled until reviewed",()=>{
  const cfg=applyDecPreset({client_id:"app&1",has_client_secret:true,enabled:true});
  assert.equal(cfg.enabled,false);
  assert.equal(cfg.protocol,"oauth2");
  assert.equal(cfg.client_id,"app&1");
  assert.equal(cfg.oauth_options.token_mode,"query");
  assert.equal(new URL(cfg.userinfo_endpoint).searchParams.get("client_id"),"app&1");
  assert.equal(cfg.claim_sub,"spRoleList");
  assert.equal(cfg.oauth_options.subject_mode,"single_array");
});
test("save and test payload retain empty fields and never return stored secrets",()=>{
  const payload=ssoPayload({...applyDecPreset({}),scopes:"",has_client_secret:true},"");
  assert.equal(payload.scopes,"");
  assert.equal(payload.client_secret,null);
  assert.equal(payload.has_client_secret,undefined);
  assert.equal(payload.oauth_options.pkce,false);
});
