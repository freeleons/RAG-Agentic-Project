import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import {
  Alert,
  Box,
  Button,
  Chip,
  IconButton,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import type { PanelState } from "../types";
import StepItem from "./StepItem";

const STATUS_COLOR: Record<
  string,
  "success" | "warning" | "error" | "default"
> = {
  completed: "success",
  needs_confirmation: "warning",
  failed: "error",
  declined: "default",
};

interface Props {
  panel: PanelState | null;
  busy: boolean;
  onConfirm: (approved: boolean) => void;
}

export default function TracePanel({ panel, busy, onConfirm }: Props) {
  if (!panel) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Send a goal or click a trace chip to inspect a run.
        </Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ p: 2, overflowY: "auto", height: "100%" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h6">Run #{panel.runId}</Typography>
        <Chip
          size="small"
          label={panel.status}
          color={STATUS_COLOR[panel.status] ?? "default"}
        />
        {panel.totalLatencyMs != null && (
          <Typography variant="caption" color="text.secondary">
            {(panel.totalLatencyMs / 1000).toFixed(1)}s total
          </Typography>
        )}
      </Stack>
      {panel.traceId && (
        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mb: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace" }}>
            trace_id: {panel.traceId}
          </Typography>
          <Tooltip title="Copy trace_id">
            <IconButton
              size="small"
              onClick={() => navigator.clipboard.writeText(panel.traceId as string)}
              aria-label="copy trace id"
            >
              <ContentCopyIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      )}
      {panel.steps.map((s) => (
        <StepItem key={s.seq} step={s} />
      ))}
      {panel.status === "needs_confirmation" && panel.pendingAction && (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
          <Alert severity="warning" sx={{ mb: 1 }}>
            The agent wants to run <b>{panel.pendingAction.tool}</b>
          </Alert>
          <Box
            component="pre"
            sx={{ fontSize: 12, overflowX: "auto", mb: 1 }}
          >
            {JSON.stringify(panel.pendingAction.arguments, null, 2)}
          </Box>
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              color="success"
              disabled={busy}
              onClick={() => onConfirm(true)}
            >
              Approve
            </Button>
            <Button
              variant="outlined"
              color="error"
              disabled={busy}
              onClick={() => onConfirm(false)}
            >
              Reject
            </Button>
          </Stack>
        </Paper>
      )}
    </Box>
  );
}
