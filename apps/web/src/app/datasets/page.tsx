"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  Database,
  RefreshCw,
  FileCode,
  Download,
  Layers,
  CheckCircle2,
  Copy,
  Hash,
  Search,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import {
  fetchDatasets,
  fetchDatasetRecords,
  datasetExportUrl,
  DatasetSummary,
  DatasetRecord,
} from "@/lib/api";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selected, setSelected] = useState<DatasetSummary | null>(null);
  const [records, setRecords] = useState<DatasetRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState<boolean>(false);
  const [filter, setFilter] = useState<string>("");

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

  const openDataset = async (dataset: DatasetSummary) => {
    setSelected(dataset);
    setRecords([]);
    setRecordsLoading(true);
    try {
      const res = await fetchDatasetRecords(dataset.id, 200, 0);
      setRecords(res.records);
    } finally {
      setRecordsLoading(false);
    }
  };

  const totalRecords = useMemo(
    () => datasets.reduce((sum, d) => sum + (d.record_count || 0), 0),
    [datasets]
  );
  const entityCount = useMemo(() => new Set(datasets.map((d) => d.entity)).size, [datasets]);

  const filtered = datasets.filter(
    (d) =>
      d.name.toLowerCase().includes(filter.toLowerCase()) ||
      d.entity.toLowerCase().includes(filter.toLowerCase())
  );

  const columns = useMemo(() => {
    if (selected?.schema_fields?.length) return selected.schema_fields;
    const keys = new Set<string>();
    records.slice(0, 20).forEach((r) => Object.keys(r.data || {}).forEach((k) => keys.add(k)));
    return Array.from(keys);
  }, [selected, records]);

  return (
    <div className="space-y-8 max-w-6xl mx-auto pb-12">
      {/* Header */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-[#0c1427] to-[#0a1020] border border-slate-800 p-6 md:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/25 text-indigo-300 text-xs font-semibold">
              <Database className="w-3.5 h-3.5" />
              <span>Phase 5: Data Intelligence Pipeline</span>
            </div>
            <h1 className="text-3xl font-extrabold text-white tracking-tight">
              Compiled Datasets
            </h1>
            <p className="text-sm text-slate-400">
              Clean, normalized, validated and deduplicated records compiled from collected raw
              documents — with source provenance and CSV/JSON export.
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

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Datasets</span>
            <Database className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{datasets.length}</div>
          <div className="text-xs text-slate-500 mt-1">Compiled artifacts</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Records</span>
            <Layers className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{totalRecords}</div>
          <div className="text-xs text-emerald-400/80 mt-1">Validated &amp; unique</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Entities</span>
            <FileCode className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">{entityCount}</div>
          <div className="text-xs text-slate-500 mt-1">Distinct target types</div>
        </Card>

        <Card className="border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400 font-medium">Delivery</span>
            <Download className="w-4 h-4 text-teal-400" />
          </div>
          <div className="text-sm font-semibold text-white mt-2">CSV / JSON</div>
          <div className="text-xs text-teal-400/80 mt-1">One-click export</div>
        </Card>
      </div>

      {/* Search */}
      {datasets.length > 0 && (
        <div className="relative max-w-md">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter datasets by name or entity..."
            className="w-full bg-slate-900/90 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500/50"
          />
        </div>
      )}

      {/* Empty / list */}
      {loading ? (
        <Card className="border-slate-800 bg-slate-900/40 p-12 text-center text-sm text-slate-400">
          Loading datasets...
        </Card>
      ) : filtered.length === 0 ? (
        <Card className="border-slate-800 bg-slate-900/40 p-12 text-center">
          <Database className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-white">No datasets yet</h3>
          <p className="text-sm text-slate-400 max-w-md mx-auto mt-1">
            Run a workflow from the Dashboard through its extraction, validation, deduplication
            and dataset-building steps to compile your first dataset.
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((dataset) => (
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
                  <span className="text-slate-500 block">Format</span>
                  <span className="text-slate-200 font-mono uppercase">{dataset.output_format}</span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-800/40 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  {dataset.duplicate_count} duplicates removed
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-indigo-300 hover:text-white"
                  onClick={(e) => {
                    e.stopPropagation();
                    openDataset(dataset);
                  }}
                >
                  Inspect records →
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-5xl w-full max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            <div className="p-4 border-b border-slate-800 flex items-start justify-between bg-slate-950/60">
              <div>
                <h3 className="text-sm font-semibold text-white">{selected.name}</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  {selected.record_count} records · entity <span className="font-mono">{selected.entity}</span> ·{" "}
                  <span className="font-mono">{selected.id}</span>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <a href={datasetExportUrl(selected.id, "csv")} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>
                    CSV
                  </Button>
                </a>
                <a href={datasetExportUrl(selected.id, "json")} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm" icon={<Download className="w-3.5 h-3.5" />}>
                    JSON
                  </Button>
                </a>
                <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
                  Close
                </Button>
              </div>
            </div>

            <div className="p-4 overflow-auto flex-1">
              {/* Field coverage: shows what the collected sources actually provided */}
              {selected.metadata?.field_coverage &&
                Object.keys(selected.metadata.field_coverage as Record<string, number>).length > 0 && (
                  <div className="mb-4 p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                    <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-400 mb-2">
                      Field coverage
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(selected.metadata.field_coverage as Record<string, number>).map(
                        ([field, pct]) => (
                          <span
                            key={field}
                            title={pct === 0 ? "Not found in any collected source" : undefined}
                            className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
                              pct >= 0.5
                                ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/30"
                                : pct > 0
                                ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                                : "bg-rose-500/10 text-rose-300 border-rose-500/30"
                            }`}
                          >
                            {field}: {Math.round(pct * 100)}%
                          </span>
                        )
                      )}
                    </div>
                    {selected.metadata?.mean_completeness !== undefined && (
                      <div className="text-[11px] text-slate-500 mt-2">
                        Mean completeness:{" "}
                        {Math.round((selected.metadata.mean_completeness as number) * 100)}%
                      </div>
                    )}
                  </div>
                )}
              {recordsLoading ? (
                <p className="text-sm text-slate-400">Loading records...</p>
              ) : records.length === 0 ? (
                <p className="text-sm text-slate-400">No records in this dataset.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                      {columns.map((col) => (
                        <th key={col} className="pb-2 pr-4 font-semibold whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                      <th className="pb-2 pr-4 font-semibold">Source</th>
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
                          {record.source_url ? (
                            <a
                              href={record.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sky-400 hover:underline inline-flex items-center gap-1 max-w-[16rem] truncate"
                            >
                              <CheckCircle2 className="w-3 h-3 shrink-0 text-emerald-400" />
                              <span className="truncate">{record.source_url}</span>
                              <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                          ) : (
                            <span className="text-slate-500">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="p-3 border-t border-slate-800 text-xs text-slate-500 flex items-center justify-between bg-slate-950/60 font-mono">
              <span className="inline-flex items-center gap-1.5">
                <Hash className="w-3 h-3" /> confidence avg{" "}
                {records.length
                  ? (records.reduce((s, r) => s + (r.confidence || 0), 0) / records.length).toFixed(2)
                  : "—"}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Copy className="w-3 h-3" /> {selected.duplicate_count} duplicates · {selected.valid_count} valid
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
