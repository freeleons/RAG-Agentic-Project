import { Paper, Stack, Typography } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RunStats } from "../types";

const STATUS_COLORS = {
  completed: "#2e7d32",
  failed: "#d32f2f",
  declined: "#9e9e9e",
  needs_confirmation: "#ed6c02",
} as const;

export default function ChartsRow({ stats }: { stats: RunStats | null }) {
  if (!stats || stats.total_runs === 0) {
    return (
      <Typography color="text.secondary" sx={{ my: 2 }}>
        No run data yet — charts appear once the agent has handled a few goals.
      </Typography>
    );
  }
  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ my: 2 }}>
      <Paper sx={{ flex: 1, p: 2, height: 300 }} data-testid="runs-per-day-chart">
        <Typography variant="subtitle2" gutterBottom>
          Runs per day
        </Typography>
        <ResponsiveContainer width="100%" height="88%">
          <BarChart data={stats.runs_per_day}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Legend />
            {(Object.keys(STATUS_COLORS) as Array<keyof typeof STATUS_COLORS>).map(
              (status) => (
                <Bar key={status} dataKey={status} stackId="day" fill={STATUS_COLORS[status]} />
              )
            )}
          </BarChart>
        </ResponsiveContainer>
      </Paper>
      <Paper sx={{ flex: 1, p: 2, height: 300 }} data-testid="latency-chart">
        <Typography variant="subtitle2" gutterBottom>
          Run latency distribution
        </Typography>
        <ResponsiveContainer width="100%" height="88%">
          <BarChart data={stats.latency_buckets}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Bar dataKey="count" fill="#1976d2" />
          </BarChart>
        </ResponsiveContainer>
      </Paper>
    </Stack>
  );
}
