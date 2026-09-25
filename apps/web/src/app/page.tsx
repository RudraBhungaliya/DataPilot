"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  ArrowRight,
  Database,
  Layers,
  Server,
  Activity,
  CheckCircle2,
  HardDrive,
  Cpu,
  Clock,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { fetchHealth, fetchApiRoot, HealthData, ApiRootData } from "@/lib/api";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [apiInfo, setApiInfo] = useState<ApiRootData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [promptText, setPromptText] = useState("");

  const refreshSystemData = async () => {
    setLoading(true);
    const [healthRes, infoRes] = await Promise.all([
      fetchHealth(),
      fetchApiRoot(),
    ]);
    setHealth(healthRes);
    setApiInfo(infoRes);
    setLoading(false);
  };

  useEffect(() => {
    refreshSystemData();
  }, []);

  const sampleTasks = [
    {
      id: "TSK-1092",
      prompt: "Extract AI engineer job postings in SF with salary ranges > $180k",
      source: "LinkedIn, Indeed",
      records: "1,420 items",
      status: "running" as const,
      timestamp: "2 mins ago",
    },
    {
      id: "TSK-1091",
      prompt: "Monitor Series A fintech funding announcements across EU tech blogs",
      source: "TechCrunch, Sifted",
      records: "385 items",
      status: "completed" as const,
      timestamp: "1 hour ago",
    },
    {
      id: "TSK-1090",
      prompt: "Aggregate quarterly open source repository commit velocity metrics",
      source: "GitHub API",
      records: "5,800 items",
      status: "completed" as const,
      timestamp: "3 hours ago",
    },
  ];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-[#0c1427] to-[#0a1020] border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 space-y-4 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Phase 1 Architecture Foundation</span>
          </div>

          <h1 className="text-3xl md:text-4xl font-extrabold text-white tracking-tight leading-tight">
            AI-Powered <span className="text-transparent bg-clip-text bg-gradient-to-r from-sky-400 via-teal-300 to-indigo-400">Data Intelligence</span> Platform
          </h1>

          <p className="text-sm md:text-base text-slate-400 leading-relaxed">
            Turn natural language business requirements into clean, structured, source-backed datasets with autonomous collection workflows, validation, and deduplication.
          </p>

          {/* Prompt Box Preview */}
          <div className="pt-2">
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-slate-950/80 p-2 rounded-xl border border-slate-700/60 shadow-inner">
              <div className="flex items-center gap-2.5 px-3 flex-1 text-slate-400">
                <Sparkles className="w-4 h-4 text-sky-400 shrink-0" />
                <input
                  type="text"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  placeholder="e.g. Find all seed-funded robotics startups founded in 2025..."
                  className="bg-transparent text-xs sm:text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none w-full"
                />
              </div>
              <Link href="/tasks">
                <Button
                  variant="primary"
                  size="sm"
                  className="w-full sm:w-auto"
                  icon={<ArrowRight className="w-4 h-4" />}
                >
                  Create Workflow
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="hover:border-sky-500/30 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">FastAPI Backend</span>
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400">
              <Server className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-white">v0.1.0</div>
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 mt-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Modular Clean App</span>
            </div>
          </div>
        </Card>

        <Card className="hover:border-indigo-500/30 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Database Layer</span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Database className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-white">PostgreSQL</div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
              <span className="w-2 h-2 rounded-full bg-sky-400" />
              <span>SQLAlchemy Async</span>
            </div>
          </div>
        </Card>

        <Card className="hover:border-rose-500/30 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Cache & Queue</span>
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-400">
              <HardDrive className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-white">Redis 7</div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
              <span className="w-2 h-2 rounded-full bg-rose-400" />
              <span>Pub/Sub & Queue Ready</span>
            </div>
          </div>
        </Card>

        <Card className="hover:border-emerald-500/30 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Monorepo Setup</span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <Layers className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-white">Scale-Ready</div>
            <div className="flex items-center gap-1.5 text-xs text-emerald-400 mt-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Next.js + FastAPI</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Backend Health Check Live Status Section */}
      <Card className="border-slate-800 bg-slate-900/40">
        <CardHeader
          title="System & Infrastructure Status"
          subtitle="Real-time verification of backend API and container services"
          action={
            <Button
              variant="outline"
              size="sm"
              icon={<RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />}
              onClick={refreshSystemData}
            >
              Verify Connections
            </Button>
          }
        />

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
          {/* API Status */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300">FastAPI Health</span>
              <Badge variant={health ? "success" : "warning"}>
                {health?.status || "Checking..."}
              </Badge>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Endpoint: <span className="text-sky-400">/api/v1/health</span>
            </p>
            <div className="text-[11px] text-slate-500 mt-2">
              Environment: <span className="text-slate-300 font-medium">{health?.environment || "development"}</span>
            </div>
          </div>

          {/* PostgreSQL Status */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300">PostgreSQL</span>
              <Badge
                variant={health?.services.database === "connected" ? "success" : "neutral"}
              >
                {health?.services.database || "Ready"}
              </Badge>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Driver: <span className="text-indigo-400">asyncpg / SQLAlchemy</span>
            </p>
            <div className="text-[11px] text-slate-500 mt-2">
              Compose service: <span className="text-slate-300 font-mono">datapilot-postgres</span>
            </div>
          </div>

          {/* Redis Status */}
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300">Redis Foundation</span>
              <Badge
                variant={health?.services.redis === "connected" ? "success" : "neutral"}
              >
                {health?.services.redis || "Ready"}
              </Badge>
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Client: <span className="text-rose-400">redis-py asyncio</span>
            </p>
            <div className="text-[11px] text-slate-500 mt-2">
              Compose service: <span className="text-slate-300 font-mono">datapilot-redis</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Recent Activity Sample Table */}
      <Card>
        <CardHeader
          title="Recent Workflow Pipelines"
          subtitle="Preview of scheduled and automated data collection runs"
          action={
            <Link href="/tasks">
              <Button variant="ghost" size="sm" icon={<ArrowRight className="w-4 h-4" />}>
                View All Tasks
              </Button>
            </Link>
          }
        />

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                <th className="pb-3 font-semibold">Task ID</th>
                <th className="pb-3 font-semibold">Prompt Requirement</th>
                <th className="pb-3 font-semibold">Sources</th>
                <th className="pb-3 font-semibold">Records</th>
                <th className="pb-3 font-semibold">Status</th>
                <th className="pb-3 font-semibold text-right">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {sampleTasks.map((task) => (
                <tr key={task.id} className="group hover:bg-slate-800/30 transition-colors">
                  <td className="py-3 font-mono font-medium text-sky-400">{task.id}</td>
                  <td className="py-3 text-slate-200 font-medium max-w-xs truncate pr-4">
                    {task.prompt}
                  </td>
                  <td className="py-3 text-slate-400">{task.source}</td>
                  <td className="py-3 font-mono text-slate-300">{task.records}</td>
                  <td className="py-3">
                    <Badge variant={task.status === "completed" ? "success" : "info"}>
                      {task.status}
                    </Badge>
                  </td>
                  <td className="py-3 text-right text-slate-500 font-mono">{task.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
