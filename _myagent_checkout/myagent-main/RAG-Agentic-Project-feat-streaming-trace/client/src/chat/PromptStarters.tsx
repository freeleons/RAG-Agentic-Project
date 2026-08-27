import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DescriptionIcon from "@mui/icons-material/Description";
import CreditCardIcon from "@mui/icons-material/CreditCard";
import SearchIcon from "@mui/icons-material/Search";
import SupportAgentIcon from "@mui/icons-material/SupportAgent";
import { Box, Paper, Typography, Grid } from "@mui/material";

interface Props {
  onSelectPrompt: (prompt: string) => void;
}

const STARTERS = [
  {
    icon: <DescriptionIcon color="primary" />,
    title: "Remote Work Policy",
    description: "Ask about guidelines, requirements, and reimbursement rules.",
    prompt: "What is our company remote work policy?",
  },
  {
    icon: <CreditCardIcon color="secondary" />,
    title: "Nimbus Subscription",
    description: "Inquire about billing, refunds, or cancellation steps.",
    prompt: "How do I cancel my Nimbus subscription?",
  },
  {
    icon: <SearchIcon color="info" />,
    title: "Vector Search Overview",
    description: "Learn how AnythingLLM embeds and retrieves documents.",
    prompt: "Can you explain how vector search works?",
  },
  {
    icon: <SupportAgentIcon color="warning" />,
    title: "Escalate IT Issue",
    description: "Route an urgent technical ticket to human support.",
    prompt: "I need to escalate an urgent IT network issue to support.",
  },
];

export default function PromptStarters({ onSelectPrompt }: Props) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        p: 3,
        textAlign: "center",
      }}
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1,
          mb: 1,
          color: "primary.main",
        }}
      >
        <AutoAwesomeIcon fontSize="large" />
        <Typography variant="h5" fontWeight={600}>
          How can I assist you today?
        </Typography>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 4, maxWidth: 500 }}>
        Select a prompt starter below or type a custom goal into the input box to start the AI agent loop.
      </Typography>

      <Grid container spacing={2} sx={{ maxWidth: 700 }}>
        {STARTERS.map((s, idx) => (
          <Grid item xs={12} sm={6} key={idx}>
            <Paper
              variant="outlined"
              onClick={() => onSelectPrompt(s.prompt)}
              sx={{
                p: 2,
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                textAlign: "left",
                cursor: "pointer",
                borderRadius: 2,
                transition: "all 0.2s ease-in-out",
                "&:hover": {
                  borderColor: "primary.main",
                  bgcolor: "action.hover",
                  transform: "translateY(-2px)",
                  boxShadow: 2,
                },
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                {s.icon}
                <Typography variant="subtitle2" fontWeight={600}>
                  {s.title}
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary">
                {s.description}
              </Typography>
            </Paper>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
