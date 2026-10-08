"use client";

import { useEffect, useState, type ReactNode } from "react";
import { http } from "@/lib/api";
import { oauthDefaults, ssoPayload } from "@/lib/sso-config";

const input = "w-full rounded-md border border-[#d0d7de] bg-white px-3 py-2 text-[13px] text-[#24292f] outline-none focus:border-[#0969da] focus:ring-2 focus:ring-[#0969da]/15 disabled:bg-[#f6f8fa]";
const card = "rounded-lg border border-[#d0d7de] bg-white p-4";
const secondary = "rounded-md border border-[#d0d7de] bg-white px-3 py-1.5 text-[13px] text-[#24292f] hover:bg-[#f6f8fa] disabled:opacity-60";
function Field({title,hint,children}:{title:string;hint?:string;children:ReactNode}) {
  return <label className="block min-w-0 space-y-1.5"><span className="block text-[12px] font-medium text-[#24292f]">{title}</span>{children}{hint&&<span className="block text-[12px] leading-relaxed text-[#656d76]">{hint}</span>}</label>;
}
function Section({title,description,children}:{title:string;description?:string;children:ReactNode}) {
  return <section className={card}><h3 className="text-[15px] font-semibold">{title}</h3>{description&&<p className="mt-1 text-[12px] leading-relaxed text-[#656d76]">{description}</p>}<div className="mt-4">{children}</div></section>;
}

