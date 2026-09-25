import React from "react";
import { PlaceholderPage } from "@/components/ui/PlaceholderPage";
import { Database } from "lucide-react";

export default function DatasetsPage() {
  return (
    <PlaceholderPage
      title="Datasets"
      subtitle="Structured, source-backed datasets ready for exploration and export"
      badgeText="Phase 2 Feature"
      icon={Database}
      actionLabel="Import Dataset"
      plannedFeatures={[
        "Interactive data grid with column filtering, search, and sorting",
        "Source audit trail and verification provenance for every record",
        "Export in multiple formats: JSON, CSV, Parquet, and direct DB sync",
        "Continuous dataset versioning and diff comparisons",
      ]}
    />
  );
}
