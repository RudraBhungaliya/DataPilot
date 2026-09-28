"use client";

import React, { useEffect, useState } from "react";
import {
  Globe,
  Database,
  Layers,
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Server,
  FileCode,
  Hash,
  Play,
  ArrowRight,
  Filter,
  Check,
  Activity,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  fetchSources,
  fetchCollectionJobs,
  fetchDocuments,
  testDiscoverSources,
  triggerDirectCollection,
  resumeCollectionJob,
  SourceDefinition,
  CollectionJob,
  RawDocument,
} from "@/lib/api";

export default function SourcesPage() {
  const [activeTab, setActiveTab] = useState<"sources" | "documents" | "tester">("sources");
  const [sources, setSources] = useState<SourceDefinition[]>([]);
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [documents, setDocuments] = useState<RawDocument[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDoc, setSelectedDoc] = useState<RawDocument | null>(null);
  const [resumingJobId, setResumingJobId] = useState<string | null>(null);

  // Playground state
  const [testQuery, setTestQuery] = useState("Indian AI Startups");
  const [testEntity, setTestEntity] = useState("startups");
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<any>(null);


  const loadData = async () => {
    setLoading(true);
    try {
      const [srcList, jobList, docList] = await Promise.all([
        fetchSources(),
        fetchCollectionJobs(),
        fetchDocuments(),
      ]);
      setSources(srcList);
      setJobs(jobList);
      setDocuments(docList);
    } catch (err) {
      console.error("Failed to load source engine data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunDiscoveryTest = async () => {
    setTestRunning(true);
    setTestResult(null);
    try {
      const res = await testDiscoverSources({
        query: testQuery,
        entity: testEntity,
      });
      setTestResult(res);
      // Refresh list to show newly discovered sources
      loadData();
    } catch (err: any) {
      setTestResult({ success: false, error: err.message });
    } finally {
      setTestRunning(false);
    }
  };

  const handleRunSampleCollection = async () => {
    setTestRunning(true);
    setTestResult(null);
    try {
      const samplePayload = {
        request_id: `req_${Date.now()}`,
        workflow_id: null,
        target_entity: testEntity || "startup",
        search_query: testQuery || "AI startups",
        sources: [
          {
            id: "src_hackernews_test",
            name: "HackerNews API Feed",
            domain: "news.ycombinator.com",
            base_url: "https://hacker-news.firebaseio.com/v0/topstories.json",
            type: "API",
            access_method: "REST_API",
            tier: 2,
            rate_limit_per_minute: 60,
          },
        ],
        parameters: { max_pages: 1 },
      };
      const res = await triggerDirectCollection(samplePayload);
      setTestResult(res);
      loadData();
    } catch (err: any) {
      setTestResult({ success: false, error: err.message });
    } finally {
      setTestRunning(false);
    }
  };

  const handleResumeJob = async (jobId: string) => {
    setResumingJobId(jobId);
    try {
      const res = await resumeCollectionJob(jobId);
      if (res.ok) {
        await loadData();
      } else {
        alert(`Resume failed: ${res.data?.detail || res.error || "Unable to resume"}`);
      }
    } catch (err: any) {
      alert(`Resume error: ${err.message}`);
    } finally {
      setResumingJobId(null);
    }
  };

  const humanActionJobs = jobs.filter(
    (j) => j.status === "HUMAN_ACTION_REQUIRED" || (j as any).human_action_required
  );

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">

      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-[#0c1427] to-[#0a1020] border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/25 text-cyan-400 text-xs font-semibold">
              <Globe className="w-3.5 h-3.5" />
              <span>Phase 4: Source Collection Engine</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Source Connectors & Raw Document Store
            </h1>
            <p className="text-sm text-slate-400">
              Deterministic routing, robots.txt compliance, anti-SSRF protections, sliding-window rate limiters, and content-hashed document repository.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={loading}
              className="border-slate-700 hover:bg-slate-800 text-slate-300"
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Refresh Engine
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Registered Sources</span>
            <Globe className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{sources.length}</div>
          <div className="text-xs text-slate-500 mt-1">Multi-tier capability registry</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Persisted Raw Documents</span>
            <FileCode className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{documents.length}</div>
          <div className="text-xs text-emerald-400/80 mt-1">SHA-256 deduplicated store</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Collection Jobs</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{jobs.length}</div>
          <div className="text-xs text-slate-500 mt-1">Executed pipeline batches</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Compliance Guard</span>
            <ShieldCheck className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-sm font-semibold text-white mt-2">Strict Policy</div>
          <div className="text-xs text-sky-400/80 mt-1">Robots.txt + Anti-SSRF Safe</div>
        </Card>
      </div>

      {/* Human Action Required Notification Banners */}
      {humanActionJobs.map((job) => (
        <div
          key={job.id}
          className="p-6 rounded-2xl bg-amber-500/10 border-2 border-amber-500/40 text-amber-200 shadow-2xl space-y-4"
        >
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                <ShieldCheck className="w-6 h-6" />
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

            <Button
              onClick={() => handleResumeJob(job.id)}
              disabled={resumingJobId === job.id}
              className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold shrink-0 shadow-lg shadow-amber-500/25 px-5"
            >
              <Play className={`w-4 h-4 mr-2 ${resumingJobId === job.id ? "animate-spin" : "fill-current"}`} />
              {resumingJobId === job.id ? "Resuming..." : "Resume Collection"}
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 p-4 bg-slate-950/70 rounded-xl border border-amber-500/20 text-xs font-mono">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Source Name</span>
              <span className="text-slate-200 font-semibold">{job.checkpoint?.source_name || (job as any).source?.name || "Protected Source"}</span>
            </div>
            <div className="md:col-span-2">
              <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Source URL (Open in browser)</span>
              <a
                href={job.checkpoint?.source_url || (job as any).source?.base_url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-cyan-400 hover:underline flex items-center gap-1 truncate"
              >
                <span className="truncate">{job.checkpoint?.source_url || (job as any).source?.base_url || "N/A"}</span>
                <ExternalLink className="w-3.5 h-3.5 shrink-0" />
              </a>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase font-sans font-medium">Task ID & Status</span>
              <span className="text-amber-400 font-semibold">{job.id} (HUMAN_ACTION_REQUIRED)</span>
            </div>
          </div>
        </div>
      ))}

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-800 gap-4">

        <button
          onClick={() => setActiveTab("sources")}
          className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
            activeTab === "sources"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Registered Sources ({sources.length})
        </button>
        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
            activeTab === "documents"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Raw Documents ({documents.length})
        </button>
        <button
          onClick={() => setActiveTab("tester")}
          className={`pb-3 text-sm font-medium transition-colors border-b-2 ${
            activeTab === "tester"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Live Engine Playground
        </button>
      </div>

      {/* Tab 1: Sources Registry */}
      {activeTab === "sources" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Deterministic multi-tiered access registry with domain rate limiting</span>
            <span>Seed registries automatically initialize on boot</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sources.map((src) => (
              <Card
                key={src.id}
                className="border-slate-800/80 bg-slate-900/40 p-5 hover:border-slate-700 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-white text-base">{src.name}</h3>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">{src.domain}</p>
                    </div>
                    <Badge
                      className={
                        src.status === "ACTIVE"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }
                    >
                      {src.status}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-slate-800/60 text-xs">
                    <div>
                      <span className="text-slate-500">Access Method:</span>{" "}
                      <span className="text-slate-300 font-mono">{src.access_method}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Tier:</span>{" "}
                      <span className="text-cyan-400 font-medium">Tier {src.tier}</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Rate Limit:</span>{" "}
                      <span className="text-slate-300">{src.rate_limit_per_minute}/min</span>
                    </div>
                    <div>
                      <span className="text-slate-500">Pagination:</span>{" "}
                      <span className="text-slate-300">{src.supports_pagination ? "Supported" : "Single Page"}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/40 flex items-center justify-between text-[11px] text-slate-500">
                  <span>Success Rate: {Math.round(src.success_rate * 100)}%</span>
                  <span className="font-mono text-slate-600">{src.id}</span>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Raw Documents Repository */}
      {activeTab === "documents" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Documents captured during workflow execution and direct collection</span>
            <span>All payloads stored with SHA-256 content hashes</span>
          </div>

          {documents.length === 0 ? (
            <Card className="border-slate-800 bg-slate-900/40 p-12 text-center">
              <FileCode className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-white">No Collected Documents Yet</h3>
              <p className="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-5">
                Run a workflow on the Dashboard or trigger a sample collection from the Playground tab to collect and store raw documents.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveTab("tester")}
                className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10"
              >
                Go to Collection Playground
              </Button>
            </Card>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <Card
                  key={doc.id}
                  className="border-slate-800 bg-slate-900/40 p-4 hover:border-slate-700 transition-all"
                >
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="space-y-1 max-w-2xl">
                      <div className="flex items-center gap-2">
                        <Badge
                          className={
                            doc.status_code === 200
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                              : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                          }
                        >
                          HTTP {doc.status_code}
                        </Badge>
                        <span className="text-xs font-mono text-cyan-400 truncate max-w-md">
                          {doc.url}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span>MIME: <span className="text-slate-400 font-mono">{doc.content_type}</span></span>
                        <span>Job: <span className="text-slate-400 font-mono">{doc.job_id}</span></span>
                        <span>Hash: <span className="text-slate-400 font-mono">{doc.content_hash.slice(0, 12)}...</span></span>
                        <span>{new Date(doc.collected_at).toLocaleTimeString()}</span>
                      </div>
                    </div>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setSelectedDoc(doc)}
                      className="border-slate-700 hover:bg-slate-800 text-slate-300 text-xs self-start md:self-auto"
                    >
                      Inspect Raw Payload
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {/* Document Content Modal */}
          {selectedDoc && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
              <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-3xl w-full max-h-[80vh] flex flex-col shadow-2xl overflow-hidden">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Raw Document Inspector</h3>
                    <p className="text-xs text-slate-400 font-mono mt-0.5 truncate max-w-lg">{selectedDoc.url}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedDoc(null)}
                    className="text-slate-400 hover:text-white"
                  >
                    Close
                  </Button>
                </div>
                <div className="p-4 overflow-auto flex-1 font-mono text-xs text-slate-300 bg-slate-950/40">
                  <pre className="whitespace-pre-wrap break-all">
                    {selectedDoc.content || "(No raw content preview stored)"}
                  </pre>
                </div>
                <div className="p-3 border-t border-slate-800 text-xs text-slate-500 flex justify-between bg-slate-950/60">
                  <span>SHA-256: {selectedDoc.content_hash}</span>
                  <span>Collected: {selectedDoc.collected_at}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Interactive Collection Playground */}
      {activeTab === "tester" && (
        <div className="space-y-6">
          <Card className="border-slate-800 bg-slate-900/40 p-6 space-y-4">
            <div>
              <h3 className="text-base font-semibold text-white">Source Collection Engine Playground</h3>
              <p className="text-xs text-slate-400 mt-1">
                Directly trigger Phase 4 discovery or collection endpoints without going through the full AI workflow planner.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1">Search Query / Prompt</label>
                <input
                  type="text"
                  value={testQuery}
                  onChange={(e) => setTestQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  placeholder="e.g. Indian AI startups, python internships"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400 block mb-1">Target Entity Keyword</label>
                <input
                  type="text"
                  value={testEntity}
                  onChange={(e) => setTestEntity(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
                  placeholder="e.g. startup, internship, funding"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                onClick={handleRunDiscoveryTest}
                disabled={testRunning}
                className="bg-cyan-600 hover:bg-cyan-500 text-white"
              >
                <Search className={`w-4 h-4 mr-2 ${testRunning ? "animate-spin" : ""}`} />
                Test Source Discovery (POST /collection/discover)
              </Button>

              <Button
                onClick={handleRunSampleCollection}
                disabled={testRunning}
                variant="outline"
                className="border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/10"
              >
                <Play className={`w-4 h-4 mr-2 ${testRunning ? "animate-spin" : ""}`} />
                Test Live Collector (POST /collection/execute)
              </Button>
            </div>
          </Card>

          {/* Test Execution Output */}
          {testResult && (
            <Card className="border-slate-800 bg-slate-950/80 p-5 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <span className="text-xs font-semibold text-cyan-400 flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5" /> Engine Response Output
                </span>
                <Badge
                  className={
                    testResult.success !== false
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  }
                >
                  {testResult.success !== false ? "SUCCESS" : "ERROR"}
                </Badge>
              </div>
              <pre className="text-xs font-mono text-slate-300 overflow-auto max-h-96 p-3 bg-slate-900/60 rounded-lg border border-slate-800/60">
                {JSON.stringify(testResult, null, 2)}
              </pre>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