/** Extends the existing admin form; one active enterprise connection per deployment. */
export function SsoPanel() {
  const [cfg,setCfg]=useState<any>(null);
  const [secret,setSecret]=useState("");
  const [busy,setBusy]=useState<"save"|"test"|null>(null);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [result,setResult]=useState<any>(null);
  const load=()=>http.get("/admin/sso/config").then(setCfg).catch(e=>setError(e.message||"加载失败"));
  useEffect(()=>{void load();},[]);
  const set=(patch:any)=>{setCfg((old:any)=>({...old,...patch}));setResult(null);setNotice("");};
  const opt={...oauthDefaults,...cfg?.oauth_options};
  const option=(patch:any)=>set({oauth_options:{...opt,...patch}});
  const oauth=cfg?.protocol==="oauth2";
  const text=(key:string,placeholder="")=><input className={input} value={cfg[key]||""} onChange={e=>set({[key]:e.target.value})} placeholder={placeholder}/>;
  const optText=(key:string,placeholder="")=><input className={input} value={opt[key]||""} onChange={e=>option({[key]:e.target.value})} placeholder={placeholder}/>;
  const choose=(key:string,choices:[string,string][],onChange?:(v:string)=>void)=><select className={input} value={opt[key]} onChange={e=>onChange?onChange(e.target.value):option({[key]:e.target.value})}>{choices.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>;
  const run=async(action:"save"|"test")=>{
    setBusy(action);setError("");setNotice("");setResult(null);
    try {
      const payload=ssoPayload(cfg,secret);
      if(action==="save") {setCfg(await http.put("/admin/sso/config",payload));setSecret("");setNotice("SSO 配置已保存");}
      else setResult(await http.post("/admin/sso/config/test",payload));
    } catch(e:any) {setError(e.message||"操作失败，请重试");}
    finally {setBusy(null);}
  };
  if(!cfg) return <div className={card}>{error?<><p className="text-[13px] text-[#cf222e]">{error}</p><button className={`${secondary} mt-3`} onClick={load}>重新加载</button></>:<p className="text-[13px] text-[#656d76]">加载中…</p>}</div>;
  return <div className="space-y-4">
    <fieldset disabled={!!busy} className="min-w-0 space-y-4 disabled:opacity-75">
      <Section title="企业统一身份登录" description="配置企业身份服务，员工可使用企业账号登录社区。当前部署使用一套生效配置。">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-[13px]"><input type="checkbox" checked={!!cfg.enabled} onChange={e=>set({enabled:e.target.checked})} className="h-4 w-4 accent-[#0969da]"/>启用 SSO 登录入口</label>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field title="认证协议"><select className={input} value={cfg.protocol} onChange={e=>set({protocol:e.target.value,scopes:e.target.value==="oauth2"?"":"openid profile email"})}><option value="oidc">OpenID Connect（OIDC）</option><option value="oauth2">OAuth 2.0（授权码）</option></select></Field>
          <Field title="登录按钮名称">{text("label","企业统一身份登录")}</Field>
        </div>
        <p className="mt-3 text-[12px] text-[#656d76]">{oauth?"通过授权码换取 Access Token，再从指定接口或 Token 响应中读取用户信息。":"校验 ID Token 的签名、Issuer、Audience 和 Nonce，并使用 PKCE 保护授权码。"}</p>
      </Section>

      <Section title="应用凭据与回调" description="应用凭据由客户身份平台分配；Client Secret 加密存储，保存后不显示明文。">
        <div className="mb-4 rounded-md border border-[#d0d7de] bg-[#f6f8fa] p-3">
          <div className="text-[12px] text-[#656d76]">回调地址 Redirect URI · 请登记到身份平台的回调白名单</div>
          <div className="mt-2 flex items-start gap-3"><code className="min-w-0 flex-1 break-all text-[13px] text-[#0969da]">{cfg.redirect_uri}</code><button className={secondary} onClick={async()=>{try {await navigator.clipboard.writeText(cfg.redirect_uri);setNotice("回调地址已复制");}catch {setError("复制失败，请手动复制回调地址");}}}>复制</button></div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field title="Client ID">{text("client_id")}</Field>
          <Field title="Client Secret" hint="留空保留已保存的密钥。"><input type="password" autoComplete="new-password" className={input} value={secret} onChange={e=>{setSecret(e.target.value);setResult(null);}} placeholder={cfg.has_client_secret?"已配置，输入新值可替换":"尚未配置"}/></Field>
        </div>
      </Section>

      <Section title="认证接口" description={oauth?"填写企业提供的完整 HTTPS 接口地址。":"Issuer 用于验证令牌签发者；端点可显式填写，缺少时通过 Issuer 自动发现。"}>
        <div className="grid gap-4 md:grid-cols-2">
          {!oauth&&<div className="md:col-span-2"><Field title="Issuer URL">{text("issuer","https://sso.example.com")}</Field></div>}
          <Field title="授权地址 Authorize URI">{text("authorization_endpoint","https://sso.example.com/authorize")}</Field>
          <Field title="Token 地址 Token URI">{text("token_endpoint","https://sso.example.com/token")}</Field>
          {!oauth&&<Field title="JWKS 地址">{text("jwks_uri")}</Field>}
          <Field title="Scope" hint={oauth?"按客户要求填写，允许留空。":"通常填写 openid profile email。"}>{text("scopes")}</Field>
        </div>
        {oauth&&<details className="mt-4 rounded-md border border-[#d0d7de] bg-[#f6f8fa] p-3"><summary className="cursor-pointer text-[13px] font-medium text-[#0969da]">高级请求参数</summary>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <Field title="Token 请求方式">{choose("token_method",[["POST","POST"],["GET","GET"],["PUT","PUT"]],value=>option({token_method:value,...(value==="GET"?{token_mode:"query"}:{})}))}</Field>
            <Field title="Token 传参方式">{choose("token_mode",opt.token_method==="GET"?[["query","Query"]]:[["form","Form"],["query","Query"],["json","Body（JSON）"]])}</Field>
            <Field title="客户端认证">{choose("token_auth",[["parameters","通过请求参数"],["basic","Authorization: Basic"]])}</Field>
          </div>
          <label className="mt-4 flex items-center gap-2 text-[13px]"><input type="checkbox" checked={opt.pkce} onChange={e=>option({pkce:e.target.checked})} className="h-4 w-4 accent-[#0969da]"/>启用 PKCE S256（身份平台支持时开启）</label>
          <p className="mt-2 text-[12px] text-[#656d76]">State 校验始终启用。Query 可能包含凭据，部署时应避免代理记录完整请求地址。</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">{(["authorize_params","token_params"] as const).map(group=><div key={group}><h4 className="mb-2 text-[12px] font-medium">{group==="authorize_params"?"授权请求参数名":"Token 请求参数名"}</h4><div className="space-y-2">{(group==="authorize_params"?["client_id","redirect_uri","response_type","scope","state"]:["client_id","client_secret","grant_type","code","redirect_uri"]).map(key=><label key={key} className="flex items-center gap-2 text-[12px]"><span className="w-28 shrink-0 font-mono text-[#656d76]">{key}</span><input aria-label={`${group}.${key}`} className={input} value={opt[group]?.[key]??key} onChange={e=>option({[group]:{...opt[group],[key]:e.target.value}})}/></label>)}</div></div>)}</div>
        </details>}
      </Section>

      <Section title="用户信息与身份映射" description="唯一账号标识用于稳定识别同一用户；用户名和姓名用于展示，不应随意替代唯一标识。">
        <div className="grid gap-4 md:grid-cols-2">
          {oauth&&<Field title="用户信息来源">{choose("userinfo_source",[["endpoint","单独请求用户信息接口"],["token","从 Token 响应中读取"]])}</Field>}
          {(!oauth||opt.userinfo_source==="endpoint")&&<Field title="用户信息地址 UserInfo URI" hint={oauth?"需要固定 client_id 等参数时，可追加在地址的查询参数中。":undefined}>{text("userinfo_endpoint")}</Field>}
          {oauth&&opt.userinfo_source==="endpoint"&&<>
            <Field title="用户信息请求方式">{choose("userinfo_method",[["GET","GET"],["POST","POST"],["PUT","PUT"]],value=>option({userinfo_method:value,...(value==="GET"&&!['query','bearer'].includes(opt.userinfo_mode)?{userinfo_mode:"query"}:{})}))}</Field>
            <Field title="Access Token 传递方式">{choose("userinfo_mode",opt.userinfo_method==="GET"?[["bearer","Authorization: Bearer"],["query","Query"]]:[["bearer","Authorization: Bearer"],["query","Query"],["form","Form"],["json","Body（JSON）"]])}</Field>
            {opt.userinfo_mode!=="bearer"&&<Field title="Access Token 参数名">{optText("access_token_param")}</Field>}
          </>}
          {oauth&&<Field title="用户信息对象路径" hint="根对象留空；嵌套对象例如 data.user。">{optText("userinfo_path","例如 data.user")}</Field>}
          <Field title="唯一账号标识字段" hint={oauth?"填写身份服务提供的稳定、唯一标识字段，例如 id 或 uid。":"通常使用已验证的 sub。"}>{text("claim_sub","sub")}</Field>
          {oauth&&<Field title="账号标识格式" hint="单值数组模式遇到空数组或多个值时拒绝登录。">{choose("subject_mode",[["string","字符串"],["single_array","严格单值数组"]])}</Field>}
          {oauth&&<Field title="用户名字段">{optText("claim_username")}</Field>}
          <Field title="姓名字段">{text("claim_name")}</Field>
          <Field title="邮箱字段">{text("claim_email")}</Field>
          {oauth&&<Field title="手机字段">{optText("claim_mobile")}</Field>}
        </div>
      </Section>

      <Section title="账号与退出" description="首次开通的账号默认为普通会员。后续权限在社区用户管理中分配。">
        <div className="grid gap-4 md:grid-cols-2">
          <Field title="账号绑定规则"><select className={input} value={cfg.bind_rule} onChange={e=>set({bind_rule:e.target.value})}><option value="sub">按唯一账号标识绑定</option><option value="email">按邮箱匹配已有账号</option></select></Field>
          <Field title="退出地址 Logout URI" hint="可选。仅企业登录会话在本地退出后跳转；请填写客户确认的完整 HTTPS 地址。">{optText("logout_url")}</Field>
        </div>
        <div className="mt-4 flex flex-wrap gap-4 text-[13px]">
          <label className="flex items-center gap-2"><input type="checkbox" checked={!!cfg.auto_provision} onChange={e=>set({auto_provision:e.target.checked})} className="h-4 w-4 accent-[#0969da]"/>首次登录自动开通账号</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={!!cfg.extract_employee} onChange={e=>set({extract_employee:e.target.checked})} className="h-4 w-4 accent-[#0969da]"/>员工扩展信息 AI 抽取</label>
        </div>
        <p className="mt-3 text-[12px] text-[#656d76]">{cfg.bind_rule==="email"?"邮箱匹配会绑定已有账号，请确认身份平台返回的邮箱可信。":"按唯一标识绑定时，不会因邮箱相同自动合并已有账号。"} 退出跳转不等于完整单点注销或已签发会话的即时撤销。</p>
      </Section>
    </fieldset>
    {notice&&<div role="status" className="rounded-md border border-[#d0d7de] bg-[#f6f8fa] px-3 py-2 text-[13px] text-[#1a7f37]">{notice}</div>}
    {error&&<div role="alert" className="rounded-md bg-[#ffebe9] px-3 py-2 text-[13px] text-[#cf222e]">{error}</div>}
    {result&&<div role="status" className={`rounded-lg border px-4 py-3 text-[13px] ${result.ok?"border-[#d0d7de] bg-[#f6f8fa] text-[#1a7f37]":"border-[#ffcecb] bg-[#ffebe9] text-[#cf222e]"}`}><p className="font-medium">{result.message}</p>{result.details&&<dl className="mt-2 space-y-1 text-[12px] text-[#656d76]">{Object.entries(result.details).map(([key,value])=><div key={key} className="flex flex-wrap gap-2"><dt>{key}</dt><dd>{String(value)}</dd></div>)}</dl>}</div>}
    <div className="flex flex-wrap gap-3"><button onClick={()=>run("save")} disabled={!!busy} className="rounded-md bg-[#0969da] px-4 py-2 text-sm text-white hover:bg-[#0550ae] disabled:opacity-60">{busy==="save"?"保存中…":"保存配置"}</button><button className={secondary} onClick={()=>run("test")} disabled={!!busy}>{busy==="test"?"检查中…":"检查配置（不保存）"}</button></div>
  </div>;
}
