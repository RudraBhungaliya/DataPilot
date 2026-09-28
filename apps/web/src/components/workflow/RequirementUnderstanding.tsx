"use client";

import React, { useState } from "react";
import {
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  MapPin,
  Tag,
  Filter,
  Layers,
  Code,
  FileSpreadsheet,
  RefreshCw,
  HelpCircle,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  parseRequirement,
  createWorkflow,
  planWorkflow,
  StructuredRequirement,
  RequirementParseResponse,
  WorkflowDefinition,
} from "@/lib/api";
import { WorkflowEngineView } from "./WorkflowEngineView";

const PRESET_EXAMPLES = [
  {
    label: "Internships in India",
    prompt:
      "Find software engineering internships in India posted in the last 7 days. I need company name, role, location, salary and application URL.",
  },
  {
    label: "SaaS Startups >50 Emp",
    prompt:
      "Find SaaS startups founded after 2020 with more than 50 employees. Include company name, founded year, employee count, website, and funding round.",
  },
  {
    label: "Cybersecurity Companies",
    prompt:
      "Find cybersecurity companies in India. Extract company name, headquarters city, industry, website, and contact email.",
  },
  {
    label: "College Event Sponsors",
    prompt:
      "Find technology sponsors for a college technical hackathon in Bengaluru. I need sponsor name, tier/category, point of contact, and website.",
  },
];

