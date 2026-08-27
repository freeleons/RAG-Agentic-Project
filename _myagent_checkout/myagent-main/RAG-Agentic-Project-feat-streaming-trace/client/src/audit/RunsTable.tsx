import {
  Box,
  Chip,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import type { Conversation, RunFilters, RunsPage } from "../types";

const STATUS_CHIP: Record<string, "success" | "warning" | "error" | "default"> = {
  completed: "success",
  needs_confirmation: "warning",
  failed: "error",
  declined: "default",
};

const STATUSES = ["completed", "failed", "declined", "needs_confirmation", "running"];

interface RunsTableProps {
  page: RunsPage | null;
  filters: RunFilters;
  onFiltersChange: (f: RunFilters) => void;
  conversations: Conversation[];
  isAdmin: boolean;
  onOpenRun: (runId: number) => void;
}

export default function RunsTable({
  page,
  filters,
  onFiltersChange,
  conversations,
  isAdmin,
  onOpenRun,
}: RunsTableProps) {
  const patch = (p: Partial<RunFilters>) =>
    onFiltersChange({ ...filters, ...p, page: 1 });

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Status"
          value={filters.status ?? ""}
          onChange={(e) => patch({ status: e.target.value || undefined })}
          sx={{ minWidth: 180 }}
          slotProps={{ htmlInput: { "aria-label": "status filter" } }}
        >
          <MenuItem value="">All statuses</MenuItem>
          {STATUSES.map((s) => (
            <MenuItem key={s} value={s}>
              {s}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Conversation"
          value={filters.conversationId ?? ""}
          onChange={(e) =>
            patch({ conversationId: e.target.value ? Number(e.target.value) : undefined })
          }
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">All conversations</MenuItem>
          {conversations.map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.title}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="From"
          type="date"
          value={filters.dateFrom ?? ""}
          onChange={(e) => patch({ dateFrom: e.target.value || undefined })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          label="To"
          type="date"
          value={filters.dateTo ?? ""}
          onChange={(e) => patch({ dateTo: e.target.value || undefined })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        {isAdmin && (
          <TextField
            size="small"
            label="User email"
            defaultValue={filters.userEmail ?? ""}
            onBlur={(e) => patch({ userEmail: e.target.value || undefined })}
            onKeyDown={(e) => {
              if (e.key === "Enter")
                patch({ userEmail: (e.target as HTMLInputElement).value || undefined });
            }}
          />
        )}
      </Stack>
      {page && page.runs.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
          No runs match these filters.
        </Typography>
      ) : (
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                {isAdmin && <TableCell>User</TableCell>}
                <TableCell>Goal</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Steps</TableCell>
                <TableCell align="right">Latency</TableCell>
                <TableCell align="right">Tokens</TableCell>
                <TableCell>Conversation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(page?.runs ?? []).map((run) => (
                <TableRow
                  key={run.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => onOpenRun(run.id)}
                >
                  <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
                  {isAdmin && <TableCell>{run.user_email}</TableCell>}
                  <TableCell sx={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {run.goal}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={run.status} color={STATUS_CHIP[run.status] ?? "default"} />
                  </TableCell>
                  <TableCell align="right">{run.step_count}</TableCell>
                  <TableCell align="right">
                    {run.total_latency_ms != null ? `${(run.total_latency_ms / 1000).toFixed(1)}s` : "—"}
                  </TableCell>
                  <TableCell align="right">
                    {run.prompt_tokens + run.completion_tokens}
                  </TableCell>
                  <TableCell>{run.conversation_title}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
      <TablePagination
        component="div"
        count={page?.total ?? 0}
        page={(page?.page ?? 1) - 1}
        onPageChange={(_, newPage) => onFiltersChange({ ...filters, page: newPage + 1 })}
        rowsPerPage={page?.per_page ?? 20}
        rowsPerPageOptions={[20]}
      />
    </Paper>
  );
}
