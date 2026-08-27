import { createTheme } from "@mui/material/styles";

/**
 * Design System Tokens & Brand Key
 * ----------------------------------------------------
 * Standardized color palette, typography, shape tokens, and tool status keys
 * for enterprise-grade UI consistency across all feature branches.
 */
export const BRAND_TOKENS = {
  primary: "#4F46E5", // Modern Indigo
  primaryHover: "#4338CA",
  secondary: "#06B6D4", // Electric Cyan
  darkSlate: "#0F172A", // Header Slate Navy
  drawerBg: "#1E293B", // Sidebar Slate
  canvasBg: "#F8FAFC", // Soft Gray Canvas
  surfaceBg: "#FFFFFF", // Paper / Card Surface
  borderLight: "#E2E8F0",
  textPrimary: "#0F172A",
  textSecondary: "#64748B",
};

/**
 * Tool Execution Visual Color Key (For Agent Trace Observability)
 */
export const TOOL_COLOR_KEY: Record<string, { bg: string; color: string; label: string }> = {
  search_knowledge: { bg: "#E0F2FE", color: "#0284C7", label: "Knowledge Search" },
  escalate_it_issue: { bg: "#FFE4E6", color: "#E11D48", label: "IT Escalation" },
  create_ticket: { bg: "#FEF3C7", color: "#D97706", label: "Ticket Creation" },
  model_call: { bg: "#F3E8FF", color: "#7C3AED", label: "LLM Reasoning" },
  default: { bg: "#F1F5F9", color: "#475569", label: "Tool Action" },
};

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: BRAND_TOKENS.primary,
      dark: BRAND_TOKENS.primaryHover,
      contrastText: "#FFFFFF",
    },
    secondary: {
      main: BRAND_TOKENS.secondary,
      contrastText: "#FFFFFF",
    },
    background: {
      default: BRAND_TOKENS.canvasBg,
      paper: BRAND_TOKENS.surfaceBg,
    },
    text: {
      primary: BRAND_TOKENS.textPrimary,
      secondary: BRAND_TOKENS.textSecondary,
    },
  },
  typography: {
    fontFamily: [
      "Inter",
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      "sans-serif",
    ].join(","),
    h6: {
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    subtitle1: {
      fontWeight: 600,
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 10,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          fontWeight: 600,
          boxShadow: "none",
          "&:hover": {
            boxShadow: "0 2px 4px rgba(0,0,0,0.08)",
          },
        },
        containedPrimary: {
          background: `linear-gradient(135deg, ${BRAND_TOKENS.primary} 0%, ${BRAND_TOKENS.primaryHover} 100%)`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
        elevation1: {
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)",
          border: `1px solid ${BRAND_TOKENS.borderLight}`,
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: BRAND_TOKENS.darkSlate,
          backgroundImage: "none",
          boxShadow: "0 1px 3px 0 rgba(0, 0, 0, 0.2)",
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 6,
        },
      },
    },
  },
});
