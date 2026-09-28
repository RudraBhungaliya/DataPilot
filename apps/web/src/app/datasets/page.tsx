"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Database,
  RefreshCw,
  FileCode,
  Download,
  Layers,
  Hash,
  Search,
  ExternalLink,
  Link2,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  fetchDatasets,
  fetchDatasetRecords,
  fetchRecordEvidence,
  datasetExportUrl,
  DatasetSummary,
  DatasetRecord,
  RecordEvidence,
} from "@/lib/api";

const PAGE_SIZE = 25;

function coverageClass(pct: number): string {
  if (pct >= 0.5) return "bg-emerald-500/10 text-emerald-300 border-emerald-500/30";
  if (pct > 0) return "bg-amber-500/10 text-amber-300 border-amber-500/30";
  return "bg-rose-500/10 text-rose-300 border-rose-500/30";
}

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Selected dataset + record browser
  const [selected, setSelected] = useState<DatasetSummary | null>(null);
  const [records, setRecords] = useState<DatasetRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [recordsLoading, setRecordsLoading] = useState<boolean>(false);
  const [query, setQuery] = useState<string>("");
  const [sortField, setSortField] = useState<string>("");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [offset, setOffset] = useState<number>(0);
  const [evidence, setEvidence] = useState<RecordEvidence | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState<boolean>(false);

  const loadDatasets = async () => {
    setLoading(true);
    try {
      setDatasets(await fetchDatasets());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadRecords = useCallback(
    async (dataset: DatasetSummary, opts?: { q?: string; sort?: string; order?: "asc" | "desc"; offset?: number }) => {
      setRecordsLoading(true);
      try {
        const res = await fetchDatasetRecords(dataset.id, {
          q: opts?.q ?? query,
          sort: opts?.sort ?? sortField,
          order: opts?.order ?? order,
          limit: PAGE_SIZE,
          offset: opts?.offset ?? offset,
        });
        setRecords(res.records);
        setTotal(res.total);
      } finally {
        setRecordsLoading(false);
      }
    },
    [query, sortField, order, offset]
  );

  const openDataset = async (dataset: DatasetSummary) => {
    setSelected(dataset);
    setRecords([]);
    setTotal(0);
    setQuery("");
    setSortField("");
    setOrder("asc");
    setOffset(0);
    setEvidence(null);
    setRecordsLoading(true);
    try {
      const res = await fetchDatasetRecords(dataset.id, { limit: PAGE_SIZE, offset: 0 });
      setRecords(res.records);
      setTotal(res.total);
    } finally {
      setRecordsLoading(false);
    }
  };

  const applySearch = async () => {
    if (!selected) return;
    setOffset(0);
    await loadRecords(selected, { q: query, offset: 0 });
  };

  const changeSort = async (field: string) => {
    if (!selected) return;
    const nextOrder: "asc" | "desc" = sortField === field && order === "asc" ? "desc" : "asc";
    setSortField(field);
    setOrder(nextOrder);
    setOffset(0);
    await loadRecords(selected, { sort: field, order: nextOrder, offset: 0 });
  };

  const goToPage = async (nextOffset: number) => {
    if (!selected || nextOffset < 0) return;
    setOffset(nextOffset);
    await loadRecords(selected, { offset: nextOffset });
  };

  const showEvidence = async (record: DatasetRecord) => {
    if (!selected) return;
    setEvidenceLoading(true);
    setEvidence(null);
    try {
      setEvidence(await fetchRecordEvidence(selected.id, record.record_id));
    } finally {
      setEvidenceLoading(false);
    }
  };

  const totalRecords = useMemo(
    () => datasets.reduce((sum, d) => sum + (d.record_count || 0), 0),
    [datasets]
  );
  const entityCount = useMemo(() => new Set(datasets.map((d) => d.entity)).size, [datasets]);

  const filteredDatasets = datasets.filter(
    (d) =>
      d.name.toLowerCase().includes(query.toLowerCase()) ||
      d.entity.toLowerCase().includes(query.toLowerCase())
  );

  const columns = useMemo(() => {
    if (selected?.schema_fields?.length) return selected.schema_fields;
    const keys = new Set<string>();
    records.slice(0, 20).forEach((r) => Object.keys(r.data || {}).forEach((k) => keys.add(k)));
    return Array.from(keys);
  }, [selected, records]);

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-[#0c1427] to-[#0a1020] border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs font-semibold">
              <Database className="w-3.5 h-3.5" />
              <span>Phase 6: Dataset &amp; Evidence Platform</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">Compiled Datasets</h1>
            <p className="text-sm text-slate-400">
              Search, filter, sort and trace every record back to its source document. Export as CSV,
              JSON or JSONL.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadDatasets}
            disabled={loading}
            className="border-slate-700 hover:bg-slate-800 text-slate-300"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Datasets</span>
            <Database className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{datasets.length}</div>
        </Card>
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Records</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{totalRecords}</div>
        </Card>
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Entities</span>
            <FileCode className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{entityCount}</div>
        </Card>
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Delivery</span>
            <Download className="w-4 h-4 text-teal-400" />
          </div>
          <div className="text-sm font-semibold text-white mt-2">CSV / JSON / JSONL</div>
        </Card>
      </div>

      {loading ? (
        <Card className="border-slate-800 bg-slate-900/40 p-12 text-center text-sm text-slate-400">
          Loading datasets...
        </Card>
      ) : filteredDatasets.length === 0 ? (
        <Card className="border-slate-800 bg-slate-900/40 p-12 text-center">
          <Database className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No datasets yet</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto mt-1">
            Run a workflow from the Dashboard to compile your first dataset.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredDatasets.map((dataset) => (
            <Card
              key={dataset.id}
              className="border-slate-800/80 bg-slate-900/40 p-5 hover:border-indigo-500/30 transition-all cursor-pointer"
              onClick={() => openDataset(dataset)}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-white text-base">{dataset.name}</h3>
                  <p className="text-xs text-slate-400 font-mono mt-0.5">{dataset.id}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className="bg-slate-800 text-slate-300 border-slate-700">v{dataset.version}</Badge>
                  <Badge
                    className={
                      dataset.status === "READY"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    }
                  >
                    {dataset.status}
                  </Badge>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 mt-4 pt-4 border-t border-slate-800/60 text-xs">
                <div>
                  <span className="text-slate-500 block">Entity</span>
                  <span className="text-slate-200 font-medium uppercase">{dataset.entity}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Records</span>
                  <span className="text-emerald-400 font-mono">{dataset.record_count}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Duplicates</span>
                  <span className="text-slate-300 font-mono">{dataset.duplicate_count}</span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-5xl w-full max-h-[88vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-slate-950/60">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  {selected.name}
                  <Badge className="bg-slate-800 text-slate-300 border-slate-700">v{selected.version}</Badge>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {total} matching records · entity <span className="font-mono">{selected.entity}</span>
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <a href={datasetExportUrl(selected.id, "csv")} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>CSV</Button>
                </a>
                <a href={datasetExportUrl(selected.id, "json")} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>JSON</Button>
                </a>
                <a href={datasetExportUrl(selected.id, "jsonl")} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>JSONL</Button>
                </a>
                <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>Close</Button>
              </div>
            </div>

            <div className="p-4 overflow-auto flex-1">
              {/* Coverage */}
              {selected.metadata?.field_coverage &&
                Object.keys(selected.metadata.field_coverage as Record<string, number>).length > 0 && (
                  <div className="mb-3 p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-2">
                      Field coverage
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(selected.metadata.field_coverage as Record<string, number>).map(([f, pct]) => (
                        <span key={f} className={`px-2 py-0.5 rounded text-[11px] font-mono border ${coverageClass(pct)}`}>
                          {f}: {Math.round(pct * 100)}%
                        </span>
                      ))}
                    </div>
                  </div>
                )}

              {/* Search + sort */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 mb-3">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && applySearch()}
                    placeholder="Search records..."
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500/50"
                  />
                </div>
                <Button variant="secondary" size="sm" onClick={applySearch}>Search</Button>
              </div>

              {recordsLoading ? (
                <p className="text-sm text-slate-400 py-6 text-center">Loading records...</p>
              ) : records.length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No matching records.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                      {columns.map((col) => (
                        <th
                          key={col}
                          onClick={() => changeSort(col)}
                          className="pb-2 pr-4 font-semibold whitespace-nowrap cursor-pointer hover:text-slate-200"
                        >
                          <span className="inline-flex items-center gap-1">
                            {col}
                            <ArrowUpDown className={`w-3 h-3 ${sortField === col ? "text-indigo-400" : "text-slate-600"}`} />
                          </span>
                        </th>
                      ))}
                      <th className="pb-2 pr-4 font-semibold">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {records.map((record) => (
                      <tr key={record.record_id} className="hover:bg-slate-800/30">
                        {columns.map((col) => (
                          <td key={col} className="py-2 pr-4 text-slate-200 max-w-xs truncate">
                            {record.data?.[col] === null || record.data?.[col] === undefined
                              ? "—"
                              : String(record.data[col])}
                          </td>
                        ))}
                        <td className="py-2 pr-4">
                          <button
                            onClick={() => showEvidence(record)}
                            className="inline-flex items-center gap-1 text-indigo-300 hover:text-white"
                          >
                            <Link2 className="w-3 h-3" /> View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            {/* Pagination */}
            <div className="p-3 border-t border-slate-800 flex items-center justify-between bg-slate-950/60 text-xs text-slate-400">
              <span className="font-mono">
                {total === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)}`} of {total}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" disabled={offset === 0 || recordsLoading} onClick={() => goToPage(offset - PAGE_SIZE)}>
                  <ChevronLeft className="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={offset + PAGE_SIZE >= total || recordsLoading}
                  onClick={() => goToPage(offset + PAGE_SIZE)}
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
          </div>

          {/* Evidence panel */}
          {(evidence || evidenceLoading) && (
            <div className="absolute right-4 top-4 bottom-4 w-full max-w-md bg-slate-950 border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden">
              <div className="p-3 border-b border-slate-800 flex items-center justify-between">
                <span className="text-xs font-semibold text-white inline-flex items-center gap-1.5">
                  <Link2 className="w-3.5 h-3.5 text-indigo-400" /> Evidence &amp; Lineage
                </span>
                <Button variant="ghost" size="sm" onClick={() => setEvidence(null)}>Close</Button>
              </div>
              <div className="p-3 overflow-auto flex-1 text-xs space-y-3">
                {evidenceLoading || !evidence ? (
                  <p className="text-slate-400">Loading evidence...</p>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <Badge className="bg-slate-800 text-slate-300 border-slate-700">
                        {evidence.extraction_method}
                      </Badge>
                      <Badge className="bg-slate-800 text-slate-300 border-slate-700">
                        confidence {evidence.confidence?.toFixed(2)}
                      </Badge>
                      <Badge className="bg-slate-800 text-slate-300 border-slate-700">
                        completeness {Math.round((evidence.completeness || 0) * 100)}%
                      </Badge>
                    </div>

                    {evidence.missing_fields?.length > 0 && (
                      <div className="text-rose-300">
                        Missing: <span className="font-mono">{evidence.missing_fields.join(", ")}</span>
                      </div>
                    )}

                    <div>
                      <div className="text-slate-500 uppercase text-[10px] mb-1">Record data</div>
                      <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-300 overflow-auto max-h-40">
                        {JSON.stringify(evidence.data, null, 2)}
                      </pre>
                    </div>

                    <div>
                      <div className="text-slate-500 uppercase text-[10px] mb-1">Evidence sources</div>
                      <div className="space-y-2">
                        {evidence.evidence.map((ev, i) => (
                          <div key={i} className="p-2 rounded bg-slate-900 border border-slate-800">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-slate-200 truncate">{ev.source_type}</span>
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-mono border ${
                                  ev.verification_status === "observed"
                                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                                    : "bg-amber-500/10 text-amber-300 border-amber-500/30"
                                }`}
                              >
                                {ev.verification_status}
                              </span>
                            </div>
                            {ev.source && (
                              <a
                                href={ev.source}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sky-400 hover:underline break-all inline-flex items-center gap-1 mt-1"
                              >
                                {ev.source.slice(0, 60)} <ExternalLink className="w-3 h-3 shrink-0" />
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {evidence.document?.excerpt && (
                      <div>
                        <div className="text-slate-500 uppercase text-[10px] mb-1">Raw document excerpt</div>
                        <pre className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-400 overflow-auto max-h-40 whitespace-pre-wrap">
                          {evidence.document.excerpt}
                        </pre>
                        <div className="text-[10px] text-slate-500 mt-1 inline-flex items-center gap-1">
                          <Hash className="w-3 h-3" /> {evidence.document.content_hash}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
