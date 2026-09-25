import React from "react";
import Link from "next/link";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { ArrowLeft, Sparkles, LucideIcon } from "lucide-react";

interface PlaceholderPageProps {
  title: string;
  subtitle: string;
  badgeText: string;
  icon: LucideIcon;
  plannedFeatures: string[];
  actionLabel?: string;
  onAction?: () => void;
}

export function PlaceholderPage({
  title,
  subtitle,
  badgeText,
  icon: Icon,
  plannedFeatures,
  actionLabel = "Create Sample",
  onAction,
}: PlaceholderPageProps) {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
              <Icon className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-white tracking-tight">{title}</h1>
                <Badge variant="info">{badgeText}</Badge>
              </div>
              <p className="text-sm text-slate-400 mt-1">{subtitle}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="outline" size="sm" icon={<ArrowLeft className="w-4 h-4" />}>
              Dashboard
            </Button>
          </Link>
          {actionLabel && (
            <Button
              variant="primary"
              size="sm"
              icon={<Sparkles className="w-4 h-4" />}
              onClick={onAction}
            >
              {actionLabel}
            </Button>
          )}
        </div>
      </div>

      {/* Main Empty / Placeholder Canvas */}
      <div className="glass-card rounded-2xl p-8 sm:p-12 border border-slate-800/80 text-center flex flex-col items-center justify-center min-h-[380px]">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-sky-500/20 to-indigo-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 mb-5 shadow-lg shadow-sky-500/10">
          <Icon className="w-8 h-8" />
        </div>

        <h2 className="text-xl font-semibold text-slate-100 mb-2">
          {title} Module Initialized
        </h2>
        <p className="text-slate-400 text-sm max-w-md mb-8 leading-relaxed">
          Foundation routing and state management are connected. This workspace is scheduled for full autonomous agent integration in Phase 2.
        </p>

        {/* Feature roadmap preview */}
        <div className="w-full max-w-lg bg-slate-900/60 rounded-xl p-5 border border-slate-800 text-left">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-sky-400" />
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Planned Capabilities (Phase 2)
            </span>
          </div>
          <ul className="space-y-2">
            {plannedFeatures.map((feat, index) => (
              <li key={index} className="flex items-start gap-2 text-xs text-slate-400">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-sky-400 mt-1.5 shrink-0" />
                <span>{feat}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
