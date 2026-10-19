import test from "node:test";
import assert from "node:assert/strict";
import {oauthDefaults,ssoPayload} from "../lib/sso-config.ts";

test("custom provider settings survive payload construction",()=>{
  const payload=ssoPayload({client_id:"app&1",protocol:"oauth2",oauth_options:{token_mode:"query",claim_username:"account.name"}},"");
  assert.equal(payload.client_id,"app&1");
  assert.equal(payload.oauth_options.token_mode,"query");
  assert.equal(payload.oauth_options.claim_username,"account.name");
  assert.equal(payload.oauth_options.subject_mode,"string");
  assert.equal(oauthDefaults.token_mode,"form");
});
test("save and test payload retain empty fields and never return stored secrets",()=>{
  const payload=ssoPayload({protocol:"oauth2",scopes:"",has_client_secret:true},"");
  assert.equal(payload.scopes,"");
  assert.equal(payload.client_secret,null);
  assert.equal(payload.has_client_secret,undefined);
  assert.equal(payload.oauth_options.pkce,false);
});
