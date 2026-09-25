"use client";

import React, { useState, useEffect } from "react";
import { Search, Bell, ExternalLink, Cpu, Database, RefreshCw, CheckCircle2, AlertCircle } from "lucide-react";
import { Badge } from "../ui/Badge";
import { fetchHealth, HealthData } from "@/lib/api";

export function Navbar() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const checkHealth = async () => {
    setLoading(true);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 border-b border-slate-800/80 bg-[#090d16]/80 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Search Input Preview */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search tasks, datasets, sources... (Press '/' to focus)"
            className="w-full bg-slate-900/90 border border-slate-800 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500/50 transition-colors"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4">
        {/* Backend Live Health Pill */}
        <button
          onClick={checkHealth}
          title="Click to refresh backend health status"
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition-colors text-xs font-mono"
        >
          {loading ? (
            <RefreshCw className="w-3.5 h-3.5 text-sky-400 animate-spin" />
          ) : health?.status === "healthy" || health?.status === "degraded" ? (
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
          )}

          <span className="text-slate-300">
            API:{" "}
            {health?.status === "healthy" || health?.status === "degraded"
              ? "Online"
              : "Connecting..."}
          </span>

          <span
            className={`w-2 h-2 rounded-full ${
              health?.status === "healthy"
                ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                : health?.status === "degraded"
                ? "bg-amber-400"
                : "bg-rose-400 animate-pulse"
            }`}
          />
        </button>

        {/* API Docs link */}
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-sky-400 transition-colors px-2.5 py-1.5 rounded-lg hover:bg-slate-800/40"
        >
          <span>Swagger Docs</span>
          <ExternalLink className="w-3.5 h-3.5" />
        </a>

        {/* Notifications Icon */}
        <button className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 transition-colors relative">
          <Bell className="w-4 h-4" />
          <span className="w-2 h-2 bg-sky-400 rounded-full absolute top-1.5 right-1.5" />
        </button>
      </div>
    </header>
  );
}
