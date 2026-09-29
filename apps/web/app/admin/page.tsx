"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { CategoryManager } from "@/components/admin/CategoryManager";
import { RagManager } from "@/components/admin/RagManager";
import { ModelConfigPanel } from "@/components/admin/ModelConfigPanel";
import { ReviewsPanel } from "@/components/admin/ReviewsPanel";
import { NewsPanel } from "@/components/admin/NewsPanel";
import { UsersPanel } from "@/components/admin/UsersPanel";
import { OverviewPanel } from "@/components/admin/OverviewPanel";
import { AuditPanel } from "@/components/admin/AuditPanel";
import { SettingsPanel } from "@/components/admin/SettingsPanel";
import { TicketPanel } from "@/components/admin/TicketPanel";
import { ExternalAgentsPanel } from "@/components/admin/ExternalAgentsPanel";
import { SsoPanel } from "@/components/admin/SsoPanel";

type TabKey = "overview" | "reviews" | "news" | "users" | "categories" | "rag" | "models" | "external" | "audit" | "tickets" | "sso" | "settings" | "other";

const MENU: { key: TabKey; label: string; icon: string }[] = [
  { key: "overview", label: "总览", icon: "📊" },
  { key: "reviews", label: "审核", icon: "🛡️" },
  { key: "news", label: "资讯", icon: "📰" },
  { key: "users", label: "用户", icon: "👥" },
  { key: "categories", label: "栏目", icon: "🗂️" },
  { key: "rag", label: "知识库", icon: "📚" },
  { key: "models", label: "模型配置", icon: "🤖" },
  { key: "external", label: "外部 Agent", icon: "🔗" },
  { key: "sso", label: "SSO 登录", icon: "🔐" },
  { key: "audit", label: "审计", icon: "🔍" },
  { key: "tickets", label: "奖励设置", icon: "⭐" },
  { key: "settings", label: "设置", icon: "⚙️" },
  { key: "other", label: "其他", icon: "⋯" },
];

const TAB_LABELS: Record<TabKey, string> = {
  overview: "总览 / MCP",
  reviews: "审核队列",
  news: "AI 资讯源",
  users: "用户与邀请码",
  categories: "栏目 & AI 管理员",
  rag: "知识库 RAG",
  models: "模型配置",
  external: "外部回帖源（第三方 Agent）",
  sso: "企业统一身份登录（OIDC）",
  audit: "审计日志",
  tickets: "奖励（⭐ Ticket）配置",
  settings: "站点设置",
  other: "其他功能",
};

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const tabParam = params.get("tab") as TabKey | null;
  const [tab, setTab] = useState<TabKey>(tabParam && MENU.some((m) => m.key === tabParam) ? tabParam : "overview");

  useEffect(() => {
    if (user && user.role !== "super_admin") router.push("/");
  }, [user, router]);

  // URL 与 state 同步（支持直接 /admin?tab=reviews）
  useEffect(() => {
    if (tabParam && tabParam !== tab && MENU.some((m) => m.key === tabParam)) setTab(tabParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tabParam]);

  const selectTab = (k: TabKey) => {
    setTab(k);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", k);
    window.history.replaceState({}, "", url.toString());
  };

  if (!user || user.role !== "super_admin") {
    return <div className="p-10 text-center text-sm text-[#656d76]">加载中…</div>;
  }

  return (
    <div className="mx-auto max-w-[1360px] px-4 py-6">
      <div className="mb-5">
        <h1 className="text-[24px] font-semibold">管理后台</h1>
        <p className="text-[13px] text-[#656d76]">AI 原生运维控制台 · 所有 Agent 决策可审计</p>
      </div>
      <div className="flex gap-6">
        {/* 左侧边栏菜单 */}
        <aside className="w-[180px] shrink-0">
          <ul className="space-y-1">
            {MENU.map((m) => (
              <li key={m.key}>
                <button
                  onClick={() => selectTab(m.key)}
                  className={`flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm ${
                    tab === m.key ? "bg-[#0969da]/10 font-medium text-[#0969da]" : "text-[#24292f] hover:bg-[#eaeef2]"
                  }`}
                >
                  <span className="text-[13px]">{m.icon}</span> {m.label}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* 右侧内容 */}
        <main className="min-w-0 flex-1">
          <div className="mb-3 text-[13px] text-[#656d76]">{TAB_LABELS[tab]}</div>
          {tab === "overview" && <OverviewPanel />}
          {tab === "reviews" && <ReviewsPanel />}
          {tab === "news" && <NewsPanel />}
          {tab === "users" && <UsersPanel />}
          {tab === "categories" && <CategoryManager />}
          {tab === "rag" && <RagManager />}
          {tab === "models" && <ModelConfigPanel />}
          {tab === "external" && <ExternalAgentsPanel />}
          {tab === "sso" && <SsoPanel />}
          {tab === "audit" && <AuditPanel />}
          {tab === "tickets" && <TicketPanel />}
          {tab === "settings" && <SettingsPanel />}
          {tab === "other" && (
            <div className="rounded-lg border border-[#d0d7de] bg-white p-6">
              <h3 className="mb-2 text-[15px] font-semibold">其他</h3>
              <p className="text-[13px] text-[#656d76]">
                MCP 接入信息、Agent 执行记录与操作审计日志在「总览」「审计」页查看；站点名称、附件限制、审核提示词在「设置」页配置。
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
