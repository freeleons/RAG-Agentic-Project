import React from "react";
import { TraceStep } from "../types";

/**
 * Progress model for the Pip answer area.
 *
 * Run steps are only persisted once they finish, so the live events below are
 * derived from the polled step list: an `llm_call` that picked a tool means
 * that tool is now running, and the matching `tool_call` step closes it out.
 */

export type AgentStage = "ANALYZING" | "TOOL_CALLING" | "GENERATING" | "COMPLETED";

export type AgentEvent =
  | { type: "stage_change"; stage: AgentStage; message: string }
  | { type: "thinking"; message: string }
  | { type: "tool_start"; tool: string; args: Record<string, unknown> }
  | { type: "tool_result"; tool: string; success: boolean; latencyMs: number; summary: string };

export interface ToolActivity {
  tool: string;
  args: Record<string, unknown>;
  status: "running" | "success" | "error";
  latencyMs: number | null;
  summary: string;
}

export interface AgentProgress {
  percent: number;
  stage: AgentStage;
  label: string;
  events: AgentEvent[];
  tools: ToolActivity[];
}

const START_PERCENT = 20;
// Leave headroom so the bar only reaches 100% once the answer is in hand
const MAX_LIVE_PERCENT = 85;

const PERCENT_BUMP: Record<AgentEvent["type"], number> = {
  stage_change: 5,
  thinking: 3,
  tool_start: 2,
  tool_result: 4,
};

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: "🔍 Searching audited policy knowledge base...",
  list_tickets: "📋 Retrieving active support tickets...",
  escalate: "⚠️ Processing ticket escalation...",
};

const ANALYZING_LABEL = "🧠 Analyzing request...";
const GENERATING_LABEL = "✍️ Formulating policy-grounded response...";

const toolLabel = (tool: string): string => TOOL_LABELS[tool] ?? `🛠️ Executing tool: ${tool}...`;

const summarize = (value: unknown, limit = 120): string => {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (!text) return "";
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
};

const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};

export const deriveAgentProgress = (
  steps: TraceStep[],
  runStatus?: string,
): AgentProgress => {
  const events: AgentEvent[] = [
    { type: "stage_change", stage: "ANALYZING", message: ANALYZING_LABEL },
  ];
  const tools: ToolActivity[] = [];
  let stage: AgentStage = "ANALYZING";
  let label = ANALYZING_LABEL;

  const enterStage = (next: AgentStage, message: string) => {
    if (stage !== next) {
      stage = next;
      events.push({ type: "stage_change", stage: next, message });
    }
  };

  for (const step of steps) {
    if (step.kind === "llm_call") {
      const result = asRecord(step.result);
      if (result.type === "tool_call" && typeof result.name === "string") {
        const args = asRecord(result.arguments);
        enterStage("TOOL_CALLING", `Calling ${result.name}...`);
        events.push({ type: "tool_start", tool: result.name, args });
        tools.push({
          tool: result.name,
          args,
          status: "running",
          latencyMs: null,
          summary: summarize(args, 80),
        });
        label = toolLabel(result.name);
      } else if (result.type === "final") {
        enterStage("GENERATING", GENERATING_LABEL);
        events.push({ type: "thinking", message: GENERATING_LABEL });
        label = GENERATING_LABEL;
      } else if (result.error) {
        events.push({ type: "thinking", message: summarize(result.error, 80) });
      }
      continue;
    }

    if (step.kind === "tool_call" && step.tool_name) {
      const result = asRecord(step.result);
      const success = !result.error;
      const latencyMs = step.latency_ms ?? 0;
      const summary = summarize(success ? result : result.error);
      events.push({ type: "tool_result", tool: step.tool_name, success, latencyMs, summary });

      const pending = [...tools].reverse().find((t) => t.tool === step.tool_name && t.status === "running");
      if (pending) {
        pending.status = success ? "success" : "error";
        pending.latencyMs = latencyMs;
        pending.summary = summary;
      } else {
        tools.push({
          tool: step.tool_name,
          args: asRecord(step.arguments),
          status: success ? "success" : "error",
          latencyMs,
          summary,
        });
      }
      label = GENERATING_LABEL;
    }
  }

  const bumped = events.reduce((total, event) => total + PERCENT_BUMP[event.type], START_PERCENT);
  let percent = Math.min(MAX_LIVE_PERCENT, bumped);

  if (runStatus === "completed" || runStatus === "declined") {
    stage = "COMPLETED";
    percent = 100;
  }

  return { percent, stage, label, events, tools };
};

