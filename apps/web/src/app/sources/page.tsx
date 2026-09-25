import React from "react";
import { PlaceholderPage } from "@/components/ui/PlaceholderPage";
import { Globe } from "lucide-react";

export default function SourcesPage() {
  return (
    <PlaceholderPage
      title="Source Connectors"
      subtitle="Configured data origin feeds, web endpoints, and compliant API integrations"
      badgeText="Phase 2 Feature"
      icon={Globe}
      actionLabel="Add Connector"
      plannedFeatures={[
        "Pre-built integrations for LinkedIn, GitHub, News Feeds, Reddit, SEC filings",
        "Custom web crawler configurations with rate-limiting and robots.txt compliance",
        "Proxy network management and session rotation",
        "Connector health checks and schema drift alert monitoring",
      ]}
    />
  );
}
