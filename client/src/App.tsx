import React, { useEffect, useState } from "react";
import {
  api,
  fetchRunDetails,
  fetchTickets,
  getCurrentUser,
  reseedTickets,
  triageTicket,
  updateTicket,
} from "./api";
import { AuthPage } from "./auth/AuthPage";
import { AICopilotWidget } from "./components/AICopilotWidget";

import { Header } from "./components/Header";
import { KnowledgeInspectorModal } from "./components/KnowledgeInspectorModal";
import { ObservabilityAuditView } from "./components/ObservabilityAuditView";
import { PipOnboardingModal } from "./components/PipOnboardingModal";
import { TicketQueue } from "./components/TicketQueue";
import { TicketWorkbench } from "./components/TicketWorkbench";
import { AgentRun, Ticket, UserProfile } from "./types";

export const mapBackendStepToText = (steps: Array<{ kind: string; tool_name?: string }>): string => {
  if (!steps || steps.length === 0) {
    return "🧠 Analyzing query intent...";
  }

  const latest = steps[steps.length - 1];

  if (latest.kind === "tool_call") {
    switch (latest.tool_name) {
      case "search_knowledge":
        return "🔍 Searching audited policy knowledge base...";
      case "list_tickets":
        return "📋 Retrieving active support tickets...";
      case "escalate":
        return "⚠️ Processing ticket escalation...";
      default:
        return `🛠️ Executing ${latest.tool_name}...`;
    }
  }

  if (latest.kind === "llm_call") {
    return "📚 Parsing retrieved documents & reasoning...";
  }

  return "⚡ Processing agent workflow...";
};


