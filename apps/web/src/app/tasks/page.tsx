"use client";

import React from "react";
import { CheckSquare, Sparkles } from "lucide-react";
import { RequirementUnderstanding } from "@/components/workflow/RequirementUnderstanding";

export default function TasksPage() {
  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold mb-2">
          <Sparkles className="w-3.5 h-3.5" />
          <span>AI Workflow Specification</span>
        </div>
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Workflow Generator & Requirement Analyzer
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Specify your data needs in natural language. DataPilot automatically synthesizes entity targets, filter rules, field mappings, and workflow specifications.
        </p>
      </div>

      <RequirementUnderstanding />
    </div>
  );
}
