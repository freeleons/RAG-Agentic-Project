import {
  AppBar,
  Box,
  Button,
  Chip,
  Drawer,
  Snackbar,
  Tab,
  Tabs,
  Toolbar,
  Typography,
} from "@mui/material";
import { useEffect, useRef, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth/AuthContext";
import TicketsPage from "../tickets/TicketsPage";
import type { Conversation, PanelState, RunOutcome, UiMessage } from "../types";
import ChatView from "./ChatView";
import ConversationList from "./ConversationList";
import PromptStarters from "./PromptStarters";
import { pairHistory } from "./history";

const DRAWER_WIDTH = 260;

export function errMsg(err: unknown): string {
  return err instanceof ApiError ? err.message : "Network error — is the backend running?";
}

export default function AppPage() {
  const { email, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<PanelState | null>(null);
  const [snack, setSnack] = useState<string | null>(null);
  const [view, setView] = useState<"tickets" | "chat">("chat");
  const [searchQuery, setSearchQuery] = useState("");
  const [ticketRefreshVersion, setTicketRefreshVersion] = useState(0);

  const checkTicketMutation = (outcome: RunOutcome) => {
    if (
      outcome.trace.some((s) =>
        ["create_ticket", "update_ticket", "delete_ticket"].includes(s.tool_name || "")
      )
    ) {
      setTicketRefreshVersion((v) => v + 1);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      api
        .listConversations(searchQuery.trim() || undefined)
        .then(setConversations)
        .catch((err) => setSnack(errMsg(err)));
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const awaiting = messages.some((m) => m.awaitingConfirmation);

  const selectConversation = (id: number) => {
    setSelectedId(id);
    setMessages([]);
    setPanel(null);
    api
      .getHistory(id)
      .then((h) => {
        const ui = pairHistory(h);
        setMessages(ui);
        const paused = ui.find((m) => m.awaitingConfirmation);
        if (paused?.runId !== undefined) {
          openRun(paused.runId);
        }
      })
      .catch((err) => setSnack(errMsg(err)));
  };

  const newConversation = async () => {
    try {
      const created = await api.createConversation();
      const item = { ...created, created_at: new Date().toISOString() };
      setConversations((cs) => [item, ...cs]);
      selectConversation(created.id);
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  const applyOutcome = (outcome: RunOutcome) => {
    checkTicketMutation(outcome);
    if (outcome.status === "needs_confirmation") {
      setMessages((ms) => [
        ...ms,
        {
          role: "assistant",
          content: "The agent wants to take an action — review it in the trace panel.",
          runId: outcome.run_id,
          awaitingConfirmation: true,
        },
      ]);
    } else {
      const totalLatencyMs = outcome.trace.reduce(
        (sum, s) => sum + (s.latency_ms ?? 0),
        0
      );
      setMessages((ms) => [
        ...ms,
        {
          role: "assistant",
          content: outcome.answer ?? "",
          runId: outcome.run_id,
          stepCount: outcome.trace.length,
          totalLatencyMs,
        },
      ]);
    }
    setPanel({
      runId: outcome.run_id,
      status: outcome.status,
      steps: outcome.trace,
      pendingAction: outcome.pending_action,
    });
  };

  const abortRef = useRef<AbortController | null>(null);

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setBusy(false);
  };

  const send = async (customGoal?: string) => {
    const goal = (customGoal ?? draft).trim();
    if (!goal) return;

    let targetId = selectedId;
    if (!targetId) {
      try {
        const created = await api.createConversation();
        const item = { ...created, created_at: new Date().toISOString() };
        targetId = created.id;
        setSelectedId(created.id);
        setConversations((cs) => [item, ...cs]);
      } catch (err) {
        setSnack(errMsg(err));
        return;
      }
    }

    setMessages((ms) => [...ms, { role: "user", content: goal }]);
    if (!customGoal) setDraft("");
    setBusy(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const outcome = await api.sendMessage(targetId, goal, controller.signal);
      if (outcome.conversation_title) {
        setConversations((cs) =>
          cs.map((c) => (c.id === targetId ? { ...c, title: outcome.conversation_title! } : c))
        );
      }
      applyOutcome(outcome);
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setMessages((ms) => [
          ...ms,
          { role: "assistant", content: "Generation stopped by user." },
        ]);
      } else {
        setSnack(errMsg(err));
        if (!customGoal) setDraft(goal);
        setMessages((ms) => ms.slice(0, -1));
      }
    } finally {
      abortRef.current = null;
      setBusy(false);
    }
  };

  const confirm = async (approved: boolean) => {
    if (!panel) return;
    setBusy(true);
    try {
      const outcome = await api.confirmRun(panel.runId, approved);
      checkTicketMutation(outcome);
      if (outcome.status === "needs_confirmation") {
        setPanel({
          runId: outcome.run_id,
          status: outcome.status,
          steps: outcome.trace,
          pendingAction: outcome.pending_action,
        });
      } else {
        setMessages((ms) =>
          ms.map((m) =>
            m.runId === outcome.run_id && m.awaitingConfirmation
              ? {
                  role: "assistant" as const,
                  content: outcome.answer ?? "",
                  runId: outcome.run_id,
                  stepCount: outcome.trace.length,
                }
              : m
          )
        );
        setPanel({
          runId: outcome.run_id,
          status: outcome.status,
          steps: outcome.trace,
        });
      }
    } catch (err) {
      setSnack(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const openRun = async (runId: number) => {
    try {
      const run = await api.getRun(runId);
      setPanel({
        runId: run.id,
        status: run.status,
        steps: run.steps,
        totalLatencyMs: run.total_latency_ms,
        pendingAction: run.pending_action,
      });
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.deleteConversation(id);
      setConversations((cs) => cs.filter((c) => c.id !== id));
      if (selectedId === id) {
        setSelectedId(null);
        setMessages([]);
        setPanel(null);
      }
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  const sendPromptStarter = async (promptText: string) => {
    let convId = selectedId;
    if (convId === null) {
      try {
        const created = await api.createConversation();
        setConversations((cs) => [...cs, { ...created, created_at: "" }]);
        setSelectedId(created.id);
        convId = created.id;
      } catch (err) {
        setSnack(errMsg(err));
        return;
      }
    }
    setMessages([{ role: "user", content: promptText }]);
    setDraft("");
    setBusy(true);
    try {
      applyOutcome(await api.sendMessage(convId, promptText));
    } catch (err) {
      setSnack(errMsg(err));
      setDraft(promptText);
      setMessages([]);
    } finally {
      setBusy(false);
    }
  };

  const renameConversation = async (id: number, newTitle: string) => {
    try {
      const updated = await api.updateConversation(id, newTitle);
      setConversations((cs) =>
        cs.map((c) => (c.id === id ? { ...c, title: updated.title } : c))
      );
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mr: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.02em" }}>
              Our Company Name
            </Typography>
            <Chip
              label="Support Triage v1.0"
              size="small"
              sx={{
                height: 22,
                fontSize: "0.7rem",
                bgcolor: "rgba(255,255,255,0.12)",
                color: "#E2E8F0",
                fontWeight: 600,
              }}
            />
          </Box>

          <Tabs
            value={view}
            onChange={(_, v: "tickets" | "chat") => setView(v)}
            textColor="inherit"
            indicatorColor="secondary"
            sx={{ flexGrow: 1 }}
          >
            <Tab value="tickets" label="Tickets" sx={{ fontWeight: 600 }} />
            <Tab value="chat" label="Chat" sx={{ fontWeight: 600 }} />
          </Tabs>
          <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
            <Typography variant="body2" sx={{ color: "#E2E8F0", fontWeight: 500 }}>
              {email}
            </Typography>

            <Button
              color="inherit"
              size="small"
              variant="outlined"
              onClick={logout}
              sx={{ borderColor: "rgba(255,255,255,0.2)" }}
            >
              Logout
            </Button>
          </Box>
        </Toolbar>
      </AppBar>

      {view === "tickets" ? (
        <Box component="main" sx={{ flexGrow: 1, overflowY: "auto" }}>
          <Toolbar />
          <TicketsPage
            selectedConversationId={selectedId}
            onSelectConversation={selectConversation}
            onOpenFullChat={(convId) => {
              selectConversation(convId);
              setView("chat");
            }}
            conversations={conversations}
            onNewConversation={newConversation}
            onRefreshConversations={() => {
              api.listConversations().then(setConversations).catch(() => {});
            }}
            globalBusy={busy}
            globalMessages={messages}
            globalPendingAction={
              panel?.pendingAction
                ? { runId: panel.runId, tool: panel.pendingAction.tool, arguments: panel.pendingAction.arguments }
                : null
            }
            onGlobalSend={(g) => send(g)}
            onGlobalStop={handleStop}
            onGlobalConfirm={confirm}
            refreshVersion={ticketRefreshVersion}
          />
        </Box>
      ) : (
        <>
          <Drawer
            variant="permanent"
            sx={{
              width: DRAWER_WIDTH,
              "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" },
            }}
          >
            <Toolbar />
            <ConversationList
              conversations={conversations}
              selectedId={selectedId}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              onSelect={selectConversation}
              onDelete={deleteConversation}
              onRename={renameConversation}
              onNew={newConversation}
            />
          </Drawer>

          <Box
            component="main"
            sx={{ flexGrow: 1, display: "flex", flexDirection: "column", minWidth: 0 }}
          >
            <Toolbar />
            {selectedId === null ? (
              <Box sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <PromptStarters onSelectPrompt={sendPromptStarter} />
              </Box>
            ) : (
              <ChatView
                messages={messages}
                busy={busy}
                disabled={busy || awaiting}
                draft={draft}
                onDraftChange={setDraft}
                onSend={send}
                onSelectPrompt={sendPromptStarter}
                onOpenRun={openRun}
                pendingAction={panel?.pendingAction}
                onConfirm={confirm}
                onStop={handleStop}
              />
            )}
          </Box>
        </>
      )}
      <Snackbar
        open={snack !== null}
        autoHideDuration={5000}
        onClose={() => setSnack(null)}
        message={snack ?? ""}
      />
    </Box>
  );
}
