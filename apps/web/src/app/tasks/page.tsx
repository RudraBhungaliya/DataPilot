import React from "react";
import { PlaceholderPage } from "@/components/ui/PlaceholderPage";
import { CheckSquare } from "lucide-react";

export default function TasksPage() {
  return (
    <PlaceholderPage
      title="Collection Tasks"
      subtitle="Autonomous data harvesting pipelines and queue monitor"
      badgeText="Phase 2 Feature"
      icon={CheckSquare}
      actionLabel="Create New Task"
      plannedFeatures={[
        "Natural language prompt to dynamic pipeline generator",
        "Multi-source scraping and API extraction orchestrator",
        "Real-time task execution progress, retry policies, and worker telemetry",
        "Automated data cleaning, deduplication, and schema validation",
      ]}
    />
  );
}
