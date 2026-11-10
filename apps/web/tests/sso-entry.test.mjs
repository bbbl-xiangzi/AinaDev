import test from "node:test";
import assert from "node:assert/strict";
import { resolveSsoEntry } from "../lib/sso.ts";

const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
test("valid session enters home without starting another SSO login", async () => {
  assert.equal(await resolveSsoEntry("token", async (url, init) => {
    assert.equal(url, "/api/auth/me");
    assert.equal(init.headers.Authorization, "Bearer token");
    return response({ id: 1 });
  }, () => assert.fail("must preserve session")), "home");
});
test("expired session is cleared and starts SSO", async () => {
  let cleared = false;
  assert.equal(await resolveSsoEntry("expired", async url =>
    url.endsWith("/me") ? response({}, 401) : response({ enabled: true }),
  () => { cleared = true; }), "sso");
  assert.equal(cleared, true);
});
test("anonymous visitor starts SSO only when enabled", async () => {
  assert.equal(await resolveSsoEntry(null, async () => response({ enabled: true }), () => {}), "sso");
  await assert.rejects(resolveSsoEntry(null, async () => response({ enabled: false }), () => {}), /尚未启用/);
});
test("server failures do not clear credentials or trigger SSO", async () => {
  await assert.rejects(resolveSsoEntry("token", async () => response({}, 503),
    () => assert.fail("must preserve session")), /验证失败/);
});
test("malformed user and status failures stop navigation", async () => {
  await assert.rejects(resolveSsoEntry("token", async () => response({}), () => {}), /验证失败/);
  await assert.rejects(resolveSsoEntry(null, async () => response({}, 500), () => {}), /不可用/);
});
test("cancelled effect cannot clear the session or choose a destination", async () => {
  const controller = new AbortController();
  await assert.rejects(resolveSsoEntry("token", async () => {
    controller.abort();
    return response({}, 401);
  }, () => assert.fail("cancelled"), controller.signal), { name: "AbortError" });
});
