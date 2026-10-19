import test from "node:test";
import assert from "node:assert/strict";
import { newSsoAttempt } from "../lib/sso.ts";
test("HTTP contexts can generate login attempts without randomUUID",()=>{
  const cryptoLike={getRandomValues(bytes){bytes.set(Array.from({length:bytes.length},(_,i)=>i));return bytes;}};
  assert.equal(newSsoAttempt(cryptoLike),"000102030405060708090a0b0c0d0e0f1011121314151617");
});
