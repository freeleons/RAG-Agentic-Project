import BuildIcon from "@mui/icons-material/Build";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import PsychologyIcon from "@mui/icons-material/Psychology";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Stack,
  Typography,
} from "@mui/material";
import { TOOL_COLOR_KEY } from "../theme";
import type { TraceStep } from "../types";

function Section({ label, value }: { label: string; value: unknown }) {
  return (
    <Box sx={{ mb: 1 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ textTransform: "uppercase", fontWeight: 700, letterSpacing: "0.05em" }}
      >
        {label}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          fontSize: 11,
          fontFamily: "monospace",
          overflowX: "auto",
          bgcolor: "#0F172A",
          color: "#E2E8F0",
          borderRadius: 1.5,
        }}
      >
        {JSON.stringify(value, null, 2)}
      </Box>
    </Box>
  );
}

export default function StepItem({ step }: { step: TraceStep }) {
  const isLlm = step.kind === "llm_call";
  const toolKey = isLlm ? "model_call" : (step.tool_name ?? "default");
  const toolBadge = TOOL_COLOR_KEY[toolKey] ?? TOOL_COLOR_KEY.default;
  const title = isLlm ? "model call" : (step.tool_name ?? step.kind);

  return (
    <Accordion disableGutters sx={{ mb: 1, borderRadius: 1.5, overflow: "hidden" }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ width: "100%" }}>
          {isLlm ? (
            <PsychologyIcon fontSize="small" sx={{ color: toolBadge.color }} />
          ) : (
            <BuildIcon fontSize="small" sx={{ color: toolBadge.color }} />
          )}
          <Typography variant="body2" sx={{ fontWeight: 600, flexGrow: 1 }}>
            #{step.seq} · {title}
          </Typography>
          <Chip
            size="small"
            label={toolBadge.label}
            sx={{
              height: 20,
              fontSize: "0.65rem",
              bgcolor: toolBadge.bg,
              color: toolBadge.color,
              fontWeight: 700,
            }}
          />
          {step.latency_ms != null && (
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
              {step.latency_ms} ms
            </Typography>
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {step.arguments != null && <Section label="arguments" value={step.arguments} />}
        {step.result != null && <Section label="result" value={step.result} />}
        {step.llm_messages != null && (
          <Section label="model input" value={step.llm_messages} />
        )}
      </AccordionDetails>
    </Accordion>
  );
}
