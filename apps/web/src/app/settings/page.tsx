"use client";

import React, { useEffect, useState } from "react";
import { Settings, Server, Database, HardDrive, ShieldCheck, Key, CheckCircle2, Plus, Trash2, Power } from "lucide-react";
import { Card, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  fetchHealth,
  fetchApiRoot,
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  getApiKey,
  setApiKey,
  HealthData,
  ApiRootData,
  ApiKeyRecord,
} from "@/lib/api";

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [apiInfo, setApiInfo] = useState<ApiRootData | null>(null);
  const [keys, setKeys] = useState<ApiKeyRecord[]>([]);
  const [newKeyName, setNewKeyName] = useState("dashboard-key");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);
  const [activeKey, setActiveKeyState] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadKeys = async () => setKeys(await fetchApiKeys());

  useEffect(() => {
    fetchHealth().then(setHealth);
    fetchApiRoot().then(setApiInfo);
    setActiveKeyState(getApiKey());
    loadKeys();
  }, []);

  const handleCreateKey = async () => {
    setBusy(true);
    try {
      const created = await createApiKey(newKeyName || "dashboard-key");
      if (created) {
        setIssuedKey(created.api_key);
        await loadKeys();
      }
    } finally {
      setBusy(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    setBusy(true);
    try {
      await revokeApiKey(keyId);
      await loadKeys();
    } finally {
      setBusy(false);
    }
  };

  const handleUseKey = (key: string | null) => {
    setApiKey(key);
    setActiveKeyState(key);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
            <Settings className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">System Settings</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Configuration, service endpoints, and environment variables
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Backend & API Settings */}
        <Card>
          <CardHeader
            title="FastAPI Configuration"
            subtitle="Backend runtime parameters"
            action={<Badge variant="info">FastAPI</Badge>}
          />
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">API Prefix</span>
              <span className="font-mono text-sky-400">/api/v1</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">Backend Port</span>
              <span className="font-mono text-slate-200">8000</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">Environment</span>
              <span className="font-mono text-emerald-400">{health?.environment || "development"}</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">CORS Allowed</span>
              <span className="font-mono text-slate-200">http://localhost:3000</span>
            </div>
          </div>
        </Card>

        {/* Database & Cache */}
        <Card>
          <CardHeader
            title="Database & Redis Cache"
            subtitle="Infrastructure connection specs"
            action={<Badge variant="info">Docker Ready</Badge>}
          />
          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">PostgreSQL Host</span>
              <span className="font-mono text-slate-200">localhost:5432</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">PostgreSQL Status</span>
              <Badge variant={health?.services.database === "connected" ? "success" : "neutral"} size="sm">
                {health?.services.database || "Ready"}
              </Badge>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800/60">
              <span className="text-slate-400">Redis Host</span>
              <span className="font-mono text-slate-200">localhost:6379</span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Redis Status</span>
              <Badge variant={health?.services.redis === "connected" ? "success" : "neutral"} size="sm">
                {health?.services.redis || "Ready"}
              </Badge>
            </div>
          </div>
        </Card>

        {/* AI & Worker Engines (Phase 2 preview) */}
        <Card className="md:col-span-2">
          <CardHeader
            title="Future Modules (Phase 2 Configuration)"
            subtitle="LLM providers and scraping worker cluster configuration"
            action={<Badge variant="neutral">Upcoming</Badge>}
          />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <div className="flex items-center gap-2 mb-1.5 text-slate-200 font-semibold text-xs">
                <Key className="w-4 h-4 text-sky-400" />
                <span>LLM Providers</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Gemini, OpenAI, Anthropic orchestration keys configuration
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <div className="flex items-center gap-2 mb-1.5 text-slate-200 font-semibold text-xs">
                <Server className="w-4 h-4 text-indigo-400" />
                <span>Worker Pool</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Celery / Redis background queue concurrency parameters
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <div className="flex items-center gap-2 mb-1.5 text-slate-200 font-semibold text-xs">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Proxy & Rate Limits</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Rotating residential proxy pools and domain request limits
              </p>
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="API Access"
          subtitle="Manage API keys. When AUTH_ENABLED is on, every API request must send X-API-Key."
          action={
            <Badge variant="info">
              <Key className="w-3 h-3" /> Auth
            </Badge>
          }
        />

        <div className="space-y-4 text-xs">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name"
              className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500/50"
            />
            <Button size="sm" onClick={handleCreateKey} disabled={busy} icon={<Plus className="w-3.5 h-3.5" />}>
              Create key
            </Button>
          </div>

          {issuedKey && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300">
              <div className="font-semibold mb-1">New key (shown once)</div>
              <code className="font-mono break-all text-emerald-200">{issuedKey}</code>
              <div className="mt-2">
                <Button size="sm" variant="outline" onClick={() => handleUseKey(issuedKey)}>
                  Use this key in the dashboard
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {keys.length === 0 ? (
              <p className="text-slate-500">No API keys yet.</p>
            ) : (
              keys.map((k) => (
                <div
                  key={k.id}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/60 border border-slate-800"
                >
                  <div>
                    <span className="text-slate-200 font-medium">{k.name}</span>
                    <span className="text-slate-500 font-mono ml-2">{k.key_prefix}…</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={k.is_active ? "success" : "neutral"}>
                      {k.is_active ? "active" : "revoked"}
                    </Badge>
                    {k.is_active && (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => handleRevoke(k.id)}
                        disabled={busy}
                        icon={<Trash2 className="w-3.5 h-3.5" />}
                      >
                        Revoke
                      </Button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-800">
            <span className="text-slate-500">
              Dashboard key:{" "}
              <span className="font-mono text-slate-300">
                {activeKey ? `${activeKey.slice(0, 10)}…` : "not set"}
              </span>
            </span>
            {activeKey && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleUseKey(null)}
                icon={<Power className="w-3.5 h-3.5" />}
              >
                Clear
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
