import React, { useEffect, useState } from "react";
import {
  createTicket,
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
import { TicketQueue } from "./components/TicketQueue";
import { TicketWorkbench } from "./components/TicketWorkbench";
import { AgentRun, Ticket, UserProfile } from "./types";

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("apexcare_token"));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [activeView, setActiveView] = useState<"workbench" | "observability" | "knowledge">("workbench");
  const [darkMode, setDarkMode] = useState<boolean>(false);
  const [isLoadingTickets, setIsLoadingTickets] = useState<boolean>(false);
  const [isTriaging, setIsTriaging] = useState<boolean>(false);
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [showNewTicketModal, setShowNewTicketModal] = useState<boolean>(false);


  // New ticket form state
  const [newTitle, setNewTitle] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newCategory, setNewCategory] = useState<Ticket["category"]>("HR & Benefits");
  const [newPriority, setNewPriority] = useState<Ticket["priority"]>("medium");

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
      if (data.length > 0 && !selectedTicket) {
        setSelectedTicket(data[0]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const handleLoginSuccess = (authToken: string, authUser: UserProfile) => {
    localStorage.setItem("apexcare_token", authToken);
    setToken(authToken);
    setUser(authUser);
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
      if (fresh.length > 0) setSelectedTicket(fresh[0]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const triageAbortControllerRef = React.useRef<AbortController | null>(null);

  const handleRunTriage = async (ticket: Ticket) => {
    setIsTriaging(true);
    setLatestRun(null);
    const controller = new AbortController();
    triageAbortControllerRef.current = controller;

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
      setSelectedTicket(updatedTicket);
      setLatestRun(runObj);
      setTickets((prev) => prev.map((t) => (t.id === updatedTicket.id ? updatedTicket : t)));
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
      }
      alert(err.message || "Triage failed");
    } finally {
      setIsTriaging(false);
    }
  };

  const handleStopTriage = () => {
    triageAbortControllerRef.current?.abort();
    setIsTriaging(false);
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



  const handleCreateTicketSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newDesc.trim()) return;
    try {
      const created = await createTicket({
        title: newTitle,
        description: newDesc,
        category: newCategory,
        priority: newPriority,
        requester_name: "Self / Internal Agent",
        requester_email: user?.email || "specialist@apexcare.tech",
        requester_department: user?.department || "HR Operations",
      });
      setTickets((prev) => [created, ...prev]);
      setSelectedTicket(created);
      setShowNewTicketModal(false);
      setNewTitle("");
      setNewDesc("");
    } catch (err: any) {
      alert(err.message || "Failed to create ticket");
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
          <ObservabilityAuditView onClose={() => setActiveView("workbench")} />
        )}

        {/* Primary Triage Workbench Layout */}
        <div className={`flex-1 flex overflow-hidden ${activeView === "workbench" ? "" : "hidden"}`}>
          {/* Left Ticket Queue Sidebar (~30%) */}
          <div className="w-80 lg:w-96 shrink-0 h-full">
            <TicketQueue
              tickets={tickets}
              selectedTicket={selectedTicket}
              onSelectTicket={(t) => setSelectedTicket(t)}
              onCreateNewTicket={() => setShowNewTicketModal(true)}
              isLoading={isLoadingTickets}
            />
          </div>

          {/* Center Ticket Workbench Panel (~45%) */}
          <TicketWorkbench
            ticket={selectedTicket}
            onRunTriage={handleRunTriage}
            onStopTriage={handleStopTriage}
            onUpdateTicketStatus={handleUpdateTicketStatus}
            onSendReply={handleSendReply}
            isTriaging={isTriaging}
          />

          {/* Right AI Copilot Assistant & Trace Drawer (~25%) */}
          <AICopilotWidget
            user={user}
            activeTicket={selectedTicket}
            tickets={tickets}
            latestRun={latestRun}
            isProcessing={isTriaging}
          />
        </div>
      </div>



      {/* New Ticket Modal */}
      {showNewTicketModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 dark:bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-white dark:bg-slate-900 w-full max-w-lg p-6 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-4 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <h3 className="font-bold text-base text-slate-900 dark:text-white">+ Create Support Ticket</h3>
              <button
                onClick={() => setShowNewTicketModal(false)}
                className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white font-bold text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTicketSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Ticket Title / Subject</label>
                <input
                  type="text"
                  required
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. FSA rollover inquiry for 2026 plan year"
                  className="w-full px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Issue Description</label>
                <textarea
                  rows={4}
                  required
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Detail the employee's issue or policy question..."
                  className="w-full p-3 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Category</label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="HR & Benefits">HR & Benefits</option>
                    <option value="IT Support">IT Support</option>
                    <option value="Billing & Expenses">Billing & Expenses</option>
                    <option value="General">General</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Priority</label>
                  <select
                    value={newPriority}
                    onChange={(e) => setNewPriority(e.target.value as any)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-100 dark:bg-slate-950 border border-slate-300 dark:border-slate-800 text-xs text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewTicketModal(false)}
                  className="px-4 py-2 bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-300 dark:hover:bg-slate-700 rounded-xl text-xs font-semibold cursor-pointer transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold cursor-pointer transition shadow-sm"
                >
                  Create Ticket
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
