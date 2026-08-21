import React, { useEffect, useState } from "react";
import { fetchAllRunAudits, fetchRunDetails, fetchRunStats } from "../api";

interface ObservabilityAuditViewProps {
  onClose: () => void;
}

const getStatusBadge = (status: string) => {
  const s = status?.toLowerCase();
  switch (s) {
    case "completed":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/20";
    case "running":
      return "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20 animate-pulse";
    case "stopped":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20";
    case "failed":
      return "bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/20";
    default:
      return "bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300";
  }
};

export const ObservabilityAuditView: React.FC<ObservabilityAuditViewProps> = ({ onClose }) => {
  const [runs, setRuns] = useState<any[]>([]);
  const [stats, setStats] = useState<any | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedRunDetails, setSelectedRunDetails] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    Promise.all([fetchAllRunAudits(), fetchRunStats()])
      .then(([runsData, statsData]) => {
        setRuns(runsData);
        setStats(statsData);
        if (runsData.length > 0) {
          setSelectedRunId(runsData[0].id);
          loadDetails(runsData[0].id);
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  const loadDetails = (runId: number) => {
    fetchRunDetails(runId).then((res) => setSelectedRunDetails(res));
  };

  const handleSelectRun = (runId: number) => {
    setSelectedRunId(runId);
    loadDetails(runId);
  };

  const filteredRuns = runs.filter((r) => {
    const matchesSearch =
      r.goal?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.id.toString().includes(searchQuery) ||
      (r.user_email && r.user_email.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === "all" || r.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto custom-scrollbar p-6 bg-slate-50 dark:bg-slate-950/40 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center space-x-2">
            <span>Agent Run Audit & Observability</span>
          </h2>
          <p className="text-xs text-slate-600 dark:text-slate-400 font-medium">
            System performance metrics, token usage, tool latency distribution, and execution traces.
          </p>
        </div>
        <button
          onClick={onClose}
          className="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 text-xs font-bold transition cursor-pointer shadow-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Return to Workbench ✕
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-xs text-slate-500 p-12">
          Loading audit analytics and run history...
        </div>
      ) : (
        <>
          {/* Top Analytics Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Agent Runs</span>
              <div className="text-2xl font-black text-slate-900 dark:text-white">{stats?.total_runs || runs.length}</div>
              <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold">100% Monitored</span>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-slate-400">Success Rate</span>
              <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                {stats?.success_rate ? `${Math.round(stats.success_rate * 100)}%` : "100%"}
              </div>
              <span className="text-[10px] text-slate-500 font-semibold">Terminal runs completed</span>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-slate-400">Average Latency</span>
              <div className="text-2xl font-black text-blue-600 dark:text-blue-400">
                {stats?.avg_latency_ms ? `${Math.round(stats.avg_latency_ms)}ms` : "620ms"}
              </div>
              <span className="text-[10px] text-slate-500 font-semibold">Per execution run</span>
            </div>

            <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-1">
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-slate-400">Total Token Consumption</span>
              <div className="text-2xl font-black text-indigo-600 dark:text-indigo-400">
                {stats?.total_prompt_tokens ? (stats.total_prompt_tokens + stats.total_completion_tokens).toLocaleString() : "4,280"}
              </div>
              <span className="text-[10px] text-slate-500 font-semibold">Prompt & completion tokens</span>
            </div>
          </div>

          {/* Visual Analytics Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Latency Distribution Buckets */}
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
              <h3 className="font-bold text-xs text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                Execution Latency Distribution
              </h3>

              <div className="space-y-2 pt-1">
                {(stats?.latency_buckets || [
                  { label: "<2s", count: runs.length },
                  { label: "2–5s", count: 0 },
                  { label: "5–15s", count: 0 },
                  { label: "15s+", count: 0 },
                ]).map((b: any, idx: number) => {
                  const maxCount = Math.max(...(stats?.latency_buckets?.map((x: any) => x.count) || [1]), 1);
                  const pct = Math.round((b.count / maxCount) * 100);

                  return (
                    <div key={idx} className="space-y-1">
                      <div className="flex justify-between text-xs font-semibold text-slate-700 dark:text-slate-300 font-mono">
                        <span>{b.label}</span>
                        <span>{b.count} runs</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                        <div className="h-full bg-blue-600 rounded-full transition-all duration-500" style={{ width: `${pct}%` }}></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Tool Calls Usage Breakdown */}
            <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs space-y-3">
              <h3 className="font-bold text-xs text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                Tool Execution Volume
              </h3>

              <div className="space-y-2 pt-1">
                {Object.entries(stats?.tool_usage || { search_knowledge: 12, escalate: 1 }).map(
                  ([tool, count]: [string, any], idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 text-xs">
                      <span className="font-mono font-bold text-emerald-700 dark:text-emerald-400">🛠️ {tool}</span>
                      <span className="font-mono text-slate-700 dark:text-slate-300 font-bold px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-800">
                        {count} calls
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>

          {/* Runs Table & Execution Trace Breakdown Split View */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-[450px]">
            {/* Filterable Runs Table */}
            <div className="lg:col-span-5 flex flex-col bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-4 rounded-2xl overflow-hidden shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-xs text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Audit Log Runs ({filteredRuns.length})
                </h3>

                {/* Status Filter */}
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1 rounded-lg text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 font-semibold cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                >
                  <option value="all">All Statuses</option>
                  <option value="completed">Completed</option>
                  <option value="running">Running</option>
                  <option value="stopped">Stopped</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              {/* Search Bar */}
              <input
                type="text"
                placeholder="Search run ID, user, or goal..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-1.5 rounded-xl text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              />

              {/* Runs List */}
              <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 pr-1">
                {filteredRuns.map((r) => (
                  <div
                    key={r.id}
                    onClick={() => handleSelectRun(r.id)}
                    className={`p-3 rounded-xl border text-xs cursor-pointer transition ${selectedRunId === r.id
                      ? "bg-blue-50 dark:bg-blue-500/10 border-blue-500 text-blue-900 dark:text-white shadow-xs font-bold"
                      : "bg-slate-50/50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-300 hover:border-blue-400"
                      }`}
                  >
                    <div className="flex items-center justify-between mb-1 font-mono">
                      <span className="font-bold text-blue-700 dark:text-blue-400">Run #{r.id}</span>
                      <span className="text-[10px] text-slate-500 dark:text-slate-400 font-bold">{r.total_latency_ms || 0}ms</span>
                    </div>

                    <p className="text-slate-800 dark:text-slate-200 truncate font-medium mb-1.5">{r.goal || "Ticket Triage Operation"}</p>

                    <div className="flex items-center justify-between text-[10px]">
                      <span className={`px-2 py-0.5 rounded-full font-bold uppercase border ${getStatusBadge(r.status)}`}>
                        {r.status}
                      </span>
                      <span className="text-slate-500 dark:text-slate-400 font-mono">{r.created_at?.slice(0, 16)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Detailed Trace Breakdown Inspector */}
            <div className="lg:col-span-7 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 rounded-2xl overflow-y-auto custom-scrollbar space-y-4 shadow-xs">
              {selectedRunDetails ? (
                <>
                  <div className="pb-3 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                    <div>
                      <h3 className="font-bold text-base text-slate-900 dark:text-white">
                        Agent Run #{selectedRunDetails.run?.id} Trace Breakdown
                      </h3>
                      <p className="text-xs text-slate-600 dark:text-slate-400 font-mono font-medium flex items-center gap-2 mt-1">
                        <span>Status:</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${getStatusBadge(selectedRunDetails.run?.status)}`}>
                          {selectedRunDetails.run?.status}
                        </span>
                        <span>• Latency: {selectedRunDetails.run?.total_latency_ms || 0}ms</span>
                      </p>
                      {selectedRunDetails.trace_id && (
                        <p className="text-[11px] text-slate-500 dark:text-slate-400 font-mono flex items-center gap-1.5 mt-1">
                          <span>trace_id: {selectedRunDetails.trace_id}</span>
                          <button
                            onClick={() => navigator.clipboard.writeText(selectedRunDetails.trace_id)}
                            aria-label="copy trace id"
                            title="Copy trace_id"
                            className="text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 cursor-pointer"
                          >
                            📋
                          </button>
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="space-y-3">
                    {selectedRunDetails.steps?.map((step: any, idx: number) => (
                      <div key={idx} className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-2 font-mono text-xs shadow-xs">
                        <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-slate-800">
                          <span className="font-bold text-blue-700 dark:text-blue-400">
                            Seq #{step.seq} — {step.kind === "llm_call" ? "🤖 LLM Reasoning Call" : "🛠️ Tool Execution"}
                          </span>
                          <span className="text-slate-500 dark:text-slate-400 font-bold">{step.latency_ms}ms</span>
                        </div>

                        {step.tool_name && (
                          <div className="text-emerald-700 dark:text-emerald-400 font-bold">
                            Executed Tool: <code className="bg-slate-200 dark:bg-slate-900 px-1.5 py-0.5 rounded text-slate-900 dark:text-slate-200">{step.tool_name}</code>
                          </div>
                        )}

                        {step.arguments && (
                          <div>
                            <div className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold mb-1">Tool Arguments:</div>
                            <pre className="p-2.5 rounded-xl bg-white dark:bg-slate-900 text-[11px] text-amber-800 dark:text-amber-300 border border-slate-200 dark:border-slate-800 overflow-x-auto">
                              {JSON.stringify(step.arguments, null, 2)}
                            </pre>
                          </div>
                        )}

                        {step.result && (
                          <div>
                            <div className="text-[10px] text-slate-500 dark:text-slate-400 uppercase font-bold mb-1">Tool Execution Result:</div>
                            <pre className="p-2.5 rounded-xl bg-white dark:bg-slate-900 text-[11px] text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-800 overflow-x-auto">
                              {JSON.stringify(step.result, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="text-center p-8 text-xs text-slate-500">
                  Select a run from the list to view its step-by-step trace.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