export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("apexcare_token"));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [activeView, setActiveView] = useState<"workbench" | "observability" | "knowledge">("workbench");
  const [darkMode, setDarkMode] = useState<boolean>(false);
  const [isLoadingTickets, setIsLoadingTickets] = useState<boolean>(false);
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false);
  const [auditResetKey, setAuditResetKey] = useState<number>(0);
  const [pendingDraftQuery, setPendingDraftQuery] = useState<string | null>(null);
  const [isPipThinking, setIsPipThinking] = useState<boolean>(false);

  // Per-ticket triage processing state map
  interface TicketTriageState {
    isProcessing: boolean;
    runId?: number;
    statusText?: string;
  }

  const [triagingTickets, setTriagingTickets] = useState<Record<number, TicketTriageState>>({});
  const triageAbortControllersRef = React.useRef<Record<number, AbortController>>({});

  // Polling hook/effect for active runs:
  useEffect(() => {
    const activeEntries = Object.entries(triagingTickets).filter(
      ([_, state]) => state.isProcessing && state.runId
    );

    if (activeEntries.length === 0) return;

    const pollInterval = setInterval(async () => {
      const token = localStorage.getItem("apexcare_token");

      for (const [ticketIdStr, state] of activeEntries) {
        if (!state.runId) continue;
        try {
          const res = await fetch(`/api/runs/${state.runId}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
          if (res.ok) {
            const data = await res.json();
            const liveText = mapBackendStepToText(data.steps || []);

            setTriagingTickets((prev) => ({
              ...prev,
              [Number(ticketIdStr)]: {
                ...prev[Number(ticketIdStr)],
                statusText: liveText,
              },
            }));
          }
        } catch (err) {
          // Ignore transient poll errors
        }
      }
    }, 700);

    return () => clearInterval(pollInterval);
  }, [triagingTickets]);




  // Load user session
  useEffect(() => {
    if (token) {
      getCurrentUser()
        .then((u) => setUser(u))
        .catch(() => handleLogout());
    }
  }, [token]);

  // Load tickets when user is authenticated
  useEffect(() => {
    if (user) {
      loadTickets();
    }
  }, [user]);

  // Apply dark mode class to document
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [darkMode]);

  const loadTickets = async () => {
    setIsLoadingTickets(true);
    try {
      const data = await fetchTickets();
      setTickets(data);
      if (data.length > 0) {
        if (!selectedTicket) {
          setSelectedTicket(data[0]);
        } else {
          const fresh = data.find((t) => t.id === selectedTicket.id);
          if (fresh) setSelectedTicket(fresh);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const handleLoginSuccess = (authToken: string, authUser: UserProfile, isNewOrDemo?: boolean) => {
    localStorage.setItem("apexcare_token", authToken);
    setToken(authToken);
    setUser(authUser);
    if (isNewOrDemo) {
      setShowOnboarding(true);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("apexcare_token");
    setToken(null);
    setUser(null);
    setSelectedTicket(null);
    setTickets([]);
  };

  const handleReseed = async () => {
    try {
      setIsLoadingTickets(true);
      const fresh = await reseedTickets();
      setTickets(fresh);
      if (fresh.length > 0) {
        setSelectedTicket(fresh[0]);
      } else {
        setSelectedTicket(null);
      }
      setAuditResetKey((prev) => prev + 1);
      setTriagingTickets({});
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const handleDraftWithPip = (ticket: Ticket) => {
    const draftMsg = `Help me write a draft reply to ${ticket.requester_name} for ticket #${ticket.ticket_number || ticket.id} (${ticket.title}):\n\n"${ticket.description}"`;
    setPendingDraftQuery(draftMsg);
  };

  const handleRunTriage = async (ticket: Ticket) => {
    setLatestRun(null);
    setTriagingTickets((prev) => ({
      ...prev,
      [ticket.id]: { isProcessing: true, statusText: "🧠 Analyzing query intent..." },
    }));

    const controller = new AbortController();
    triageAbortControllersRef.current[ticket.id] = controller;

    // Fetch the latest run after a tiny delay so /triage has started and committed the run.
    setTimeout(async () => {
      try {
        const token = localStorage.getItem("apexcare_token");
        const res = await fetch("/api/runs?page=1&per_page=1", {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const data = await res.json();
          if (data.runs && data.runs.length > 0) {
            const latest = data.runs[0];
            if (latest.status === "running") {
              setTriagingTickets((prev) => {
                if (!prev[ticket.id]) return prev;
                return {
                  ...prev,
                  [ticket.id]: { ...prev[ticket.id], runId: latest.id },
                };
              });
            }
          }
        }
      } catch (err) {
        console.error("Failed to fetch active run ID early for triage:", err);
      }
    }, 200);

    try {
      const res = await triageTicket(ticket.id, { signal: controller.signal });
      let runObj = res.run;

      if (!runObj?.steps || runObj.steps.length === 0) {
        try {
          const details = await fetchRunDetails(runObj.run_id);
          runObj = { ...runObj, steps: details.steps };
        } catch (e) {
          console.error(e);
        }
      }

      const draftText =
        runObj?.pending_action?.arguments?.reply_text ||
        res.ticket.draft_reply ||
        runObj?.answer ||
        "";

      const updatedTicket = { ...res.ticket, draft_reply: draftText };
      
      if (selectedTicket?.id === ticket.id) {
        setSelectedTicket(updatedTicket);
        setLatestRun(runObj);
      }
      setTickets((prev) => prev.map((t) => (t.id === updatedTicket.id ? updatedTicket : t)));
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
      }
      alert(err.message || "Triage failed");
    } finally {
      setTriagingTickets((prev) => {
        const copy = { ...prev };
        delete copy[ticket.id];
        return copy;
      });
      delete triageAbortControllersRef.current[ticket.id];
    }
  };

  /** Approve or reject a triage-paused escalate action */
  const handleConfirmPending = async (approved: boolean) => {
    const runId = latestRun?.run_id || (latestRun as any)?.id;
    if (!runId) return;
    try {
      const outcome = await api.confirmRun(runId, approved);
      let runObj: any = outcome;
      try {
        const details = await fetchRunDetails(runId);
        runObj = { ...outcome, steps: details.steps, pending_action: (details as any).pending_action };
      } catch {
        /* keep outcome */
      }
      setLatestRun(runObj);

      // Refresh tickets so draft_pending / escalated state is visible
      const list = await fetchTickets();
      setTickets(list);
      if (selectedTicket) {
        const refreshed = list.find((t) => t.id === selectedTicket.id) || null;
        setSelectedTicket(refreshed);
      }
    } catch (err: any) {
      alert(err.message || "Confirmation failed");
    }
  };

  const handleStopTriage = async (ticketId: number) => {
    triageAbortControllersRef.current[ticketId]?.abort();
    setTriagingTickets((prev) => {
      const copy = { ...prev };
      delete copy[ticketId];
      return copy;
    });
    delete triageAbortControllersRef.current[ticketId];

    const runId = triagingTickets[ticketId]?.runId || (selectedTicket?.id === ticketId ? latestRun?.run_id : null);
    if (runId) {
      try {
        const token = localStorage.getItem("apexcare_token");
        await fetch(`/api/runs/${runId}/stop`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
      } catch (err) {
        console.error("Failed to notify backend of stopped run:", err);
      }
    }
  };

  const handleUpdateTicketStatus = async (ticketId: number, status: Ticket["status"]) => {
    try {
      const updated = await updateTicket(ticketId, { status });
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket?.id === ticketId) setSelectedTicket(updated);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUpdateResolutionNotes = async (ticketId: number, notes: string) => {
    try {
      const updated = await updateTicket(ticketId, { resolution_notes: notes });
      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket?.id === ticketId) setSelectedTicket(updated);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendReply = async (ticketId: number, replyText: string) => {
    try {
      const newReplyObj = {
        id: `reply_${Date.now()}`,
        sender: "Alexandra Vance (HR Specialist)",
        text: replyText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      const updated = await updateTicket(ticketId, {
        status: "resolved",
        draft_reply: null,
        new_reply: newReplyObj,
      } as any);

      setTickets((prev) => prev.map((t) => (t.id === ticketId ? updated : t)));
      if (selectedTicket?.id === ticketId) setSelectedTicket(updated);
    } catch (err) {
      console.error(err);
    }
  };





  if (!token || !user) {
    return <AuthPage onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-sans transition-colors duration-200">
      {/* Top Header Navbar */}
      <Header
        user={user}
        activeView={activeView}
        setActiveView={setActiveView}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        onLogout={handleLogout}
        onReseed={handleReseed}
      />

      {/* Main View Router */}
      <div className="flex-1 flex overflow-hidden relative">
        {activeView === "knowledge" && (
          <KnowledgeInspectorModal onClose={() => setActiveView("workbench")} />
        )}
        {activeView === "observability" && (
          <ObservabilityAuditView key={auditResetKey} onClose={() => setActiveView("workbench")} />
        )}

        {/* Primary Triage Workbench Layout */}
        <div className={`flex-1 flex flex-row w-full h-full overflow-hidden ${activeView === "workbench" ? "" : "hidden"}`}>
          {/* Left Ticket Queue Sidebar (~30%) */}
          <div className="w-80 lg:w-96 shrink-0 h-full overflow-hidden">
            <TicketQueue
              tickets={tickets}
              selectedTicket={selectedTicket}
              onSelectTicket={(t) => setSelectedTicket(t)}
              isLoading={isLoadingTickets}
              triagingTickets={triagingTickets}
            />
          </div>

          {/* Center Ticket Workbench Panel (~45%) — min-w-0 prevents intrinsic width layout expansion on remount */}
          <div className="flex-1 min-w-0 h-full overflow-hidden flex flex-col">
            <TicketWorkbench
              key={auditResetKey}
              ticket={selectedTicket || (tickets.length > 0 ? tickets[0] : null)}
              onDraftWithPip={handleDraftWithPip}
              isPipProcessing={isPipThinking}
              onRunTriage={handleRunTriage}
              onStopTriage={handleStopTriage}
              onUpdateTicketStatus={handleUpdateTicketStatus}
              onSendReply={handleSendReply}
              onUpdateResolutionNotes={handleUpdateResolutionNotes}
              triagingTickets={triagingTickets}
              latestRun={latestRun}
              onConfirmPending={handleConfirmPending}
            />
          </div>

          {/* Right AI Copilot Assistant (~25%) — shrink-0 prevents width collapse during center panel re-renders */}
          <div className="w-80 xl:w-96 shrink-0 h-full overflow-hidden">
            <AICopilotWidget
              key={auditResetKey}
              user={user}
              activeTicket={selectedTicket}
              tickets={tickets}
              latestRun={latestRun}
              isProcessing={selectedTicket ? Boolean(triagingTickets[selectedTicket.id]?.isProcessing) : false}
              pendingDraftQuery={pendingDraftQuery}
              onClearPendingDraftQuery={() => setPendingDraftQuery(null)}
              onBotThinkingChange={setIsPipThinking}
              onTicketUpdated={loadTickets}
            />
          </div>
        </div>
      </div>





      {/* Onboarding Tutorial Modal */}
      {showOnboarding && user && (
        <PipOnboardingModal
          userName={user.full_name}
          onComplete={() => setShowOnboarding(false)}
        />
      )}
    </div>
  );
}
