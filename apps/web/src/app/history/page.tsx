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
  Ban,
  RotateCcw,
  CalendarClock,
  Plus,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardHeader } from "@/components/ui/Card";
import {
  fetchWorkflows,
  fetchJobs,
  fetchQueueStats,
  cancelJob,
  retryJob,
  fetchSchedules,
  createSchedule,
  deleteSchedule,
  WorkflowRecord,
  BackgroundJob,
  ScheduleRecord,
} from "@/lib/api";

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
  const [schedules, setSchedules] = useState<ScheduleRecord[]>([]);
  const [queueDepth, setQueueDepth] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [newTarget, setNewTarget] = useState("");
  const [newInterval, setNewInterval] = useState(3600);

  const load = async () => {
    setLoading(true);
    try {
      const [wfs, js, stats, scheds] = await Promise.all([
        fetchWorkflows(),
        fetchJobs(),
        fetchQueueStats(),
        fetchSchedules(),
      ]);
      setWorkflows(wfs);
      setJobs(js);
      setQueueDepth(stats.depth);
      setSchedules(scheds);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleCancel = async (jobId: string) => {
    setBusy(jobId);
    try {
      await cancelJob(jobId);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const handleRetry = async (jobId: string) => {
    setBusy(jobId);
    try {
      await retryJob(jobId);
      await load();
    } finally {
      setBusy(null);
    }
  };

  const handleCreateSchedule = async () => {
    if (!newTarget.trim()) return;
    setBusy("schedule");
    try {
      await createSchedule({
        name: `Auto-run ${newTarget.slice(0, 8)}`,
        kind: "workflow.execute",
        target_id: newTarget.trim(),
        interval_seconds: Math.max(30, Number(newInterval) || 3600),
      });
      setNewTarget("");
      await load();
    } finally {
      setBusy(null);
    }
  };

  const handleDeleteSchedule = async (id: string) => {
    setBusy(id);
    try {
      await deleteSchedule(id);
      await load();
    } finally {
      setBusy(null);
    }
  };

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
              Execution log, background tasks and recurring schedules
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading} className="border-slate-700 hover:bg-slate-800 text-slate-300">
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader title="Recent Workflows" subtitle="Most recently parsed and executed pipeline runs" />
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
          subtitle="Queued jobs with progress and controls"
          action={
            <Badge variant={queueDepth > 0 ? "warning" : "neutral"}>
              <ListChecks className="w-3 h-3" /> queue: {queueDepth}
            </Badge>
          }
        />
        {jobs.length === 0 ? (
          <p className="text-sm text-slate-400 py-6 text-center">No background tasks yet.</p>
        ) : (
          <div className="space-y-2">
            {jobs.map((job) => (
              <div key={job.id} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-indigo-300 text-xs">{job.id}</span>
                      <span className="font-mono text-slate-500 text-xs">{job.kind}</span>
                      <Badge variant={statusVariant(job.status)}>
                        <StatusIcon status={job.status} />
                        {job.status}
                      </Badge>
                    </div>
                    {job.error && <div className="text-[11px] text-rose-400 mt-1 truncate">{job.error}</div>}
                    {!job.error && job.result && (
                      <div className="text-[11px] text-slate-500 mt-1 truncate font-mono">{JSON.stringify(job.result)}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {(job.status === "QUEUED" || job.status === "RUNNING") && (
                      <Button size="sm" variant="danger" disabled={busy === job.id} onClick={() => handleCancel(job.id)} icon={<Ban className="w-3.5 h-3.5" />}>
                        Cancel
                      </Button>
                    )}
                    {(job.status === "COMPLETED" || job.status === "FAILED" || job.status === "CANCELLED") && (
                      <Button size="sm" variant="outline" disabled={busy === job.id} onClick={() => handleRetry(job.id)} icon={<RotateCcw className="w-3.5 h-3.5" />}>
                        Retry
                      </Button>
                    )}
                  </div>
                </div>
                <div className="mt-2 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full ${job.status === "FAILED" ? "bg-rose-500" : "bg-sky-500"}`}
                    style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Scheduled Runs"
          subtitle="Recurring workflow executions"
          action={<Badge variant="info"><CalendarClock className="w-3 h-3" /> {schedules.length}</Badge>}
        />
        <div className="flex flex-col sm:flex-row gap-2 mb-4">
          <input
            value={newTarget}
            onChange={(e) => setNewTarget(e.target.value)}
            placeholder="Workflow ID to run on a schedule"
            className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
          />
          <input
            type="number"
            value={newInterval}
            onChange={(e) => setNewInterval(Number(e.target.value))}
            className="w-32 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500/50"
          />
          <Button size="sm" onClick={handleCreateSchedule} disabled={busy === "schedule"} icon={<Plus className="w-3.5 h-3.5" />}>
            Add schedule
          </Button>
        </div>
        {schedules.length === 0 ? (
          <p className="text-sm text-slate-400 py-2 text-center">No schedules yet.</p>
        ) : (
          <div className="space-y-2">
            {schedules.map((s) => (
              <div key={s.id} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 text-xs">
                <div className="font-mono text-slate-300">
                  {s.name} · {s.kind} · every {s.interval_seconds}s ·{" "}
                  <span className="text-slate-500">{s.enabled ? "enabled" : "disabled"}</span>
                </div>
                <Button size="sm" variant="ghost" disabled={busy === s.id} onClick={() => handleDeleteSchedule(s.id)} icon={<Trash2 className="w-3.5 h-3.5" />}>
                  Delete
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
