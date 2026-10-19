/** The full-page SDK owns its document; keep it out of the forum's React tree. */
export type SdkPageConfig = { slug: string; title: string; enabled: boolean; provider: "hiagent"; base_url: string; sdk_url: string; app_key: string };

export function sdkDocument(config: SdkPageConfig): string {
  const { base_url: baseUrl, app_key: appKey } = config;
  const sdk = new URL(config.sdk_url);
  if (sdk.protocol !== "https:" || sdk.username || sdk.password || sdk.hash) throw new Error("Invalid SDK URL");
  const base = new URL(baseUrl);
  if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash || base.pathname !== "/") {
    throw new Error("HiAgent base URL must be an HTTPS origin");
  }
  if (!appKey.trim()) throw new Error("HiAgent app key is required");
  // Escape '<' even in JSON strings so configuration cannot close a script tag.
  const json = (value: unknown) => JSON.stringify(value).replace(/</g, "\\u003c");
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{margin:0;width:100%;height:100%;background:#fff}#sdk-status{padding:32px;text-align:center;font:14px system-ui;color:#656d76}</style>
</head><body><div id="sdk-status" role="status">正在连接智能问答…</div><script>
const statusEl=document.getElementById('sdk-status');
let settled=false;
function fail(){settled=true;statusEl.hidden=false;statusEl.textContent='智能问答暂时无法加载，请检查网络后点击上方“重新加载”。';}
const timer=setTimeout(()=>{if(!settled)fail();},20000);
const script=document.createElement('script');
script.src=${json(sdk.href)};
script.onerror=()=>{clearTimeout(timer);fail();};
script.onload=()=>{clearTimeout(timer);try{
  new HiagentWebSDK.WebClient(${json({ appKey: appKey.trim(), baseUrl: base.origin, hideSidebar: false, variables: {} })});
  settled=true;statusEl.hidden=true;
}catch(error){fail();}};
document.body.appendChild(script);
</script></body></html>`;
}
