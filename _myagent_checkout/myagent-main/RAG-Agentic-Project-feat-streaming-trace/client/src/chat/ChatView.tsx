import SendIcon from "@mui/icons-material/Send";
import StopCircleIcon from "@mui/icons-material/StopCircle";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import {
  Box,
  Button,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import type { PendingAction, UiMessage } from "../types";
import MessageBubble from "./MessageBubble";
import PromptStarters from "./PromptStarters";
import ThinkingBubble from "./ThinkingBubble";

interface Props {
  messages: UiMessage[];
  busy: boolean;
  disabled: boolean;
  draft: string;
  onDraftChange: (v: string) => void;
  onSend: () => void;
  onSelectPrompt?: (prompt: string) => void;
  onOpenRun: (runId: number) => void;
  pendingAction?: PendingAction | null;
  onConfirm?: (approved: boolean) => void;
  onStop?: () => void;
}

export default function ChatView({
  messages,
  busy,
  disabled,
  draft,
  onDraftChange,
  onSend,
  onSelectPrompt,
  onOpenRun,
  pendingAction,
  onConfirm,
  onStop,
}: Props) {
  const handleStarterSelect = (prompt: string) => {
    if (onSelectPrompt) {
      onSelectPrompt(prompt);
    } else {
      onDraftChange(prompt);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      {messages.length === 0 ? (
        <Box sx={{ flex: 1, overflowY: "auto" }}>
          <PromptStarters onSelectPrompt={handleStarterSelect} />
        </Box>
      ) : (
        <Stack spacing={1.5} sx={{ flex: 1, overflowY: "auto", p: 2 }}>
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} onOpenRun={onOpenRun} />
          ))}
          {pendingAction && (
            <Paper
              elevation={0}
              sx={{
                p: 2,
                borderRadius: 2,
                bgcolor: "#FEF3C7",
                border: "1px solid #FCD34D",
                maxWidth: "80%",
              }}
            >
              <Stack spacing={1}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <WarningAmberIcon sx={{ color: "#D97706", fontSize: 20 }} />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: "#92400E" }}>
                    Action Required: {pendingAction.tool}
                  </Typography>
                </Stack>
                <Typography variant="body2" sx={{ color: "#78350F", fontSize: "0.85rem" }}>
                  The agent wants to execute <strong>{pendingAction.tool}</strong> with parameters:
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1,
                    bgcolor: "#FFFBEB",
                    borderRadius: 1,
                    fontSize: "0.75rem",
                    fontFamily: "monospace",
                    whiteSpace: "pre-wrap",
                    overflowX: "auto",
                  }}
                >
                  {JSON.stringify(pendingAction.arguments, null, 2)}
                </Box>
                <Stack direction="row" spacing={1} sx={{ pt: 0.5 }}>
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    onClick={() => onConfirm?.(true)}
                    disabled={busy}
                    sx={{ fontWeight: 600 }}
                  >
                    Approve Action
                  </Button>
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    onClick={() => onConfirm?.(false)}
                    disabled={busy}
                  >
                    Decline
                  </Button>
                </Stack>
              </Stack>
            </Paper>
          )}
          {busy && <ThinkingBubble />}
        </Stack>
      )}
      {busy && <LinearProgress color="primary" />}

      <Box
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy) onSend();
        }}
        sx={{ display: "flex", gap: 1, p: 1.5, borderTop: 1, borderColor: "divider" }}
      >
        <TextField
          fullWidth
          size="small"
          placeholder={busy ? "Agent is thinking…" : "Give the agent a goal…"}
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          disabled={disabled}
        />
        {busy ? (
          <Button
            size="small"
            variant="contained"
            color="error"
            startIcon={<StopCircleIcon />}
            onClick={onStop}
            sx={{ fontWeight: 600, px: 2, whiteSpace: "nowrap" }}
          >
            Stop
          </Button>
        ) : (
          <IconButton
            type="submit"
            color="primary"
            disabled={disabled || !draft.trim()}
            aria-label="send"
          >
            <SendIcon />
          </IconButton>
        )}
      </Box>
    </Box>
  );
}