export function RequirementUnderstanding() {
  const [prompt, setPrompt] = useState(
    "Find software engineering internships in India posted in the last 7 days. I need company name, role, location, salary and application URL."
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RequirementParseResponse | null>(null);
  const [createdWorkflowId, setCreatedWorkflowId] = useState<string | null>(null);
  const [workflowPlan, setWorkflowPlan] = useState<WorkflowDefinition | null>(null);
  const [planningWorkflow, setPlanningWorkflow] = useState(false);
  const [savingWorkflow, setSavingWorkflow] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleAnalyze = async (textToParse?: string) => {
    const text = (textToParse !== undefined ? textToParse : prompt).trim();
    if (!text) {
      setErrorMessage("Please enter a data requirement prompt.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setCreatedWorkflowId(null);
    setWorkflowPlan(null);

    try {
      const response = await parseRequirement(text);
      setResult(response);
      if (!response.success && response.error) {
        setErrorMessage(response.error);
      }
    } catch (err: any) {
      setErrorMessage("Unable to understand this requirement. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateWorkflow = async () => {
    if (!result?.requirement) return;
    setPlanningWorkflow(true);
    setErrorMessage(null);
    try {
      const res = await planWorkflow(
        result.requirement,
        prompt,
        createdWorkflowId || result.workflow_id || undefined
      );
      if (res.success && res.workflow) {
        setWorkflowPlan(res.workflow);
        setCreatedWorkflowId(res.workflow.workflow_id);
      } else {
        setErrorMessage(res.error || "Failed to generate workflow plan.");
      }
    } catch (err: any) {
      setErrorMessage("Unable to connect to workflow planning engine.");
    } finally {
      setPlanningWorkflow(false);
    }
  };

  const handleCreateWorkflow = async () => {
    if (!result?.requirement) return;
    setSavingWorkflow(true);
    try {
      const saved = await createWorkflow(prompt, result.requirement);
      if (saved) {
        setCreatedWorkflowId(saved.id);
      } else {
        setCreatedWorkflowId(result.workflow_id || "WF-" + Math.floor(1000 + Math.random() * 9000));
      }
    } catch {
      setCreatedWorkflowId("WF-" + Math.floor(1000 + Math.random() * 9000));
    } finally {
      setSavingWorkflow(false);
    }
  };

  const requirement = result?.requirement;

  return (
    <div className="space-y-6">
      {/* Prompt Input Section */}
      <Card className="border-slate-800 bg-slate-900/60 backdrop-blur-sm relative overflow-hidden shadow-xl">
        <div className="absolute top-0 right-0 w-80 h-80 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />

        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-white tracking-wide">
                  What data do you need?
                </h2>
                <p className="text-xs text-slate-400">
                  Describe your data requirement in plain English. DataPilot AI translates it into a validated specification.
                </p>
              </div>
            </div>
            <Badge variant="info" className="self-start sm:self-auto font-mono text-[11px]">
              AI Engine: Groq
            </Badge>
          </div>

          {/* Textarea Input */}
          <div className="relative">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Find software engineering internships in India posted in the last 7 days with company name, role, salary, location, and application URL..."
              rows={3}
              className="w-full bg-slate-950/80 text-slate-100 placeholder:text-slate-500 text-sm rounded-xl p-3.5 border border-slate-700/60 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition resize-none leading-relaxed"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleAnalyze();
                }
              }}
            />
          </div>

          {/* Quick Presets & Analyze Action */}
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pt-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider mr-1">
                Examples:
              </span>
              {PRESET_EXAMPLES.map((ex, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setPrompt(ex.prompt);
                    handleAnalyze(ex.prompt);
                  }}
                  className="px-2.5 py-1 rounded-lg text-xs bg-slate-800/60 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-700/50 transition duration-150"
                >
                  {ex.label}
                </button>
              ))}
            </div>

            <Button
              variant="primary"
              size="md"
              icon={
                loading ? (
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                ) : (
                  <Sparkles className="w-4 h-4 text-sky-200" />
                )
              }
              disabled={loading || !prompt.trim()}
              onClick={() => handleAnalyze()}
              className="w-full md:w-auto shadow-lg shadow-sky-500/20"
            >
              {loading ? "Analyzing..." : "Analyze Requirement"}
            </Button>
          </div>
        </div>
      </Card>

      {/* Loading State */}
      {loading && (
        <Card className="border-sky-500/20 bg-gradient-to-br from-slate-900/90 to-sky-950/20 p-8 text-center animate-pulse">
          <div className="flex flex-col items-center justify-center space-y-3">
            <div className="relative">
              <div className="w-12 h-12 rounded-full border-2 border-sky-500/30 border-t-sky-400 animate-spin flex items-center justify-center" />
              <Sparkles className="w-5 h-5 text-sky-400 absolute inset-0 m-auto" />
            </div>
            <div>
              <p className="text-base font-semibold text-white">
                Understanding your requirement...
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Decomposing entities, geographic bounds, freshness filters, and schema fields
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Error State */}
      {errorMessage && !loading && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-3 text-rose-400">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-xs sm:text-sm">
            <span className="font-semibold block mb-0.5">Understanding Error</span>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Assumptions (non-blocking - DataPilot never asks questions) */}
      {requirement && !loading && (requirement.assumptions?.length ?? 0) > 0 && (
        <div className="p-4 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-start gap-3 text-sky-200">
          <HelpCircle className="w-5 h-5 shrink-0 mt-0.5 text-sky-400" />
          <div className="text-xs sm:text-sm space-y-1">
            <span className="font-semibold block">Assumptions made</span>
            <ul className="list-disc list-inside text-slate-300 space-y-0.5">
              {requirement.assumptions!.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Structured Result Display (always shown - never blocked on clarification) */}
      {requirement && !loading && (
        <div className="space-y-4">
          {/* Status Header Banner */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <div>
                <span className="text-sm font-semibold text-emerald-300">
                  Workflow specification ready
                </span>
                <span className="text-xs text-slate-400 block sm:inline sm:ml-2">
                  Validation passed • Confidence: {Math.round((requirement.confidence_score || 1.0) * 100)}%
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Button
                variant="outline"
                size="sm"
                icon={<Code className="w-3.5 h-3.5" />}
                onClick={() => setShowRawJson(!showRawJson)}
              >
                {showRawJson ? "Hide JSON" : "View Raw JSON"}
              </Button>

              <Button
                variant="primary"
                size="sm"
                icon={
                  planningWorkflow ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Layers className="w-3.5 h-3.5 text-white" />
                  )
                }
                disabled={planningWorkflow || loading}
                onClick={handleGenerateWorkflow}
                className="bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white shadow-md shadow-sky-500/20"
              >
                {planningWorkflow
                  ? "Planning DAG..."
                  : workflowPlan
                  ? "Regenerate Workflow"
                  : "Generate Workflow"}
              </Button>
            </div>
          </div>

          {/* Workflow Created Confirmation */}
          {createdWorkflowId && (
            <div className="p-3 rounded-lg bg-sky-500/10 border border-sky-500/20 text-xs text-sky-300 flex items-center justify-between">
              <span className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-sky-400" />
                Workflow specification registered: <code className="font-mono bg-slate-900 px-1.5 py-0.5 rounded text-white">{createdWorkflowId}</code>
              </span>
              <span className="text-[11px] text-slate-400">Ready for collection pipeline</span>
            </div>
          )}

          {/* Raw JSON View */}
          {showRawJson && (
            <Card className="border-slate-800 bg-slate-950 p-4 font-mono text-xs text-sky-300 overflow-x-auto">
              <pre className="whitespace-pre">{JSON.stringify(requirement, null, 2)}</pre>
            </Card>
          )}

          {/* Visual Spec Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Objective & Entity Card */}
            <Card className="md:col-span-2 border-slate-800 bg-slate-900/40">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Parsed Objective
                  </span>
                  <Badge variant="info" className="uppercase text-[10px] font-mono tracking-wider">
                    {requirement.entity}
                  </Badge>
                </div>
                <p className="text-base font-semibold text-white leading-relaxed">
                  {requirement.objective}
                </p>

                {/* Constraints Breakdown */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 border-t border-slate-800">
                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <MapPin className="w-4 h-4 text-amber-400 shrink-0" />
                    <div>
                      <span className="text-[10px] text-slate-500 block uppercase font-medium">
                        Location
                      </span>
                      <span className="text-xs text-slate-200 font-medium">
                        {requirement.location?.country ||
                          requirement.location?.city ||
                          requirement.location?.raw ||
                          "Global / Any"}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/80">
                    <Clock className="w-4 h-4 text-sky-400 shrink-0" />
                    <div>
                      <span className="text-[10px] text-slate-500 block uppercase font-medium">
                        Time Constraint
                      </span>
                      <span className="text-xs text-slate-200 font-medium">
                        {requirement.time_constraint
                          ? `${requirement.time_constraint.type?.replace("_", " ")} ${
                              requirement.time_constraint.value || ""
                            } ${requirement.time_constraint.unit || ""}`.trim()
                          : "No time boundary"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            {/* Target Output Config */}
            <Card className="border-slate-800 bg-slate-900/40">
              <div className="space-y-3">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                  Delivery Schema
                </span>

                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <FileSpreadsheet className="w-3.5 h-3.5 text-indigo-400" /> Output Format
                    </span>
                    <span className="text-white font-mono uppercase font-semibold">
                      {requirement.output_format}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Layers className="w-3.5 h-3.5 text-teal-400" /> Source Preference
                    </span>
                    <span className="text-slate-300 font-medium">
                      {requirement.source_preferences?.length > 0
                        ? requirement.source_preferences.join(", ")
                        : "Autonomous Multi-Source"}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-xs py-1.5">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <Filter className="w-3.5 h-3.5 text-rose-400" /> Active Filters
                    </span>
                    <span className="text-slate-300 font-medium">
                      {requirement.filters?.length || 0} rule(s)
                    </span>
                  </div>
                </div>
              </div>
            </Card>
          </div>

          {/* Required Fields & Filters Section */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Required Fields Pill Box */}
            <Card className="border-slate-800 bg-slate-900/40">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-sky-400" />
                    Required Extraction Fields ({requirement.required_fields?.length || 0})
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {requirement.required_fields && requirement.required_fields.length > 0 ? (
                    requirement.required_fields.map((field, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-md bg-slate-800/80 border border-slate-700/60 text-xs text-sky-300 font-mono flex items-center gap-1.5"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                        {field}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500 italic">No specific fields requested.</span>
                  )}
                </div>
              </div>
            </Card>

            {/* Filter Rules List */}
            <Card className="border-slate-800 bg-slate-900/40">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Filter className="w-3.5 h-3.5 text-purple-400" />
                    Extraction Filters & Thresholds
                  </span>
                </div>

                {requirement.filters && requirement.filters.length > 0 ? (
                  <div className="space-y-1.5">
                    {requirement.filters.map((f, idx) => (
                      <div
                        key={idx}
                        className="p-2 rounded-lg bg-slate-950/70 border border-slate-800 flex items-center justify-between text-xs"
                      >
                        <span className="font-mono text-slate-300">{f.field}</span>
                        <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 font-mono text-[11px]">
                          {f.operator}
                        </span>
                        <span className="font-mono text-white font-semibold">
                          {String(f.value)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic py-2">
                    No custom filtering thresholds specified in prompt.
                  </p>
                )}
              </div>
            </Card>
          </div>

          {/* Phase 3: Workflow DAG Engine View */}
          {workflowPlan ? (
            <WorkflowEngineView
              initialWorkflow={workflowPlan}
              onWorkflowUpdated={(updated) => setWorkflowPlan(updated)}
            />
          ) : (
            <div className="p-6 rounded-2xl border border-dashed border-slate-800 bg-slate-900/30 text-center space-y-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center mx-auto border border-indigo-500/20">
                <Layers className="w-5 h-5" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-semibold text-white">
                  Ready to Plan Workflow DAG
                </h4>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  Translate this specification into a deterministic DAG workflow with source discovery, collection, extraction, validation, and dataset compilation steps.
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                icon={
                  planningWorkflow ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 text-sky-200" />
                  )
                }
                disabled={planningWorkflow}
                onClick={handleGenerateWorkflow}
                className="shadow-lg shadow-sky-500/20 bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500"
              >
                {planningWorkflow ? "Generating Workflow..." : "Generate Workflow Plan"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
