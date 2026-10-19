"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function SettingsPanel() {
  const [site, setSite] = useState<any>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    http.get("/admin/site-config").then(setSite).catch(() => {});
  }, []);

  const saveSite = async () => {
    setSaving(true);
    try {
      await http.put("/admin/site-config", {
        site_name: site.site_name || null,
        site_description: site.site_description || null,
        mcp_api_key: site.mcp_api_key || null,
        upload_allowed_types: site.upload_allowed_types || null,
        upload_max_size_mb: site.upload_max_size_mb ? Number(site.upload_max_size_mb) : null,
        review_prompt: site.review_prompt || null,
        logo_url: site.logo_url || "",
      });
      alert("已保存（MCP 令牌修改后需更新豆包工作配置；审核提示词修改后立即生效）");
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r: any = await http.upload("/uploads", fd);
      if (r.url) {
        setSite({ ...site, logo_url: r.url });
      }
    } catch (err: any) {
      alert("上传失败：" + (err.message || err));
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">站点配置</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">站点名称</label>
            <input value={site.site_name || ""} onChange={(e) => setSite({ ...site, site_name: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">站点描述</label>
            <input value={site.site_description || ""} onChange={(e) => setSite({ ...site, site_description: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">站点 LOGO</label>
            <div className="flex items-center gap-3">
              {site.logo_url && (
                <img src={site.logo_url} alt="logo" className="h-8 w-auto rounded border border-[#d0d7de] bg-white p-1" />
              )}
              <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={uploadLogo} className="text-[12px]" />
              {site.logo_url && (
                <button onClick={() => setSite({ ...site, logo_url: "" })} className="text-[12px] text-[#cf222e] hover:underline">移除</button>
              )}
            </div>
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">MCP 访问令牌</label>
            <input value={site.mcp_api_key || ""} onChange={(e) => setSite({ ...site, mcp_api_key: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">附件允许格式（逗号分隔）</label>
            <input value={site.upload_allowed_types || ""} onChange={(e) => setSite({ ...site, upload_allowed_types: e.target.value })} placeholder="png,jpg,jpeg,gif,webp,pdf,doc,docx,xls,xlsx,txt,md,csv,zip" className="w-full rounded border border-[#d0d7de] px-2 py-1.5 font-mono text-sm" />
          </div>
          <div>
            <label className="mb-1 block text-[12px] text-[#656d76]">单文件大小上限（MB）</label>
            <input type="number" min={1} max={500} value={site.upload_max_size_mb || ""} onChange={(e) => setSite({ ...site, upload_max_size_mb: e.target.value })} className="w-full rounded border border-[#d0d7de] px-2 py-1.5 text-sm" />
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-2 text-[15px] font-semibold">AI 内容审核提示词</h3>
        <p className="mb-2 text-[12px] text-[#656d76]">
          发帖后先异步调用大模型审核（通过才公开），此提示词决定审核标准。默认预设已覆盖：政治敏感、违法、色情低俗、暴力恐怖、人身攻击、粗口脏话、消极情绪、与技术无关的闲聊灌水、藏头诗/谐音变体等。修改后立即生效。
        </p>
        <textarea
          value={site.review_prompt || ""}
          onChange={(e) => setSite({ ...site, review_prompt: e.target.value })}
          rows={14}
          className="w-full rounded border border-[#d0d7de] px-3 py-2 font-mono text-[13px] leading-relaxed outline-none focus:border-[#0969da]"
        />
      </div>

      <button onClick={saveSite} disabled={saving} className="rounded-md bg-[#0969da] px-4 py-2 text-sm text-white hover:bg-[#0550ae] disabled:opacity-60">
        {saving ? "保存中…" : "保存配置"}
      </button>
    </div>
  );
}