const STATUS_ICON: Record<ToolActivity["status"], string> = {
  running: "⟳",
  success: "✓",
  error: "✕",
};

const STATUS_CLASS: Record<ToolActivity["status"], string> = {
  running: "text-blue-600 dark:text-blue-300",
  success: "text-emerald-600 dark:text-emerald-400",
  error: "text-rose-600 dark:text-rose-400",
};

interface AgentProgressPanelProps {
  progress: AgentProgress;
  elapsedSeconds: number;
}

/** Live progress bar + tool activity shown while Pip is working. */
export const AgentProgressPanel: React.FC<AgentProgressPanelProps> = ({
  progress,
  elapsedSeconds,
}) => (
  <div className="p-2.5 rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 space-y-2">
    <div className="flex items-center justify-between text-[9px] font-mono font-bold uppercase tracking-wider text-blue-700 dark:text-blue-300">
      <span>{progress.stage.replace("_", " ")}</span>
      <span>
        {elapsedSeconds}s · {progress.percent}%
      </span>
    </div>

    <div className="h-1.5 w-full rounded-full bg-blue-100 dark:bg-blue-900/70 overflow-hidden">
      <div
        role="progressbar"
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-full rounded-full bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 transition-all duration-500 ease-out"
        style={{ width: `${progress.percent}%` }}
      />
    </div>

    <div className="text-xs font-mono font-semibold text-blue-700 dark:text-blue-300 animate-pulse">
      {progress.label}
    </div>

    {progress.tools.length > 0 && (
      <div className="space-y-1 max-h-24 overflow-y-auto custom-scrollbar pt-1 border-t border-blue-200/70 dark:border-blue-800/70">
        {progress.tools.map((tool, index) => (
          <div
            key={`${tool.tool}-${index}`}
            className="flex items-start gap-1.5 text-[10px] font-mono leading-tight"
          >
            <span className={`${STATUS_CLASS[tool.status]} shrink-0`}>{STATUS_ICON[tool.status]}</span>
            <span className="font-bold text-slate-700 dark:text-slate-200 shrink-0">{tool.tool}</span>
            <span className="text-slate-500 dark:text-slate-400 truncate">{tool.summary}</span>
            {tool.latencyMs !== null && (
              <span className="ml-auto text-slate-400 dark:text-slate-500 shrink-0">{tool.latencyMs}ms</span>
            )}
          </div>
        ))}
      </div>
    )}
  </div>
);

interface AgentToolTraceProps {
  tools: ToolActivity[];
}

/** Compact record of the tools a finished answer used. */
export const AgentToolTrace: React.FC<AgentToolTraceProps> = ({ tools }) => {
  if (tools.length === 0) return null;

  return (
    <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-700 flex flex-wrap gap-1">
      {tools.map((tool, index) => (
        <span
          key={`${tool.tool}-${index}`}
          title={tool.summary}
          className="px-1.5 py-0.5 rounded-md bg-white/70 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-700 text-[9px] font-mono text-slate-600 dark:text-slate-300"
        >
          <span className={STATUS_CLASS[tool.status]}>{STATUS_ICON[tool.status]}</span> {tool.tool}
          {tool.latencyMs !== null && ` · ${tool.latencyMs}ms`}
        </span>
      ))}
    </div>
  );
};
