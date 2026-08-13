import React, { useEffect, useState } from "react";
import { PipAvatar, PipStatusState } from "./PipAvatar";

interface PipOnboardingModalProps {
  userName: string;
  onComplete: () => void;
}

export const PipOnboardingModal: React.FC<PipOnboardingModalProps> = ({
  userName,
  onComplete,
}) => {
  const [step, setStep] = useState(0);

  const steps: Array<{
    title: string;
    subtitle: string;
    pipStatus: PipStatusState;
    highlights: Array<{ icon: string; title: string; desc: string }>;
    btnText: string;
  }> = [
      {
        title: `Welcome, ${userName.split(" ")[0]}! ⚡`,
        subtitle: "Meet Pip • AI Support Triage Assistant",
        pipStatus: "idle",
        highlights: [
          {
            icon: "🤖",
            title: "Instant Policy Triage",
            desc: "Turns complex employee inquiries into accurate draft replies in seconds.",
          },
          {
            icon: "⚡",
            title: "Zero Friction",
            desc: "One-click execution powered by audited RAG vector search.",
          },
        ],
        btnText: "Show Me the Magic ✨",
      },
      {
        title: "One-Click AI Triage 🚀",
        subtitle: "Autonomous RAG & Tool Execution",
        pipStatus: "thinking", // 👈 Pip scans & thinks in Step 2!
        highlights: [
          {
            icon: "📄",
            title: "Audited Knowledge",
            desc: "Pip checks official company policy documents in real-time.",
          },
          {
            icon: "✍️",
            title: "Human Specialist Review",
            desc: "Inspect, edit, or dispatch drafts directly from the workbench.",
          },
        ],
        btnText: "Ooh, Smart! What Else? 💡",
      },
      {
        title: "Full System Receipts 📊",
        subtitle: "Engineered for Complete Transparency",
        pipStatus: "completed", // 👈 Pip celebrates success in Step 3!
        highlights: [
          {
            icon: "🔍",
            title: "Step-by-Step Traces",
            desc: "Inspect tool execution arguments, LLM reasoning, and payloads.",
          },
          {
            icon: "📈",
            title: "Live Observability",
            desc: "Track token consumption, success rates, and tool latency metrics.",
          },
        ],
        btnText: "Let's Triage! 🎉",
      },
    ];

  const current = steps[step];

  const handleNext = () => {
    if (step < steps.length - 1) {
      setStep(step + 1);
    } else {
      onComplete();
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onComplete();
      } else if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        handleNext();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [step]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 dark:bg-slate-950/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-white dark:bg-slate-900 w-full max-w-lg p-7 rounded-3xl border-2 border-blue-500/30 shadow-2xl space-y-6 text-center relative overflow-hidden">
        {/* Ambient Background Glow */}
        <div className="absolute -top-12 -left-12 w-36 h-36 bg-blue-500/15 rounded-full blur-2xl pointer-events-none"></div>
        <div className="absolute -bottom-12 -right-12 w-36 h-36 bg-cyan-500/15 rounded-full blur-2xl pointer-events-none"></div>

        {/* Step Indicators */}
        <div className="flex justify-center items-center space-x-2 pt-1">
          {steps.map((_, idx) => (
            <span
              key={idx}
              className={`h-2 rounded-full transition-all duration-300 ${idx === step
                  ? "w-8 bg-blue-600 dark:bg-blue-400"
                  : "w-2 bg-slate-200 dark:bg-slate-700"
                }`}
            />
          ))}
        </div>

        {/* Pip Avatar Header — Updates status dynamically per step! */}
        <div className="flex justify-center items-center py-2">
          <PipAvatar showSpeechOnClick={false} size="lg" status={current.pipStatus} />
        </div>

        {/* Header Titles */}
        <div className="space-y-1">
          <span className="text-xs font-black uppercase tracking-widest text-blue-600 dark:text-blue-400">
            {current.subtitle}
          </span>
          <h3 className="text-2xl font-black text-slate-900 dark:text-white leading-tight">
            {current.title}
          </h3>
        </div>

        {/* Bullet List Container */}
        <div className="space-y-3 text-left bg-slate-50 dark:bg-slate-800/60 p-4 rounded-2xl border border-slate-200/80 dark:border-slate-700/60">
          {current.highlights.map((h, i) => (
            <div key={i} className="flex items-start space-x-3">
              <span className="text-xl shrink-0 leading-none mt-0.5">{h.icon}</span>
              <div className="text-sm leading-relaxed">
                <span className="font-extrabold text-slate-900 dark:text-white">{h.title}: </span>
                <span className="text-slate-700 dark:text-slate-300 font-medium">{h.desc}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="pt-2 flex items-center justify-between gap-4">
          <button
            onClick={onComplete}
            className="text-sm font-bold text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition cursor-pointer px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-slate-400 rounded-xl"
          >
            Skip Tour
          </button>
          <button
            onClick={handleNext}
            className="flex-1 py-3 px-5 bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-500 hover:opacity-95 text-white rounded-2xl text-sm font-black transition shadow-lg shadow-blue-500/25 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {current.btnText}
          </button>
        </div>
      </div>
    </div>
  );
};