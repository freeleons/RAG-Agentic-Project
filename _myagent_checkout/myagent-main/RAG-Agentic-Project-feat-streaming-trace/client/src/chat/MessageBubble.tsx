import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import PersonIcon from "@mui/icons-material/Person";
import SearchIcon from "@mui/icons-material/Search";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import { Avatar, Box, Chip, Paper, Typography } from "@mui/material";
import type { UiMessage } from "../types";

interface Props {
  message: UiMessage;
  onOpenRun: (runId: number) => void;
}

export default function MessageBubble({ message, onOpenRun }: Props) {
  const isUser = message.role === "user";
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: isUser ? "row-reverse" : "row",
        alignItems: "flex-start",
        gap: 1.25,
        mb: 0.5,
      }}
    >
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: isUser ? "#4F46E5" : "#0F172A",
          fontSize: 18,
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
        }}
      >
        {isUser ? <PersonIcon fontSize="small" /> : <SmartToyIcon fontSize="small" sx={{ color: "#06B6D4" }} />}
      </Avatar>
      <Box sx={{ maxWidth: "75%" }}>
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{
            display: "block",
            mb: 0.25,
            px: 0.5,
            textAlign: isUser ? "right" : "left",
            fontWeight: 600,
            fontSize: "0.7rem",
          }}
        >
          {isUser ? "You" : "Support Agent"}
        </Typography>
        <Paper
          elevation={isUser ? 0 : 1}
          sx={{
            p: 1.75,
            borderRadius: isUser ? "16px 4px 16px 16px" : "4px 16px 16px 16px",
            background: isUser
              ? "linear-gradient(135deg, #4F46E5 0%, #3730A3 100%)"
              : "#FFFFFF",
            color: isUser ? "#FFFFFF" : "#0F172A",
            border: isUser ? "none" : "1px solid #E2E8F0",
          }}
        >
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
            {message.content}
          </Typography>
          {!isUser && (
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mt: 1.25, flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(message.content)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "4px",
                  padding: "3px 8px",
                  borderRadius: "6px",
                  fontSize: "11px",
                  fontWeight: 600,
                  border: "1px solid #CBD5E1",
                  background: "#F8FAFC",
                  color: "#475569",
                  cursor: "pointer",
                }}
              >
                📋 Copy
              </button>
              {message.awaitingConfirmation && (
                <Chip
                  size="small"
                  icon={<HourglassTopIcon />}
                  label="waiting for your confirmation"
                  color="warning"
                  sx={{ fontWeight: 600 }}
                />
              )}
              {!message.awaitingConfirmation && message.runId !== undefined && (
                <Chip
                  size="small"
                  icon={<SearchIcon />}
                  data-testid={`trace-chip-${message.runId}`}
                  onClick={() => onOpenRun(message.runId!)}
                  label={`${message.stepCount ?? "?"} steps${
                    message.totalLatencyMs != null
                      ? ` · ${(message.totalLatencyMs / 1000).toFixed(1)}s`
                      : ""
                  }`}
                  sx={{
                    bgcolor: "#F1F5F9",
                    color: "#4F46E5",
                    fontWeight: 600,
                    border: "1px solid #CBD5E1",
                    "&:hover": { bgcolor: "#E2E8F0" },
                  }}
                />
              )}
            </Box>
          )}
        </Paper>
      </Box>
    </Box>
  );
}
