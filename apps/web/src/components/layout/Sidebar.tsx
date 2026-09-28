"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  CheckSquare,
  Database,
  Globe,
  History,
  Settings,
  Sparkles,
  Terminal,
  Activity,
} from "lucide-react";
import { Badge } from "../ui/Badge";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Tasks", href: "/tasks", icon: CheckSquare, badge: "Phase 2" },
  { name: "Datasets", href: "/datasets", icon: Database, badge: "Phase 5" },
  { name: "Sources", href: "/sources", icon: Globe, badge: "Phase 4" },
  { name: "History", href: "/history", icon: History },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-[#0a0f1d] border-r border-slate-800/80 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      {/* Brand Header */}
      <div>
        <div className="p-6 border-b border-slate-800/60 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-slate-950 font-black shadow-lg shadow-sky-500/20 group-hover:scale-105 transition-transform">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-base tracking-tight block">
                DataPilot
              </span>
              <span className="text-[10px] text-sky-400 font-mono tracking-wider uppercase">
                Intelligence v0.1
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation links */}
        <div className="p-4 space-y-1">
          <div className="px-3 py-2 text-[11px] font-semibold text-slate-500 uppercase tracking-wider font-mono">
            Platform
          </div>
          {navigation.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/20 shadow-sm shadow-sky-500/5 font-semibold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 ${
                      isActive ? "text-sky-400" : "text-slate-400"
                    }`}
                  />
                  <span>{item.name}</span>
                </div>
                {item.badge && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-mono">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      </div>

      {/* System Status Footer */}
      <div className="p-4 m-3 rounded-xl bg-slate-900/80 border border-slate-800 text-xs">
        <div className="flex items-center justify-between mb-2">
          <span className="text-slate-400 font-medium flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-sky-400" /> System Core
          </span>
          <Badge variant="success" size="sm">
            Phase 5
          </Badge>
        </div>
        <div className="space-y-1.5 text-[11px] font-mono text-slate-400">
          <div className="flex justify-between">
            <span className="text-slate-500">FastAPI:</span>
            <span className="text-emerald-400">Port 8000</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">PostgreSQL:</span>
            <span className="text-slate-300">Ready</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Redis:</span>
            <span className="text-slate-300">Ready</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
