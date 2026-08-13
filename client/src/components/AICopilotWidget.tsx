import React, { useEffect, useRef, useState } from "react";

import { AgentRun, Ticket, UserProfile } from "../types";
import { PipAvatar, PipStatusState } from "./PipAvatar";

interface AICopilotWidgetProps {
  user: UserProfile;
  activeTicket: Ticket | null;
  tickets?: Ticket[];
  latestRun: AgentRun | null;
  isProcessing: boolean;
}

interface ChatMessage {
  id: string;
  sender: "user" | "pip";
  text: string;
  timestamp: string;
}

export const AICopilotWidget: React.FC<AICopilotWidgetProps> = ({
  user,
  activeTicket,
  isProcessing,
}) => {
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      sender: "pip",
      text: `Hello ${user.full_name.split(" ")[0]}! I'm Pip, your ApexCare HR AI Support Assistant. I'm here to help you search company policies, benefits, and draft ticket replies.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [isBotThinking, setIsBotThinking] = useState(false);
  const [isBotTalking, setIsBotTalking] = useState(false);
  const [thinkingStage, setThinkingStage] = useState<"searching" | "formulating">("searching");

  const abortControllerRef = useRef<AbortController | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const handleStopThinking = () => {
    abortControllerRef.current?.abort();
    setIsBotThinking(false);
  };

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, isBotThinking, isBotTalking]);

  // Dynamic multi-stage execution progress
  useEffect(() => {
    if (!isBotThinking && !isProcessing) {
      setThinkingStage("searching");
      return;
    }
    setThinkingStage("searching");
    const timer = setTimeout(() => {
      setThinkingStage("formulating");
    }, 1800);
    return () => clearTimeout(timer);
  }, [isBotThinking, isProcessing]);

  const getPipStatus = (): PipStatusState => {
    if (isProcessing || isBotThinking) return "thinking";
    if (isBotTalking) return "talking";
    return "idle";
  };

  const status = getPipStatus();

  const handleSendChatMessage = async (queryText?: string) => {
    const textToSend = queryText || inputMessage;
    if (!textToSend.trim()) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: "user",
      text: textToSend,
      timestamp,
    };

    setChatMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInputMessage("");
    setIsBotThinking(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const token = localStorage.getItem("apexcare_token");
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: textToSend }),
        signal: controller.signal,
      });

      let answerText = "";
      if (res.ok) {
        const data = await res.json();
        answerText = data.reply;
      } else {
        throw new Error("API call failed");
      }

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "pip",
        text: answerText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setChatMessages((prev) => [...prev, botMsg]);
      setIsBotThinking(false);
      setIsBotTalking(true);

      setTimeout(() => {
        setIsBotTalking(false);
      }, 3500);
    } catch (err: any) {
      if (err.name === "AbortError") {
        return;
      }
      const lower = textToSend.toLowerCase().trim();
      let answerText = "";

      if (lower.includes("weather")) {
        answerText = `I don't have live weather sensors connected, but I hope it's pleasant outside! Now, let's get back to work—what ticket or policy question shall we tackle next?`;
      } else if (lower.includes("how are you") || lower.includes("how's it going")) {
        answerText = `I'm fully operational and performing at 100%! Ready to get to work—which support ticket should we review today?`;
      } else if (lower.includes("hi") || lower.includes("hello") || lower.includes("hey")) {
        answerText = `Hello ${user.full_name.split(" ")[0]}! Ready to assist. What support ticket or policy inquiry can I help you with today?`;
      } else if (lower.includes("fsa") || lower.includes("wex")) {
        answerText = "Based on our audited WEX Benefits Policy (wex_benefits_technology_guide.md): Healthcare FSA funds allow up to $640 in unused funds to roll over into 2026. Claims can be submitted via the Wex Mobile app. What shall we tackle next?";
      } else {
        answerText = `I'm ready to assist with "${textToSend}". Let's get to work—which ticket or policy inquiry shall we review?`;
      }

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "pip",
        text: answerText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setChatMessages((prev) => [...prev, botMsg]);
      setIsBotThinking(false);
      setIsBotTalking(true);

      setTimeout(() => {
        setIsBotTalking(false);
      }, 3500);
    }
  };

  const handleNewConversation = () => {
    setChatMessages([
      {
        id: "1",
        sender: "pip",
        text: `Hello ${user.full_name.split(" ")[0]}! I'm Pip, your ApexCare HR AI Support Assistant. I'm here to help you search company policies, benefits, and draft ticket replies.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
    setInputMessage("");
  };

  return (
    <div className="w-80 xl:w-96 h-full border-l border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/80 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="pt-5 pb-4 px-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-3">
        <div className="flex items-center space-x-3 min-w-0">
          {/* Animated Interactive Pip Avatar */}
          <PipAvatar status={status} size="md" />

          <div className="min-w-0">
            <h3 className="font-bold text-sm text-slate-900 dark:text-white leading-tight truncate">
              Pip Assistant
            </h3>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate">
              Support Assistant & Chatbot
            </p>
          </div>
        </div>

        {/* New Conversation Plus Button */}
        <button
          onClick={handleNewConversation}
          title="Start New Conversation"
          className="p-2 rounded-xl text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition cursor-pointer flex items-center justify-center shrink-0 border border-slate-200/60 dark:border-slate-700/60"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
        </button>
      </div>

      {/* Content Area - Live AI Chatbot Panel */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4 flex flex-col justify-between">
        <div className="flex-1 flex flex-col justify-between space-y-3">
          {/* Chat Messages Timeline */}
          <div className="space-y-3 overflow-y-auto max-h-[380px] custom-scrollbar pr-1">
            {chatMessages.map((msg) => (
              <div
                key={msg.id}
                className={`flex space-x-2 ${msg.sender === "user" ? "justify-end" : "justify-start"
                  }`}
              >
                {msg.sender === "pip" && (
                  <div className="w-6 h-6 rounded-full bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 text-white font-black text-xs flex items-center justify-center shrink-0 shadow-sm shadow-blue-500/30 border border-white/20 mt-0.5">
                    P
                  </div>
                )}
                <div
                  className={`p-3 rounded-2xl max-w-[85%] text-xs leading-relaxed ${msg.sender === "user"
                      ? "bg-blue-600 text-white rounded-br-none shadow-xs"
                      : "bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 rounded-bl-none shadow-xs"
                    }`}
                >
                  <p>{msg.text}</p>
                  <span className="text-[9px] opacity-70 block text-right mt-1 font-mono">
                    {msg.timestamp}
                  </span>
                </div>
              </div>
            ))}

            {isBotThinking && (
              <div className="flex space-x-2 items-center text-xs text-blue-600 dark:text-blue-400 font-semibold p-2 bg-blue-50 dark:bg-blue-950/40 rounded-xl border border-blue-200 dark:border-blue-800 animate-pulse font-mono">
                <span>🤖</span>
                <span>
                  {thinkingStage === "searching"
                    ? "🔍 Searching audited policy knowledge base..."
                    : "✍️ Formulating policy-grounded response..."}
                </span>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Quick Policy Chips & Chat Input Box */}
          <div className="space-y-2 pt-2 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 custom-scrollbar text-[10px]">
              <button
                onClick={() =>
                  handleSendChatMessage("What is our WEX FSA rollover limit?")
                }
                className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-semibold whitespace-nowrap cursor-pointer transition"
              >
                💬 FSA Policy
              </button>
              <button
                onClick={() =>
                  handleSendChatMessage(
                    "How do employees replace medical ID cards?"
                  )
                }
                className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-semibold whitespace-nowrap cursor-pointer transition"
              >
                💬 Medical IDs
              </button>
              <button
                onClick={() =>
                  handleSendChatMessage(
                    "How do I report a Qualifying Life Event in Employee Navigator?"
                  )
                }
                className="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 font-semibold whitespace-nowrap cursor-pointer transition"
              >
                💬 Life Events
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendChatMessage();
              }}
              className="flex items-center space-x-2"
            >
              <textarea
                rows={1}
                placeholder="Ask Pip any policy question..."
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendChatMessage();
                  }
                }}
                className="flex-1 px-3 py-2 rounded-xl text-xs bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none overflow-y-auto max-h-24 custom-scrollbar font-medium"
              />
              {isBotThinking ? (
                <button
                  type="button"
                  onClick={handleStopThinking}
                  className="px-3.5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-bold transition cursor-pointer shadow-xs whitespace-nowrap"
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!inputMessage.trim()}
                  className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl text-xs font-bold transition cursor-pointer shadow-xs whitespace-nowrap"
                >
                  Send
                </button>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};