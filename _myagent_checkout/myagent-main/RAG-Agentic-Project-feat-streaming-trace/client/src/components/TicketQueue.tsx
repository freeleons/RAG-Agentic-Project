import React, { useState } from "react";
import { Ticket } from "../types";

interface TicketQueueProps {
  tickets: Ticket[];
  selectedTicket: Ticket | null;
  onSelectTicket: (ticket: Ticket) => void;
  isLoading: boolean;
  triagingTickets?: Record<
    number,
    { isProcessing: boolean; runId?: number; statusText?: string }
  >;
}

export const TicketQueue: React.FC<TicketQueueProps> = ({
  tickets,
  selectedTicket,
  onSelectTicket,
  isLoading,
  triagingTickets,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("All");

  const filteredTickets = tickets.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.requester_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.ticket_number.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCategory = categoryFilter === "All" || t.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case "open":
        return "status-open";
      case "in_triage":
        return "status-in_triage";
      case "draft_pending":
        return "status-draft_pending";
      case "escalated":
        return "status-escalated";
      case "resolved":
        return "status-resolved";
      default:
        return "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300";
    }
  };

  return (
    <div className="w-full h-full flex flex-col border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden">
      {/* Queue Header */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h2 className="font-bold text-base text-slate-900 dark:text-white">Tickets</h2>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
              {filteredTickets.length}
            </span>
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <input
            type="text"
            placeholder="Search tickets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 rounded-xl text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <svg className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* Category Filter Dropdown */}
        <div className="flex items-center space-x-2">
          <label className="text-[11px] font-bold text-slate-500 dark:text-slate-400 shrink-0">Category:</label>
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="w-full px-2.5 py-1 rounded-xl text-xs font-semibold bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white focus:outline-none cursor-pointer"
          >
            <option value="All">All Categories</option>
            <option value="HR & Benefits">HR & Benefits</option>
            <option value="Leaves & Disability">Leaves & Disability</option>
            <option value="Policies & Claims">Policies & Claims</option>
          </select>
        </div>
      </div>

      {/* Ticket Cards List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2 flex flex-col">
        {isLoading ? (
          <div className="p-8 text-center text-xs text-slate-500">Loading tickets...</div>
        ) : filteredTickets.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-500">No tickets found.</div>
        ) : (
          filteredTickets.map((ticket) => {
            const isSelected = selectedTicket?.id === ticket.id;
            return (
              <div
                key={ticket.id}
                onClick={() => onSelectTicket(ticket)}
                className={`p-3 rounded-xl border transition-all cursor-pointer ${isSelected
                    ? "bg-blue-50 dark:bg-blue-500/10 border-blue-500 dark:border-blue-500/50 shadow-sm"
                    : "bg-white dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/60 hover:border-slate-300 dark:hover:border-slate-600"
                  }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-[11px] font-bold text-slate-600 dark:text-slate-400">
                    {ticket.ticket_number}
                  </span>
                  <div className="flex items-center space-x-1">
                    {triagingTickets && triagingTickets[ticket.id]?.isProcessing && (
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-500 text-white animate-pulse flex items-center space-x-0.5">
                        <span>🤖 Triaging...</span>
                      </span>
                    )}
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase ${
                      ticket.priority === "urgent"
                        ? "bg-red-500/10 text-red-700 dark:text-red-400"
                        : ticket.priority === "high"
                        ? "bg-orange-500/10 text-orange-700 dark:text-orange-400"
                        : ticket.priority === "low"
                        ? "bg-slate-500/10 text-slate-600 dark:text-slate-400"
                        : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                    }`}>
                      {ticket.priority}
                    </span>
                    <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${getStatusBadgeClass(ticket.status)}`}>
                      {ticket.status.replace("_", " ").toUpperCase()}
                    </span>
                  </div>
                </div>

                <h3 className="font-bold text-xs text-slate-900 dark:text-white line-clamp-1 mb-1">
                  {ticket.title}
                </h3>

                <div className="flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 pt-1.5 border-t border-slate-100 dark:border-slate-800">
                  <span className="font-semibold text-slate-800 dark:text-slate-300">{ticket.requester_name}</span>
                  <span className="font-mono text-emerald-700 dark:text-emerald-400 font-bold">⏱️ {ticket.sla_minutes_remaining}m</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
