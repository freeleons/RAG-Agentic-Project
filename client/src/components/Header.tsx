import React from "react";
import { UserProfile } from "../types";

interface HeaderProps {
  user: UserProfile;
  activeView: "workbench" | "observability" | "knowledge";
  setActiveView: (view: "workbench" | "observability" | "knowledge") => void;
  darkMode: boolean;
  setDarkMode: (val: boolean) => void;
  onLogout: () => void;
  onReseed: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  user,
  activeView,
  setActiveView,
  darkMode,
  setDarkMode,
  onLogout,
  onReseed,
}) => {
  return (
    <header className="sticky top-0 z-40 px-6 py-3 flex items-center justify-between bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 shadow-xs transition-colors duration-200">
      {/* Brand & Organization */}
      <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveView("workbench")}>
        <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-cyan-500 flex items-center justify-center text-white font-bold shadow-md shadow-blue-500/20">
          ⚡
        </div>
        <div className="flex items-center space-x-2">
          <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-white">ApexCare</span>
          <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-700 dark:text-blue-400 border border-blue-500/20">
            HR Support Triage
          </span>
        </div>
      </div>

      {/* Center Navigation Tabs */}
      <div className="flex items-center space-x-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl border border-slate-200 dark:border-slate-700">
        <button
          onClick={() => setActiveView("workbench")}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${activeView === "workbench"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
        >
          Workbench
        </button>
        <button
          onClick={() => setActiveView("knowledge")}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${activeView === "knowledge"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
        >
          Knowledge Base
        </button>
        <button
          onClick={() => setActiveView("observability")}
          className={`px-4 py-1.5 rounded-lg text-xs font-bold transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${activeView === "observability"
              ? "bg-blue-600 text-white shadow-sm"
              : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
            }`}
        >
          Audit Logs
        </button>
      </div>

      {/* Right User Identity & Actions */}
      <div className="flex items-center space-x-3">
        {/* Quick Reseed Button */}
        <button
          onClick={onReseed}
          title="Clear all audit logs, conversations, and reset sample tickets"
          className="px-3 py-1.5 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 text-xs font-bold transition cursor-pointer border border-slate-200 dark:border-slate-700 flex items-center space-x-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <span>🔄</span>
          <span>Reset & Reseed</span>
        </button>

        {/* Dark/Light Mode Toggle */}
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="p-1.5 rounded-lg text-slate-700 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 transition cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
          title="Toggle Theme"
        >
          {darkMode ? "☀️" : "🌙"}
        </button>

        {/* Specialist Profile Badge */}
        <div className="flex items-center space-x-2 pl-2 border-l border-slate-200 dark:border-slate-700">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-bold text-xs flex items-center justify-center shadow-xs">
            {user.full_name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .toUpperCase()}
          </div>
          <span className="text-xs font-bold text-slate-900 dark:text-white">{user.full_name.split(" ")[0]}</span>
        </div>

        {/* Logout */}
        <button
          onClick={onLogout}
          className="text-xs font-semibold text-rose-600 dark:text-rose-400 hover:underline cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Logout
        </button>
      </div>
    </header>
  );
};

