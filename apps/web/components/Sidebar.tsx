"use client";

import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useEffect, useState } from "react";
import { http } from "@/lib/api";
import { usePathname, useSearchParams } from "next/navigation";

export function Sidebar() {
  const { user } = useAuth();
  const [pages, setPages] = useState<{ slug: string; title: string }[]>([]);
  useEffect(() => {
    let active = true; setPages([]);
    if (user) http.get("/sdk-pages").then(p => { if (active) setPages(p); }).catch(() => {});
    return () => { active = false; };
  }, [user?.id]);
  const [cats, setCats] = useState<any[]>([]);
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    http.get("/categories").then((d) => setCats(d)).catch(() => {});
  }, []);

  const activeCat = pathname.startsWith("/c/") ? pathname.split("/")[2] : null;
  const sort = searchParams.get("sort");
  // 高亮规则：无 sort=最新；sort=hot=热门；sort=unanswered=未回答；有 sort 但非两者则不点亮浏览项
  const browseKey = pathname === "/" ? (sort && sort !== "hot" && sort !== "unanswered" ? "none" : sort || "latest") : "none";

  return (
    <nav className="w-[220px] shrink-0 space-y-6">
      {user && pages.map(p => <Link key={p.slug} href={`/sdk/${p.slug}`} className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${pathname === `/sdk/${p.slug}` ? "bg-[#0969da]/10 font-medium text-[#0969da]" : "text-[#24292f] hover:bg-[#eaeef2]"}`}><span>💬</span>{p.title}</Link>)}
      <div>
        <div className="mb-2 px-2 text-[13px] font-semibold text-[#656d76]">浏览</div>
        <ul className="space-y-0.5">
          {[
            { href: "/", label: "最新", key: "latest" as const, icon: "🕐" },
            { href: "/?sort=hot", label: "热门", key: "hot" as const, icon: "🔥" },
            { href: "/?sort=unanswered", label: "未回答", key: "unanswered" as const, icon: "❓" },
          ].map((item) => (
            <li key={item.label}>
              <Link
                href={item.href}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                  browseKey === item.key ? "bg-[#0969da]/10 font-medium text-[#0969da]" : "text-[#24292f] hover:bg-[#eaeef2]"
                }`}
              >
                <span className="text-[13px]">{item.icon}</span> {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="mb-2 px-2 text-[13px] font-semibold text-[#656d76]">栏目</div>
        <ul className="space-y-0.5">
          {cats.map((c) => (
            <li key={c.id}>
              <Link
                href={`/c/${c.id}`}
                className={`flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                  activeCat === String(c.id) ? "bg-[#0969da]/10 font-medium text-[#0969da]" : "text-[#24292f] hover:bg-[#eaeef2]"
                }`}
              >
                <span className="text-[13px]">{c.icon || "📁"}</span>
                <span className="truncate">{c.name}</span>
                {c.ai_admin && <span className="ml-auto rounded bg-[#0969da]/10 px-1 text-[10px] text-[#0969da]">AI</span>}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
