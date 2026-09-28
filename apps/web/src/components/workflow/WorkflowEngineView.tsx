"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Play,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowDown,
  Layers,
  Sparkles,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Terminal,
  Database,
  ExternalLink,
  ShieldAlert,
  Sliders,
  FileCheck2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  WorkflowDefinition,
  WorkflowStep,
  StepStatus,
  StepType,
  executeWorkflow,
  fetchWorkflowSteps,
  fetchWorkflowDefinition,
  resumeWorkflow,
} from "@/lib/api";


interface WorkflowEngineViewProps {
  initialWorkflow: WorkflowDefinition;
  onWorkflowUpdated?: (workflow: WorkflowDefinition) => void;
}

export function WorkflowEngineView({
  initialWorkflow,
  onWorkflowUpdated,
}: WorkflowEngineViewProps) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition>(initialWorkflow);
  const [isExecuting, setIsExecuting] = useState<boolean>(
    initialWorkflow.status === "RUNNING"
  );
  const [executionError, setExecutionError] = useState<string | null>(
    initialWorkflow.error || null
  );
  const [expandedStepIds, setExpandedStepIds] = useState<Record<string, boolean>>({});
  const [isResuming, setIsResuming] = useState<boolean>(false);
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  const handleResume = async () => {
    setIsResuming(true);
    setExecutionError(null);
    try {
      // Resume the workflow itself, which resumes the paused collection job.
      setIsExecuting(true);
      startPolling(workflow.workflow_id);
      const res = await resumeWorkflow(workflow.workflow_id);
      if (res.success && res.workflow) {
        setWorkflow(res.workflow);
        if (onWorkflowUpdated) onWorkflowUpdated(res.workflow);
        if (res.workflow.status === "PAUSED") {
          setExecutionError(res.workflow.error || "Still awaiting human action.");
        }
      } else {
        setExecutionError(res.error || "Resume failed.");
      }
    } catch (err: any) {
      setExecutionError(err.message || "Resume failed.");
    } finally {
      setIsResuming(false);
      setIsExecuting(false);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      const fresh = await fetchWorkflowDefinition(workflow.workflow_id);
      if (fresh && fresh.workflow_definition) {
        setWorkflow(fresh.workflow_definition);
        if (onWorkflowUpdated) onWorkflowUpdated(fresh.workflow_definition);
      }
    }
  };

  // Sync state if initialWorkflow prop changes

  useEffect(() => {
    setWorkflow(initialWorkflow);
    if (initialWorkflow.status === "RUNNING") {
      startPolling(initialWorkflow.workflow_id);
    }
  }, [initialWorkflow.workflow_id]);

  const toggleStepExpanded = (stepId: string) => {
    setExpandedStepIds((prev) => ({
      ...prev,
      [stepId]: !prev[stepId],
    }));
  };

  const startPolling = (workflowId: string) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const stepsRes = await fetchWorkflowSteps(workflowId);
        if (stepsRes) {
          setWorkflow((prev) => {
            const updated = {
              ...prev,
              status: stepsRes.status,
              steps: stepsRes.steps,
            };
            if (onWorkflowUpdated) onWorkflowUpdated(updated);
            return updated;
          });

          if (stepsRes.status !== "RUNNING") {
            setIsExecuting(false);
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
          }
        }
      } catch (err) {
        // Soft error handling on polling
      }
    }, 1000);
  };

  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  const handleExecute = async () => {
    setIsExecuting(true);
    setExecutionError(null);

    // Optimistically set workflow and steps to running
    setWorkflow((prev) => ({
      ...prev,
      status: "RUNNING",
    }));

    try {
      startPolling(workflow.workflow_id);
      const res = await executeWorkflow(workflow.workflow_id);
      if (res.success && res.workflow) {
        setWorkflow(res.workflow);
        if (onWorkflowUpdated) onWorkflowUpdated(res.workflow);
      } else {
        setExecutionError(res.error || "Execution failed without error details.");
      }
    } catch (err: any) {
      setExecutionError(err.message || "Failed to trigger execution.");
    } finally {
      setIsExecuting(false);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      // Re-fetch fresh definition
      const fresh = await fetchWorkflowDefinition(workflow.workflow_id);
      if (fresh && fresh.workflow_definition) {
        setWorkflow(fresh.workflow_definition);
        if (onWorkflowUpdated) onWorkflowUpdated(fresh.workflow_definition);
      }
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            COMPLETED
          </span>
        );
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/10 border border-sky-500/30 text-sky-400 animate-pulse">
            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            RUNNING
          </span>
        );
      case "HUMAN_ACTION_REQUIRED":
      case "PAUSED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 border border-amber-500/40 text-amber-400 animate-pulse">
            <ShieldAlert className="w-3.5 h-3.5" />
            HUMAN ACTION REQUIRED
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 border border-rose-500/30 text-rose-400">
            <AlertCircle className="w-3.5 h-3.5" />
            FAILED
          </span>
        );
      case "SKIPPED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            SKIPPED
          </span>
        );
      case "PLANNED":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
            <Sliders className="w-3.5 h-3.5" />
            PLANNED
          </span>
        );
    }
  };

  const getStepIcon = (status: StepStatus, order: number) => {
    switch (status) {
      case "COMPLETED":
        return (
          <div className="w-7 h-7 rounded-full bg-emerald-500/20 border-2 border-emerald-400 text-emerald-400 flex items-center justify-center shrink-0 shadow-lg shadow-emerald-500/10">
            <CheckCircle2 className="w-4 h-4" />
          </div>
        );
      case "RUNNING":
        return (
          <div className="w-7 h-7 rounded-full bg-sky-500/20 border-2 border-sky-400 text-sky-400 flex items-center justify-center shrink-0 animate-spin">
            <RefreshCw className="w-4 h-4" />
          </div>
        );
      case "HUMAN_ACTION_REQUIRED":
        return (
          <div className="w-7 h-7 rounded-full bg-amber-500/20 border-2 border-amber-400 text-amber-400 flex items-center justify-center shrink-0 animate-pulse">
            <ShieldAlert className="w-4 h-4" />
          </div>
        );
      case "FAILED":
        return (
          <div className="w-7 h-7 rounded-full bg-rose-500/20 border-2 border-rose-400 text-rose-400 flex items-center justify-center shrink-0">
            <AlertCircle className="w-4 h-4" />
          </div>
        );
      case "SKIPPED":
        return (
          <div className="w-7 h-7 rounded-full bg-slate-800 border-2 border-slate-700 text-slate-500 flex items-center justify-center shrink-0">
            <span className="text-xs font-mono">{order}</span>
          </div>
        );
      case "PENDING":
      default:
        return (
          <div className="w-7 h-7 rounded-full bg-slate-900 border-2 border-slate-700 text-slate-400 flex items-center justify-center shrink-0 group-hover:border-slate-500 transition">
            <span className="text-xs font-mono font-semibold">{order}</span>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6 pt-2">
      {/* Workflow Plan Header Card */}
      <Card className="border-indigo-500/20 bg-gradient-to-br from-slate-900/90 via-[#0d162a] to-slate-900/90 p-5 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 space-y-4">
          {/* Header Row */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-indigo-500/15 border border-indigo-500/30 text-indigo-300">
                  Phase 3: Workflow DAG
                </span>
                <span className="text-xs text-slate-500 font-mono">
                  ID: {workflow.workflow_id.slice(0, 8)}...
                </span>
              </div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                {workflow.name}
              </h2>
              <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
                {workflow.description}
              </p>
            </div>

            <div className="flex items-center gap-3">
              {getStatusBadge(workflow.status)}

              <Button
                variant="primary"
                size="md"
                disabled={isExecuting || workflow.status === "RUNNING"}
                onClick={handleExecute}
                icon={
                  isExecuting ? (
                    <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  ) : (
                    <Play className="w-4 h-4 text-white fill-white" />
                  )
                }
                className="shadow-lg shadow-sky-500/25 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500"
              >
                {isExecuting
                  ? "Executing Workflow..."
                  : workflow.status === "COMPLETED"
                  ? "Re-execute Workflow"
                  : "Execute Workflow"}
              </Button>
            </div>
          </div>

          {/* Execution mode notice */}
          <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 text-xs">
            <div className="flex items-center gap-2 text-sky-300">
              <ShieldAlert className="w-4 h-4 text-sky-400 shrink-0" />
              <span>
                <strong>Phase 4 Active:</strong>{" "}
                <span className="font-mono text-sky-200 bg-sky-950/60 px-1 py-0.5 rounded">
                  DISCOVER_SOURCES
                </span>{" "}
                and{" "}
                <span className="font-mono text-sky-200 bg-sky-950/60 px-1 py-0.5 rounded">
                  COLLECT_DATA
                </span>{" "}
                run the real collection engine; downstream extraction steps remain placeholders until Phase 5.
              </span>
            </div>
            <span className="text-[11px] text-slate-400 font-mono shrink-0 hidden sm:inline">
              DAG Steps: {workflow.steps.length}
            </span>
          </div>

          {/* Execution Error Banner */}
          {executionError && !workflow.steps.some(s => s.status === "HUMAN_ACTION_REQUIRED" || s.metadata?.human_action_required) && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-xs text-rose-300 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold block">Execution Failed</span>
                <span>{executionError}</span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Human Action Required Notification Banner */}
      {(() => {
        const humanActionStep = workflow.steps.find(
          (s) => s.metadata?.human_action_required || s.status === "HUMAN_ACTION_REQUIRED"
        );
        if (!humanActionStep) return null;
        const checkpoint = humanActionStep.metadata?.checkpoint;
        const jobId = humanActionStep.metadata?.job_id;

        return (
          <div className="p-6 rounded-2xl bg-amber-500/10 border-2 border-amber-500/40 text-amber-200 shadow-2xl space-y-4">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                  <ShieldAlert className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-semibold uppercase tracking-wider">
                    Human action required
                  </div>
                  <h3 className="text-lg font-bold text-white">
                    DataPilot encountered a CAPTCHA on this source. We have paused the collection safely.
                  </h3>
                  <p className="text-sm text-amber-200/80">
                    Please complete the CAPTCHA at the source, then return to DataPilot and click Resume.
                  </p>
                </div>
              </div>

              {jobId && (
                <Button
                  onClick={handleResume}
                  disabled={isResuming}
                  className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold shrink-0 shadow-lg shadow-amber-500/25 px-5"
                >
                  <Play className={`w-4 h-4 mr-2 ${isResuming ? "animate-spin" : "fill-current"}`} />
                  {isResuming ? "Resuming..." : "Resume Collection"}
                </Button>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-4 bg-slate-950/70 rounded-xl border border-amber-500/20 text-xs font-mono">
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Source Name</span>
                <span className="text-slate-200 font-semibold">{checkpoint?.source_name || "Protected Target"}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Source URL (Complete CAPTCHA)</span>
                <a
                  href={checkpoint?.source_url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:underline flex items-center gap-1 truncate"
                >
                  <span className="truncate">{checkpoint?.source_url || "N/A"}</span>
                  <ExternalLink className="w-3.5 h-3.5 shrink-0" />
                </a>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Task ID & Status</span>
                <span className="text-amber-400 font-semibold">{jobId || humanActionStep.id} (HUMAN_ACTION_REQUIRED)</span>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Vertical Workflow Timeline */}
      <div className="space-y-3">

        <div className="flex items-center justify-between px-1">
          <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            Execution Pipeline ({workflow.steps.length} steps)
          </h3>
          <span className="text-[11px] text-slate-500">
            Topological Dependency Order
          </span>
        </div>

        <div className="relative pl-4 space-y-4">
          {/* Vertical Connecting Line */}
          <div className="absolute top-4 bottom-6 left-[29px] w-0.5 bg-gradient-to-b from-indigo-500/40 via-sky-500/30 to-slate-800 pointer-events-none" />

          {workflow.steps.map((step, idx) => {
            const isExpanded = expandedStepIds[step.id] || false;
            const hasOutput = step.output !== null && step.output !== undefined;

            return (
              <div key={step.id} className="relative flex items-start gap-3 group">
                {/* Step Status Icon Indicator */}
                <div className="pt-2 z-10">{getStepIcon(step.status, step.order)}</div>

                {/* Step Card Content */}
                <Card
                  className={`flex-1 transition duration-200 border-slate-800/90 ${
                    step.status === "COMPLETED"
                      ? "bg-slate-900/60 border-emerald-500/20 hover:border-emerald-500/40"
                      : step.status === "RUNNING"
                      ? "bg-sky-950/20 border-sky-500/40 shadow-lg shadow-sky-500/5"
                      : step.status === "FAILED"
                      ? "bg-rose-950/20 border-rose-500/30"
                      : "bg-slate-900/40 hover:border-slate-700"
                  }`}
                >
                  <div className="space-y-2.5">
                    {/* Step Card Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className="text-sm font-bold text-white tracking-wide">
                          {step.name}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-slate-800 text-sky-300 border border-slate-700">
                          {step.type}
                        </span>
                        {step.depends_on.length > 0 ? (
                          <span className="text-[11px] text-slate-400 font-mono">
                            Depends on: {step.depends_on.join(", ")}
                          </span>
                        ) : (
                          <span className="text-[11px] text-teal-400 font-mono">
                            [Root Step]
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        {step.metadata?.duration_ms !== undefined && (
                          <span className="text-[11px] font-mono text-slate-500">
                            {step.metadata.duration_ms}ms
                          </span>
                        )}
                        {getStatusBadge(step.status)}

                        <button
                          type="button"
                          onClick={() => toggleStepExpanded(step.id)}
                          className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
                          title="Toggle details"
                        >
                          {isExpanded ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Step Description */}
                    <p className="text-xs text-slate-400 leading-relaxed">
                      {step.description}
                    </p>

                    {/* Output summary pill if finished */}
                    {hasOutput && !isExpanded && (
                      <div className="pt-1 flex items-center justify-between text-[11px] text-emerald-400 font-mono">
                        <span className="flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Execution successful • output captured
                        </span>
                        <button
                          type="button"
                          onClick={() => toggleStepExpanded(step.id)}
                          className="text-xs text-sky-400 hover:underline"
                        >
                          Inspect output →
                        </button>
                      </div>
                    )}

                    {/* Expandable Config & Output Panel */}
                    {isExpanded && (
                      <div className="pt-3 border-t border-slate-800/80 space-y-3">
                        {/* Configuration */}
                        {step.config && Object.keys(step.config).length > 0 && (
                          <div className="space-y-1">
                            <span className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                              Step Configuration
                            </span>
                            <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800 font-mono text-xs text-slate-300 overflow-x-auto">
                              <pre className="whitespace-pre">
                                {JSON.stringify(step.config, null, 2)}
                              </pre>
                            </div>
                          </div>
                        )}

                        {/* Output */}
                        {hasOutput && (
                          <div className="space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] uppercase tracking-wider font-semibold text-emerald-400 flex items-center gap-1">
                                <FileCheck2 className="w-3.5 h-3.5" /> Step Output Payload
                              </span>
                              <span
                                className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                                  step.output?.is_mock === false
                                    ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                                    : "bg-sky-950 text-sky-300 border-sky-800"
                                }`}
                              >
                                {step.output?.is_mock === false ? "LIVE DATA" : "MOCK DATA"}
                              </span>
                            </div>
                            <div className="p-2.5 rounded-lg bg-slate-950/90 border border-slate-800 font-mono text-xs text-emerald-300 overflow-x-auto max-h-60">
                              <pre className="whitespace-pre">
                                {JSON.stringify(step.output, null, 2)}
                              </pre>
                            </div>
                          </div>
                        )}

                        {/* Error */}
                        {step.error && (
                          <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300 font-mono">
                            {step.error}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
