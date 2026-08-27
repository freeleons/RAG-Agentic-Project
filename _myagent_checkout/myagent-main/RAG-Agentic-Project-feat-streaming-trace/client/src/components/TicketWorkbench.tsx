import React, { useEffect, useRef, useState } from "react";
import { AgentRun, Ticket } from "../types";

interface TicketWorkbenchProps {
  ticket: Ticket | null;
  onDraftWithPip?: (ticket: Ticket) => void;
  isPipProcessing?: boolean;
  onRunTriage?: (ticket: Ticket) => void;
  onStopTriage?: (ticketId: number) => void;
  onUpdateTicketStatus: (ticketId: number, status: Ticket["status"]) => void;
  onSendReply: (ticketId: number, replyText: string) => void;
  onUpdateResolutionNotes: (ticketId: number, notes: string) => void;
  triagingTickets?: Record<number, { isProcessing: boolean; runId?: number; statusText?: string }>;
  /** Latest triage run; includes pending_action when HITL confirmation is required */
  latestRun?: AgentRun | null;
  /** Approve or reject a consequential tool (escalate) */
  onConfirmPending?: (approved: boolean) => void;
}

export const TicketWorkbench: React.FC<TicketWorkbenchProps> = ({
  ticket,
  onDraftWithPip,
  isPipProcessing = false,
  onRunTriage,
  onStopTriage,
  onUpdateTicketStatus,
  onSendReply,
  onUpdateResolutionNotes,
  triagingTickets = {},
  latestRun = null,
  onConfirmPending,
}) => {
  const [replyInput, setReplyInput] = useState("");
  // Persistent reply state memory map indexed by ticket ID
  const [ticketDrafts, setTicketDrafts] = useState<Record<number, string>>({});
  const lastSeenDrafts = useRef<Record<number, string | null | undefined>>({});
  const ticketChatEndRef = useRef<HTMLDivElement | null>(null);

  const [isEditingResolution, setIsEditingResolution] = useState(false);
  const [tempResolutionNotes, setTempResolutionNotes] = useState("");

  // Sync state for resolution notes when ticket ID changes
  useEffect(() => {
    setIsEditingResolution(false);
    setTempResolutionNotes(ticket?.resolution_notes || "");
  }, [ticket?.id]);

  const currentTriage = ticket ? triagingTickets[ticket.id] : null;
  const isTicketTriaging = Boolean(currentTriage?.isProcessing);
  const liveStatusText = currentTriage?.statusText || "🧠 Analyzing query intent...";

  const scrollToBottom = () => {
    ticketChatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Auto-scroll chat timeline to bottom when replies arrive or status changes
  useEffect(() => {
    scrollToBottom();
    const timer = setTimeout(scrollToBottom, 50);
    return () => clearTimeout(timer);
  }, [ticket?.id, ticket?.status, ticket?.draft_reply, ticket?.replies, ticket?.replies?.length, isTicketTriaging]);

  // Sync or restore ticket-specific draft text when switching active tickets or when Pip drafts a response
  useEffect(() => {
    if (!ticket) return;

    const hasNewDraftFromPip =
      ticket.draft_reply && ticket.draft_reply !== lastSeenDrafts.current[ticket.id];

    // 1. If Pip just generated a new draft reply, ALWAYS populate it and update cache
    if (hasNewDraftFromPip) {
      setReplyInput(ticket.draft_reply!);
      setTicketDrafts((prev) => ({ ...prev, [ticket.id]: ticket.draft_reply! }));
      lastSeenDrafts.current[ticket.id] = ticket.draft_reply;
      return;
    }

    // 2. Otherwise, if user has active local edits saved in memory for this ticket, preserve them
    if (ticketDrafts[ticket.id] !== undefined) {
      setReplyInput(ticketDrafts[ticket.id]);
      return;
    }

    // 3. Fallback whenever ticket has a draft_reply
    if (ticket.draft_reply) {
      setReplyInput(ticket.draft_reply);
      setTicketDrafts((prev) => ({ ...prev, [ticket.id]: ticket.draft_reply! }));
      lastSeenDrafts.current[ticket.id] = ticket.draft_reply;
    } else if (ticket.status === "open") {
      setReplyInput("");
    }
  }, [ticket?.id, ticket?.status, ticket?.draft_reply]);

  const handleInputChange = (val: string) => {
    setReplyInput(val);
    if (ticket) {
      setTicketDrafts((prev) => ({ ...prev, [ticket.id]: val }));
    }
  };

  if (!ticket) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50 dark:bg-slate-950/20">
        <div className="w-16 h-16 rounded-2xl bg-blue-500/10 text-blue-600 flex items-center justify-center mb-4 border border-blue-500/20">
          ⚡
        </div>
        <h3 className="font-bold text-base text-slate-900 dark:text-white mb-1">Select a Support Ticket</h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm">
          Click any employee ticket from the queue on the left to view the issue and interact with Pip.
        </p>
      </div>
    );
  }

  const handleSaveResolutionNotes = () => {
    if (ticket) {
      onUpdateResolutionNotes(ticket.id, tempResolutionNotes);
      setIsEditingResolution(false);
    }
  };

  const handleManualSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyInput.trim() || isTicketTriaging) return;
    onSendReply(ticket.id, replyInput);
    setReplyInput("");
    setTicketDrafts((prev) => {
      const copy = { ...prev };
      delete copy[ticket.id];
      return copy;
    });
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50 dark:bg-slate-950/20">
      {/* Top Header Bar */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between shadow-xs">
        {/* Left: Employee Info */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-500 text-white font-bold text-sm flex items-center justify-center shadow-md shadow-blue-500/20">
            {ticket.requester_name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .toUpperCase()}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="font-bold text-base text-slate-900 dark:text-white">{ticket.requester_name}</h2>
              <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
                {ticket.category}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-bold border uppercase tracking-wide ${
                ticket.priority === "urgent"
                  ? "bg-red-500/10 text-red-700 dark:text-red-400 border-red-500/20"
                  : ticket.priority === "high"
                  ? "bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/20"
                  : ticket.priority === "low"
                  ? "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20"
                  : "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20"
              }`}>
                {ticket.priority}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              {ticket.requester_department} • {ticket.requester_email}
            </p>
          </div>
        </div>

        {/* Right: Status Dropdown */}
        <div className="flex items-center space-x-2">
          <label className="text-xs text-slate-500 dark:text-slate-400 font-bold">Status:</label>
          <select
            value={ticket.status}
            onChange={(e) => onUpdateTicketStatus(ticket.id, e.target.value as any)}
            className="text-xs font-bold px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none cursor-pointer"
          >
            <option value="open">Open</option>
            <option value="in_triage">In Triage</option>
            <option value="draft_pending">Draft Pending</option>
            <option value="escalated">Escalated</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>
      </div>

      {/* Ticket Details & Phone Chat App Thread Container */}
      <div className="flex-1 flex flex-col justify-between overflow-hidden p-4 md:p-6 space-y-4">
        <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4 pr-1 flex flex-col">
          {/* Ticket Header Title Card */}
          <div className="bg-white dark:bg-slate-900/80 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-xs">
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 font-semibold">
              <span className="font-mono text-blue-600 dark:text-blue-400 font-bold">{ticket.ticket_number}</span>
              <span>Channel: {ticket.channel} • {ticket.created_at.slice(0, 10)}</span>
            </div>
            <h1 className="text-base font-bold text-slate-900 dark:text-white leading-snug">{ticket.title}</h1>
          </div>

          {/* Chat Messages Timeline (Phone App Chat UI) */}
          <div className="space-y-4 pt-2 flex flex-col">
            {/* 1. Employee Message (Left Bubble) */}
            <div className="flex space-x-3 items-start max-w-[88%]">
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                {ticket.requester_name.charAt(0)}
              </div>
              <div className="bg-white dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 p-4 rounded-2xl rounded-tl-none shadow-xs space-y-1">
                <div className="flex items-center justify-between space-x-4">
                  <span className="font-bold text-xs text-slate-900 dark:text-white">{ticket.requester_name}</span>
                  <span className="text-[10px] text-slate-400 font-mono">10:40 PM</span>
                </div>
                <p className="text-xs text-slate-800 dark:text-slate-200 leading-relaxed font-medium">
                  {ticket.description}
                </p>
              </div>
            </div>

            {/* 2. HR Worker Sent Reply Bubbles (Accumulated Sent Replies) */}
            {ticket.replies && ticket.replies.length > 0 ? (
              ticket.replies.map((reply) => (
                <div key={reply.id} className="flex space-x-3 items-start justify-end">
                  <div className="bg-blue-600 text-white p-4 rounded-2xl rounded-tr-none max-w-[85%] shadow-md space-y-1">
                    <div className="flex items-center justify-between space-x-4">
                      <span className="font-bold text-xs text-white">{reply.sender}</span>
                      <span className="text-[10px] text-white/70 font-mono">{reply.timestamp}</span>
                    </div>
                    <p className="text-xs leading-relaxed font-medium whitespace-pre-wrap">
                      {reply.text}
                    </p>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                    AV
                  </div>
                </div>
              ))
            ) : ticket.status === "resolved" ? (
              <div className="flex space-x-3 items-start justify-end">
                <div className="bg-blue-600 text-white p-4 rounded-2xl rounded-tr-none max-w-[85%] shadow-md space-y-1">
                  <div className="flex items-center justify-between space-x-4">
                    <span className="font-bold text-xs text-white">Alexandra Vance (HR Specialist)</span>
                    <span className="text-[10px] text-white/70 font-mono">Just now</span>
                  </div>
                  <p className="text-xs leading-relaxed font-medium">
                    {ticket.draft_reply || "Your ticket inquiry has been addressed per official Antra policy."}
                  </p>
                </div>
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                  AV
                </div>
              </div>
            ) : null}

            {/* 3. Escalation Alert */}
            {ticket.escalation_reason && (
              <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-800 dark:text-rose-300 text-xs font-medium space-y-1">
                <span className="font-bold block text-rose-700 dark:text-rose-400">🚨 Tier-2 Escalation</span>
                <p>{ticket.escalation_reason}</p>
              </div>
            )}

            {/* 4. Resolution Notes Card */}
            {ticket.status === "resolved" && (
              <div className="p-3.5 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-800 dark:text-emerald-300 text-xs font-medium space-y-2">
                <span className="font-bold block text-emerald-700 dark:text-emerald-400">✅ Ticket Resolution Notes</span>
                {isEditingResolution ? (
                  <div className="space-y-2">
                    <textarea
                      value={tempResolutionNotes}
                      onChange={(e) => setTempResolutionNotes(e.target.value)}
                      placeholder="Enter how this ticket was resolved..."
                      className="w-full p-2 text-xs bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg focus:outline-none text-slate-900 dark:text-white"
                      rows={3}
                    />
                    <div className="flex space-x-2">
                      <button
                        type="button"
                        onClick={handleSaveResolutionNotes}
                        className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-[10px] font-bold cursor-pointer"
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => setIsEditingResolution(false)}
                        className="px-3 py-1 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 text-slate-800 dark:text-slate-200 rounded-lg text-[10px] font-bold cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex justify-between items-start">
                    <p className="italic">{ticket.resolution_notes || "No resolution notes entered yet."}</p>
                    <button
                      type="button"
                      onClick={() => {
                        setTempResolutionNotes(ticket.resolution_notes || "");
                        setIsEditingResolution(true);
                      }}
                      className="ml-2 px-2 py-0.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-700 dark:text-emerald-300 rounded-md text-[10px] font-bold cursor-pointer shrink-0"
                    >
                      Edit
                    </button>
                  </div>
                )}
              </div>
            )}
            {/* Auto-scroll target */}
            <div ref={ticketChatEndRef} />
          </div>
        </div>

        {/* HITL: consequential tool awaiting staff approval */}
        {latestRun?.status === "needs_confirmation" && latestRun.pending_action && onConfirmPending && (
          <div className="w-full p-3 rounded-2xl border border-amber-400/40 bg-amber-50 dark:bg-amber-950/30 space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-amber-800 dark:text-amber-300">
                Pending action: {latestRun.pending_action.tool}
              </p>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-amber-200/80 dark:bg-amber-900/60 text-amber-900 dark:text-amber-200 font-bold">
                Requires Approval
              </span>
            </div>

            {latestRun.pending_action.tool === "escalate" ? (
              <div className="p-2.5 rounded-xl bg-white/80 dark:bg-slate-900/70 border border-amber-300/60 dark:border-amber-800/60 space-y-1 text-xs">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Escalation Details:</span>
                <p className="text-slate-800 dark:text-slate-200">
                  <span className="font-semibold">Priority:</span> {String(latestRun.pending_action.arguments?.priority ?? "")}
                </p>
                <p className="text-slate-800 dark:text-slate-200">
                  <span className="font-semibold">Reason:</span> {String(latestRun.pending_action.arguments?.reason ?? "")}
                </p>
              </div>
            ) : (
              <p className="text-[11px] text-amber-900/80 dark:text-amber-200/80 font-mono whitespace-pre-wrap break-words">
                {JSON.stringify(latestRun.pending_action.arguments, null, 2)}
              </p>
            )}

            <div className="flex space-x-2 pt-1">
              <button
                type="button"
                onClick={() => onConfirmPending(true)}
                className="px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold cursor-pointer transition-colors shadow-sm"
              >
                Approve & Execute
              </button>
              <button
                type="button"
                onClick={() => onConfirmPending(false)}
                className="px-3 py-1.5 rounded-xl bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-100 text-xs font-bold cursor-pointer transition-colors"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {/* Bottom Phone Chat Reply Box & Sleek Action Bar */}
        <div className="w-full pt-3 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 rounded-2xl shadow-md space-y-3 flex flex-col">
          <form onSubmit={handleManualSend} className="w-full space-y-3 flex flex-col">
            <div className="relative">
              <textarea
                rows={6}
                disabled={isTicketTriaging}
                placeholder={
                  isTicketTriaging
                    ? ""
                    : `Write a reply to ${ticket.requester_name.split(" ")[0]} or click "Draft with Pip"...`
                }
                value={
                  isTicketTriaging
                    ? liveStatusText
                    : replyInput
                }
                onChange={(e) => handleInputChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleManualSend(e);
                  }
                }}
                className={`w-full p-4 rounded-2xl text-xs sm:text-sm leading-relaxed transition-all min-h-[140px] max-h-[280px] overflow-y-auto custom-scrollbar font-medium ${isTicketTriaging
                    ? "bg-blue-500/10 dark:bg-blue-500/20 border-2 border-blue-500/60 text-blue-700 dark:text-blue-300 font-mono font-bold animate-pulse"
                    : "bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  }`}
              />
            </div>

            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] text-slate-500 dark:text-slate-400 font-medium truncate max-w-[180px] sm:max-w-xs">
                Pip assists with policy retrieval.
              </span>

              <div className="flex items-center space-x-3 ml-auto shrink-0">
                {/* "Draft with Pip" or "Stop Drafting" Button */}
                {isTicketTriaging ? (
                  <button
                    type="button"
                    onClick={() => ticket && onStopTriage?.(ticket.id)}
                    className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-extrabold text-xs flex items-center space-x-1.5 transition shadow-md cursor-pointer whitespace-nowrap shadow-rose-500/20"
                  >
                    <span>⏹️</span>
                    <span>Stop Drafting</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => ticket && (onDraftWithPip ? onDraftWithPip(ticket) : onRunTriage?.(ticket))}
                    disabled={!ticket || isPipProcessing || ticket.status === "resolved" || ticket.status === "closed"}
                    className={`px-4 py-2 rounded-xl font-extrabold text-xs flex items-center space-x-1.5 transition shadow-md whitespace-nowrap ${
                      !ticket || isPipProcessing || ticket.status === "resolved" || ticket.status === "closed"
                        ? "bg-slate-200 dark:bg-slate-800 text-slate-400 dark:text-slate-500 border border-slate-300 dark:border-slate-700 cursor-not-allowed opacity-60 shadow-none"
                        : "bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 text-white hover:opacity-95 shadow-blue-500/25 pulse-glow cursor-pointer"
                    }`}
                  >
                    <span>{isPipProcessing ? "⏳" : "✨"}</span>
                    <span>{isPipProcessing ? "Drafting with Pip..." : "Draft with Pip"}</span>
                  </button>
                )}

                {/* Primary Button: "Send Reply" (HR Specialist Sends) */}
                <button
                  type="submit"
                  disabled={!replyInput.trim() || isTicketTriaging}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-xl text-xs font-extrabold transition cursor-pointer shadow-md shadow-emerald-500/20 whitespace-nowrap"
                >
                  Send Reply
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
