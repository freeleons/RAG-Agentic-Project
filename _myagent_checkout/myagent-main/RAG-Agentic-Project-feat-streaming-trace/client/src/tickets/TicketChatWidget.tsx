import { useEffect, useRef, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import CloseIcon from "@mui/icons-material/Close";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import SendIcon from "@mui/icons-material/Send";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import StopCircleIcon from "@mui/icons-material/StopCircle";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";

import {
  Box,
  Button,
  Fab,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";

import { api } from "../api";
import MessageBubble from "../chat/MessageBubble";
import ThinkingBubble from "../chat/ThinkingBubble";
import { pairHistory } from "../chat/history";
import type { Conversation, UiMessage } from "../types";


interface Props {
  initialPrompt?: string;
  onClearInitialPrompt?: () => void;
  onTicketUpdated?: () => void;
  selectedConversationId?: number | null;
  onSelectConversation?: (id: number) => void;
  onOpenFullChat?: (id: number) => void;
  conversations?: Conversation[];
  onNewConversation?: () => void;
  onRefreshConversations?: () => void;
  globalBusy?: boolean;
  globalMessages?: UiMessage[];
  globalPendingAction?: { runId: number; tool: string; arguments: any } | null;
  onGlobalSend?: (goal: string) => void;
  onGlobalStop?: () => void;
  onGlobalConfirm?: (approved: boolean) => void;
}

export default function TicketChatWidget({
  initialPrompt,
  onClearInitialPrompt,
  onTicketUpdated,
  selectedConversationId,
  onSelectConversation,
  onOpenFullChat,
  conversations = [],
  onNewConversation,
  onRefreshConversations,
  globalBusy,
  globalMessages,
  globalPendingAction,
  onGlobalSend,
  onGlobalStop,
  onGlobalConfirm,
}: Props) {
  const [open, setOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState<number | null>(selectedConversationId ?? null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingAction, setPendingAction] = useState<{
    runId: number;
    tool: string;
    arguments: any;
  } | null>(null);

  const isBusy = globalBusy !== undefined ? globalBusy : busy;
  const activeMessages = globalMessages !== undefined ? globalMessages : messages;
  const activeAction =
    globalPendingAction !== undefined ? globalPendingAction : pendingAction;



  // Sync active conversation when selectedConversationId changes
  useEffect(() => {
    if (selectedConversationId != null) {
      setActiveConvId(selectedConversationId);
    }
  }, [selectedConversationId]);

  // Load history when activeConvId changes
  useEffect(() => {
    if (activeConvId != null) {
      api
        .getHistory(activeConvId)
        .then((h) => setMessages(pairHistory(h)))
        .catch(() => {});
    } else {
      api
        .listConversations()
        .then(async (convs) => {
          if (convs.length > 0) {
            setActiveConvId(convs[0].id);
            if (onSelectConversation) onSelectConversation(convs[0].id);
            const history = await api.getHistory(convs[0].id);
            setMessages(pairHistory(history));
          }
        })
        .catch(() => {});
    }
  }, [activeConvId]);

  // Handle pre-filled prompt when user clicks "Ask AI" on a ticket card
  useEffect(() => {
    if (initialPrompt) {
      setDraft(initialPrompt);
      setOpen(true);
      if (onClearInitialPrompt) onClearInitialPrompt();
    }
  }, [initialPrompt]);

  const handleStartNewConversation = async () => {
    try {
      const newConv = await api.createConversation("New conversation");
      setActiveConvId(newConv.id);
      setMessages([]);
      setPendingAction(null);
      if (onSelectConversation) onSelectConversation(newConv.id);
      if (onRefreshConversations) onRefreshConversations();
    } catch (err) {
      // ignore
    }
  };

  const abortRef = useRef<AbortController | null>(null);

  const handleStop = () => {
    if (onGlobalStop) {
      onGlobalStop();
      return;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setBusy(false);
  };

  const handleSend = async () => {
    const goal = draft.trim();
    if (!goal || isBusy) return;

    if (onGlobalSend) {
      setDraft("");
      onGlobalSend(goal);
      return;
    }

    let targetId = activeConvId;
    if (!targetId) {
      try {
        const newConv = await api.createConversation("New conversation");
        targetId = newConv.id;
        setActiveConvId(newConv.id);
        if (onSelectConversation) onSelectConversation(newConv.id);
        if (onRefreshConversations) onRefreshConversations();
      } catch (err) {
        return;
      }
    }

    setMessages((ms) => [...ms, { role: "user", content: goal }]);
    setDraft("");
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const outcome = await api.sendMessage(targetId, goal, controller.signal);
      const history = await api.getHistory(targetId);
      setMessages(pairHistory(history));

      if (outcome.status === "needs_confirmation" && outcome.pending_action) {
        setPendingAction({
          runId: outcome.run_id,
          tool: outcome.pending_action.tool,
          arguments: outcome.pending_action.arguments,
        });
      } else {
        setPendingAction(null);
      }

      if (onRefreshConversations) onRefreshConversations();

      // Trigger ticket refresh in parent UI if ticket tools ran
      if (
        outcome.trace.some((s: any) =>
          ["create_ticket", "update_ticket", "delete_ticket"].includes(s.tool_name || "")
        ) &&
        onTicketUpdated
      ) {
        onTicketUpdated();
      }
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setMessages((ms) => [
          ...ms,
          { role: "assistant", content: "Generation stopped by user." },
        ]);
      } else {
        setMessages((ms) => ms.slice(0, -1));
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };


  const handleConfirmAction = async (approved: boolean) => {
    if (onGlobalConfirm) {
      onGlobalConfirm(approved);
      return;
    }
    if (!pendingAction) return;
    const runId = pendingAction.runId;
    setPendingAction(null);
    setBusy(true);

    try {
      const outcome = await api.confirmRun(runId, approved);
      if (activeConvId) {
        const history = await api.getHistory(activeConvId);
        setMessages(pairHistory(history));
      }
      if (onRefreshConversations) onRefreshConversations();
      if (
        outcome.trace.some((s: any) =>
          ["create_ticket", "update_ticket", "delete_ticket"].includes(s.tool_name || "")
        ) &&
        onTicketUpdated
      ) {
        onTicketUpdated();
      }
    } catch (err) {
      // ignore
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      {!open && (
        <Tooltip title="AI Triage Assistant" placement="left">
          <Fab
            color="primary"
            onClick={() => setOpen(true)}
            sx={{
              position: "fixed",
              bottom: 24,
              right: 24,
              boxShadow: "0 6px 20px rgba(79, 70, 229, 0.4)",
              zIndex: 1200,
            }}
          >
            <SmartToyIcon />
          </Fab>
        </Tooltip>
      )}

      {/* Floating Widget Modal */}
      {open && (
        <Paper
          elevation={8}
          sx={{
            position: "fixed",
            bottom: 24,
            right: 24,
            width: 380,
            height: 520,
            borderRadius: 3,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            zIndex: 1300,
            boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
            border: "1px solid #E2E8F0",
          }}
        >
          {/* Header */}
          <Box
            sx={{
              p: 1.5,
              bgcolor: "primary.main",
              color: "primary.contrastText",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Stack direction="row" spacing={1} alignItems="center">
              <SmartToyIcon fontSize="small" />
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                AI Triage Assistant
              </Typography>
            </Stack>
            <Stack direction="row" spacing={0.5}>
              <Tooltip title="Start New Conversation">
                <IconButton
                  size="small"
                  sx={{ color: "rgba(255,255,255,0.7)", "&:hover": { color: "#FFFFFF" } }}
                  onClick={handleStartNewConversation}
                >
                  <AddIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              {activeConvId && onOpenFullChat && (
                <Tooltip title="Open in Full Chat Page">
                  <IconButton
                    size="small"
                    sx={{ color: "rgba(255,255,255,0.7)", "&:hover": { color: "#FFFFFF" } }}
                    onClick={() => onOpenFullChat(activeConvId)}
                  >
                    <OpenInNewIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              )}
              <IconButton size="small" sx={{ color: "rgba(255,255,255,0.7)" }} onClick={() => setOpen(false)}>
                <CloseIcon fontSize="small" />
              </IconButton>
            </Stack>
          </Box>

          {/* Messages Container */}
          <Stack spacing={1.5} sx={{ flex: 1, overflowY: "auto", p: 2, bgcolor: "#F8FAFC" }}>
            {activeMessages.length === 0 && (
              <Box sx={{ textAlign: "center", py: 4, px: 2 }}>
                <SmartToyIcon sx={{ fontSize: 40, color: "#94A3B8", mb: 1 }} />
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  How can I help with your tickets?
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                  Ask me to list, update, or resolve any ticket for you.
                </Typography>
              </Box>
            )}

            {activeMessages.map((m, i) => (
              <MessageBubble key={i} message={m} onOpenRun={() => {}} />
            ))}

            {/* Human-in-the-Loop Confirmation Banner */}
            {activeAction && (
              <Paper
                elevation={0}
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  bgcolor: "#FEF3C7",
                  border: "1px solid #F59E0B",
                }}
              >
                <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                  <WarningAmberIcon fontSize="small" sx={{ color: "#D97706" }} />
                  <Typography variant="caption" sx={{ fontWeight: 700, color: "#92400E" }}>
                    Action Requires Approval: {activeAction.tool}
                  </Typography>
                </Stack>
                <Box
                  sx={{
                    bgcolor: "#FFFFFF",
                    p: 1,
                    borderRadius: 1,
                    fontFamily: "monospace",
                    fontSize: "0.7rem",
                    mb: 1.5,
                    overflowX: "auto",
                  }}
                >
                  {JSON.stringify(activeAction.arguments, null, 2)}
                </Box>
                <Stack direction="row" spacing={1} justifyContent="flex-end">
                  <Button
                    size="small"
                    color="error"
                    variant="outlined"
                    onClick={() => handleConfirmAction(false)}
                    sx={{ fontSize: "0.7rem", py: 0.2 }}
                  >
                    Decline
                  </Button>
                  <Button
                    size="small"
                    color="primary"
                    variant="contained"
                    onClick={() => handleConfirmAction(true)}
                    sx={{ fontSize: "0.7rem", py: 0.2 }}
                  >
                    Approve Action
                  </Button>
                </Stack>
              </Paper>
            )}

            {/* Thinking Skeleton UI */}
            {isBusy && <ThinkingBubble />}
          </Stack>

          {isBusy && <LinearProgress color="primary" />}

          {/* Input Footer */}
          <Box
            component="form"
            onSubmit={(e) => {
              e.preventDefault();
              if (!isBusy) handleSend();
            }}
            sx={{ p: 1.5, bgcolor: "#FFFFFF", borderTop: "1px solid #E2E8F0", display: "flex", gap: 1 }}
          >
            <TextField
              fullWidth
              size="small"
              placeholder={isBusy ? "Agent is thinking…" : "Ask AI to manage tickets…"}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={isBusy || !!activeAction}
            />
            {isBusy ? (
              <Button
                size="small"
                variant="contained"
                color="error"
                startIcon={<StopCircleIcon />}
                onClick={handleStop}
                sx={{ fontWeight: 600, px: 1.5, whiteSpace: "nowrap", fontSize: "0.75rem" }}
              >
                Stop
              </Button>
            ) : (
              <IconButton
                type="submit"
                color="primary"
                disabled={isBusy || !!activeAction || !draft.trim()}
                size="small"
              >
                <SendIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        </Paper>
      )}
    </>
  );
}
