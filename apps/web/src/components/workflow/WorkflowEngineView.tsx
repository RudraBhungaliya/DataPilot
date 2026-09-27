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
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

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

          {/* Phase 3 Mock Notice Pill */}
          <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-slate-950/70 border border-slate-800/90 text-xs">
            <div className="flex items-center gap-2 text-sky-300">
              <ShieldAlert className="w-4 h-4 text-sky-400 shrink-0" />
              <span>
                <strong>Verification Mode:</strong> This workflow runs against deterministic{" "}
                <span className="font-mono text-sky-200 bg-sky-950/60 px-1 py-0.5 rounded">
                  MockStepExecutors
                </span>
                . External crawlers & scraping workers activate in Phase 4.
              </span>
            </div>
            <span className="text-[11px] text-slate-400 font-mono shrink-0 hidden sm:inline">
              DAG Steps: {workflow.steps.length}
            </span>
          </div>

          {/* Execution Error Banner */}
          {executionError && (
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
                          Execution successful • Mock output captured
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
                              <span className="text-[10px] font-mono bg-sky-950 text-sky-300 px-1.5 py-0.5 rounded border border-sky-800">
                                MOCK DATA
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
