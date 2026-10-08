import test from "node:test";
import assert from "node:assert/strict";
import { consumeSsoResult, safeSsoLogoutUrl } from "../lib/sso.ts";

test("SSO completion clears URL before verification and uses server user identity", async () => {
  let cleaned = false;
  const result = await consumeSsoResult("https://community.example/login?sso_ok=1#token=server-token&user_id=999&attempt=browser-attempt", () => { cleaned = true; }, async (token) => {
    assert.equal(cleaned, true);
    assert.equal(token, "server-token");
    return { id: 42, name: "employee" };
  }, "browser-attempt");
  assert.equal(result.user.id, 42);
  assert.equal(result.token, "server-token");
});

test("unverified tokens never produce a login result", async () => {
  await assert.rejects(consumeSsoResult("https://community.example/login?sso_ok=1#token=bad&attempt=browser-attempt", () => {}, async () => { throw new Error("401"); }, "browser-attempt"), /401/);
});

test("missing or duplicate token is rejected, ordinary login is untouched", async () => {
  for (const hash of ["#attempt=browser-attempt", "#token=a&token=b&attempt=browser-attempt"]) {
    await assert.rejects(consumeSsoResult("https://community.example/login?sso_ok=1" + hash, () => {}, async () => { throw new Error("must not verify"); }, "browser-attempt"), /缺少有效/);
  }
  assert.equal(await consumeSsoResult("https://community.example/login", () => { throw new Error("must not clean"); }, async () => null), null);
});

test("logout accepts only explicit HTTPS URLs", () => {
  assert.equal(safeSsoLogoutUrl("https://adapter.example/logout"), "https://adapter.example/logout");
  for (const value of ["javascript:alert(1)", "//evil.example", "http://adapter.example/logout", "https://u:p@adapter.example/logout", undefined]) {
    assert.equal(safeSsoLogoutUrl(value), "/login");
  }
});

test("a token from an unsolicited or different browser login cannot sign in", async () => {
  for (const expected of [null, "different-attempt"]) {
    let verified = false;
    await assert.rejects(consumeSsoResult("https://community.example/login?sso_ok=1#token=valid-attacker-token&attempt=attacker-attempt", () => {}, async () => {
      verified = true;
      return { id: 12 };
    }, expected));
    assert.equal(verified, false);
  }
});
