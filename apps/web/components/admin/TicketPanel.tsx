"use client";

import { useEffect, useState } from "react";
import { http } from "@/lib/api";

export function TicketPanel() {
  const [configs, setConfigs] = useState<any[]>([]);
  const [balances, setBalances] = useState<any[]>([]);
  const [msg, setMsg] = useState("");

  const reload = () => {
    http.get("/admin/tickets/configs").then(setConfigs).catch(() => {});
    http.get("/admin/tickets/users").then(setBalances).catch(() => {});
  };
  useEffect(() => { reload(); }, []);

  const save = async (key: string, patch: any) => {
    try {
      await http.put(`/admin/tickets/configs/${key}`, patch);
      setMsg(`已保存 ${key}`);
      reload();
    } catch (e: any) {
      setMsg("保存失败：" + (e.message || e));
    }
  };

  return (
    <div className="space-y-6">
      {msg && <div className="rounded-md bg-[#dafbe1] px-3 py-2 text-[13px] text-[#1a7f37]">{msg}</div>}

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-1 text-[15px] font-semibold">奖励规则（⭐ Ticket）</h3>
        <p className="mb-3 text-[12px] text-[#656d76]">
          用户完成对应行为后自动发放。奖励值支持 0.1 的精度；每日上限为 0 表示不限。停用某项后该行为不再发奖。
        </p>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-3">行为</th>
              <th className="py-2 pr-3">说明</th>
              <th className="py-2 pr-3">奖励 ⭐</th>
              <th className="py-2 pr-3">每日上限</th>
              <th className="py-2 pr-3">启用</th>
              <th className="py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((c) => (
              <tr key={c.action_key} className="border-b border-[#d0d7de]/50">
                <td className="py-2 font-medium">{c.action_name}</td>
                <td className="py-2 text-[12px] text-[#656d76]">{c.description || c.action_key}</td>
                <td className="py-2">
                  <input
                    type="number" step="0.1" min="0"
                    defaultValue={c.reward}
                    key={`r-${c.action_key}-${c.reward}`}
                    onBlur={(e) => {
                      const v = parseFloat(e.target.value);
                      if (!isNaN(v) && v !== c.reward) save(c.action_key, { reward: v });
                    }}
                    className="w-20 rounded border border-[#d0d7de] px-2 py-1 text-center"
                  />
                </td>
                <td className="py-2">
                  <input
                    type="number" min="0"
                    defaultValue={c.daily_cap}
                    key={`c-${c.action_key}-${c.daily_cap}`}
                    onBlur={(e) => {
                      const v = parseInt(e.target.value);
                      if (!isNaN(v) && v !== c.daily_cap) save(c.action_key, { daily_cap: v });
                    }}
                    className="w-20 rounded border border-[#d0d7de] px-2 py-1 text-center"
                  />
                </td>
                <td className="py-2">
                  <input
                    type="checkbox" checked={c.enabled}
                    onChange={(e) => save(c.action_key, { enabled: e.target.checked })}
                  />
                </td>
                <td className="py-2 text-[11px] text-[#999]">{c.action_key}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border border-[#d0d7de] bg-white p-4">
        <h3 className="mb-3 text-[15px] font-semibold">用户余额排行（Top 100）</h3>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-[#d0d7de] text-left text-[#656d76]">
              <th className="py-2 pr-3">用户</th>
              <th className="py-2 pr-3">当前余额 ⭐</th>
              <th className="py-2">累计获得 ⭐</th>
            </tr>
          </thead>
          <tbody>
            {balances.map((b) => (
              <tr key={b.user_id} className="border-b border-[#d0d7de]/50">
                <td className="py-2">{b.name}</td>
                <td className="py-2 font-medium">{b.balance.toFixed(1)}</td>
                <td className="py-2 text-[#656d76]">{b.total_earned.toFixed(1)}</td>
              </tr>
            ))}
            {balances.length === 0 && (
              <tr><td colSpan={3} className="py-6 text-center text-[#656d76]">暂无用户获得 ticket</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
