import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { sdkDocument } from "../lib/sdk-pages.ts";
const hiagentDocument = (base_url, app_key) => sdkDocument({base_url, app_key, sdk_url: "https://agent.example/resources/product/llm/public/sdk/embedFull.js"});

test("embed uses configured HTTPS platform and escapes script-closing input", () => {
  const html = hiagentDocument("https://agent.example", '</script><script>alert(1)</script>');
  assert.ok(html.includes("https://agent.example/resources/product/llm/public/sdk/embedFull.js"));
  assert.equal((html.match(/<\/script>/g) || []).length, 1);
  assert.ok(html.includes('"hideSidebar":false'));
  assert.ok(html.includes('"variables":{}'));
});

test("embed rejects invalid configuration", () => {
  for (const url of ["http://agent.example", "javascript:alert(1)", "https://user:pass@agent.example", "https://agent.example/path"]) {
    assert.throws(() => hiagentDocument(url, "app"));
  }
  assert.throws(() => hiagentDocument("https://agent.example", ""));
});

test("SDK bootstrap initializes once on load and shows a readable failure", () => {
  const html = hiagentDocument("https://agent.example", "application");
  const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
  const status = { hidden: false, textContent: "" };
  const script = {};
  let options;
  vm.runInNewContext(code, {
    document: { getElementById: () => status, createElement: () => script, body: { appendChild() {} } },
    setTimeout() {}, clearTimeout() {},
    HiagentWebSDK: { WebClient: function (value) { options = value; } },
  });
  script.onload();
  assert.equal(options.appKey, "application");
  assert.equal(options.baseUrl, "https://agent.example");
  assert.equal(status.hidden, true);
  script.onerror();
  assert.equal(status.hidden, false);
  assert.match(status.textContent, /无法加载/);
});
