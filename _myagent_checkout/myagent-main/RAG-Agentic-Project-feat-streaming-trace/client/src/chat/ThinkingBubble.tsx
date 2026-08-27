import SmartToyIcon from "@mui/icons-material/SmartToy";
import { Avatar, Box, Paper, Skeleton, Stack, Typography } from "@mui/material";

export default function ThinkingBubble() {
  return (
    <Box sx={{ display: "flex", gap: 1.5, my: 0.5, alignItems: "flex-start" }}>
      <Avatar
        sx={{
          width: 28,
          height: 28,
          bgcolor: "primary.main",
          boxShadow: "0 2px 6px rgba(79, 70, 229, 0.3)",
        }}
      >
        <SmartToyIcon sx={{ fontSize: 16, color: "#FFFFFF" }} />
      </Avatar>
      <Paper
        elevation={0}
        sx={{
          p: 1.5,
          borderRadius: "16px 16px 16px 4px",
          bgcolor: "#FFFFFF",
          border: "1px solid #E2E8F0",
          width: 240,
        }}
      >
        <Stack spacing={1}>
          <Typography
            variant="caption"
            sx={{
              fontWeight: 700,
              color: "primary.main",
              fontSize: "0.75rem",
              letterSpacing: "0.02em",
            }}
          >
            Thinking…
          </Typography>
          <Skeleton variant="rounded" width="100%" height={12} animation="wave" />
          <Skeleton variant="rounded" width="65%" height={12} animation="wave" />
        </Stack>
      </Paper>
    </Box>
  );
}


