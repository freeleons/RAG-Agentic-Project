import { Card, CardContent, Stack, Typography } from "@mui/material";
import type { RunStats } from "../types";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card sx={{ minWidth: 130, flex: 1 }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase" }}>
          {label}
        </Typography>
        <Typography variant="h5">{value}</Typography>
      </CardContent>
    </Card>
  );
}

export default function StatsCards({ stats }: { stats: RunStats | null }) {
  const fmt = (v: number | null, f: (n: number) => string) => (v == null ? "—" : f(v));
  return (
    <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" sx={{ my: 2 }}>
      <StatCard label="Total runs" value={stats ? String(stats.total_runs) : "—"} />
      <StatCard
        label="Success rate"
        value={stats ? fmt(stats.success_rate, (n) => `${Math.round(n * 100)}%`) : "—"}
      />
      <StatCard
        label="Avg steps"
        value={stats ? fmt(stats.avg_steps, (n) => n.toFixed(1)) : "—"}
      />
      <StatCard
        label="Avg latency"
        value={stats ? fmt(stats.avg_latency_ms, (n) => `${(n / 1000).toFixed(1)}s`) : "—"}
      />
      <StatCard
        label="Tokens (prompt / completion)"
        value={
          stats
            ? `${stats.total_prompt_tokens.toLocaleString()} / ${stats.total_completion_tokens.toLocaleString()}`
            : "—"
        }
      />
      <StatCard
        label="Failed + declined"
        value={
          stats
            ? String((stats.by_status["failed"] ?? 0) + (stats.by_status["declined"] ?? 0))
            : "—"
        }
      />
    </Stack>
  );
}
