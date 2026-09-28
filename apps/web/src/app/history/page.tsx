"use client";

import React, { useEffect, useState } from "react";
import {
  History,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ListChecks,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import { fetchWorkflows, fetchJobs, fetchQueueStats, WorkflowRecord, BackgroundJob } from "@/lib/api";

function statusVariant(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "COMPLETED":
      return "success";
    case "PAUSED":
    case "QUEUED":
      return "warning";
    case "FAILED":
      return "danger";
    case "RUNNING":
      return "info";
    default:
      return "neutral";
  }
}

function StatusIcon({ status }: { status: string }) {
  if (status === "COMPLETED") return <CheckCircle2 className="w-3.5 h-3.5" />;
  if (status === "FAILED") return <AlertCircle className="w-3.5 h-3.5" />;
  if (status === "RUNNING") return <Loader2 className="w-3.5 h-3.5 animate-spin" />;
  return <Clock className="w-3.5 h-3.5" />;
}

export default function HistoryPage() {
  const [workflows, setWorkflows] = useState<WorkflowRecord[]>([]);
  const [jobs, setJobs] = useState<BackgroundJob[]>([]);
  const [queueDepth, setQueueDepth] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  const load = async () => {
    setLoading(true);
    try {
      const [wfs, js, stats] = await Promise.all([fetchWorkflows(), fetchJobs(), fetchQueueStats()]);
      setWorkflows(wfs);
      setJobs(js);
      setQueueDepth(stats.depth);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <History className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Workflow &amp; Task History</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Execution log of workflows and background jobs
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={load}
          disabled={loading}
          className="border-slate-700 hover:bg-slate-800 text-slate-300"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader
          title="Recent Workflows"
          subtitle="Most recently parsed and executed pipeline runs"
        />
        {loading ? (
          <p className="text-sm text-slate-400 py-6 text-center">Loading workflow history...</p>
        ) : workflows.length === 0 ? (
          <p className="text-sm text-slate-400 py-6 text-center">No workflow runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                  <th className="pb-3 font-semibold">Workflow</th>
                  <th className="pb-3 font-semibold">Prompt</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold text-right">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {workflows.map((wf) => (
                  <tr key={wf.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 font-mono text-sky-400">{wf.id.slice(0, 12)}</td>
                    <td className="py-3 text-slate-200 max-w-md truncate pr-4">{wf.prompt}</td>
                    <td className="py-3">
                      <Badge variant={statusVariant(wf.status)}>
                        <StatusIcon status={wf.status} />
                        {wf.status}
                      </Badge>
                    </td>
                    <td className="py-3 text-right text-slate-500 font-mono">
                      {wf.created_at ? new Date(wf.created_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Background Tasks"
          subtitle="Asynchronously queued jobs and their results"
          action={
            <Badge variant={queueDepth > 0 ? "warning" : "neutral"}>
              <ListChecks className="w-3 h-3" /> queue: {queueDepth}
            </Badge>
          }
        />
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-400 py-6 text-center">No background tasks yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                  <th className="pb-3 font-semibold">Task ID</th>
                  <th className="pb-3 font-semibold">Kind</th>
                  <th className="pb-3 font-semibold">Status</th>
                  <th className="pb-3 font-semibold">Result / Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 font-mono text-indigo-300">{job.id}</td>
                    <td className="py-3 font-mono text-slate-400">{job.kind}</td>
                    <td className="py-3">
                      <Badge variant={statusVariant(job.status)}>
                        <StatusIcon status={job.status} />
                        {job.status}
                      </Badge>
                    </td>
                    <td className="py-3 text-slate-400 max-w-md truncate font-mono">
                      {job.error
                        ? job.error
                        : job.result
                        ? JSON.stringify(job.result)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
