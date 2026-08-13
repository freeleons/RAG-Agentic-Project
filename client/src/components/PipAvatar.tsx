import React, { useState } from "react";

export type PipStatusState = "idle" | "thinking" | "talking" | "explaining" | "needs_confirmation" | "completed" | "declined" | "error" | "not_found";

interface PipAvatarProps {
  status?: PipStatusState;
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  showSpeechOnClick?: boolean;
}

export const PipAvatar: React.FC<PipAvatarProps> = ({
  status = "idle",
  size = "md",
  showSpeechOnClick = true,
}) => {
  const [speechBubble, setSpeechBubble] = useState<string | null>(null);
  const [isBigSmile, setIsBigSmile] = useState(false);

  const getStatusQuotes = () => {
    switch (status) {
      case "thinking":
        return [
          "Searching audited company policies... 🔍",
          "Reading RAG Knowledge Store... ⚡",
          "Connecting vector embeddings... 🧠",
        ];
      case "talking":
        return [
          "Here is what I found in our policy documents! 💬",
          "Let me explain this for you! 💡",
          "Check out this answer! 🚀",
        ];
      case "explaining":
      case "needs_confirmation":
        return [
          "Check out my proposed draft reply! 💡",
          "Option D human approval gate active! 🛡️",
          "Review text before sending to employee! ✍️",
        ];
      case "completed":
        return [
          "Yay! Reply dispatched successfully! ✨",
          "Ticket updated and resolved! 🌟",
          "High-five! Another employee helped! 🖐️",
        ];
      case "declined":
      case "error":
      case "not_found":
        return [
          "Hmm, couldn't find a policy match for this! ❓",
          "I'm not 100% sure, so I escalated to Tier-2! 🎒",
          "Puzzled... let's review this together! 🧐",
        ];
      default:
        return [
          "Ready to help you triage tickets! (◠‿◠)✨",
          "Pip is super happy to assist today! 💖",
          "Select any employee ticket to get started! 🎧",
        ];
    }
  };

  const handlePipClick = () => {
    setIsBigSmile(true);
    if (showSpeechOnClick) {
      const quotes = getStatusQuotes();
      const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];
      setSpeechBubble(randomQuote);
    }

    setTimeout(() => {
      setIsBigSmile(false);
      setSpeechBubble(null);
    }, 3000);
  };

  // Dimensions based on size prop
  const sizeClasses = {
    xs: "w-7 h-7 text-[10px]",
    sm: "w-9 h-9 text-xs",
    md: "w-12 h-12 text-base",
    lg: "w-20 h-20 text-xl",
    xl: "w-28 h-28 text-3xl",
  }[size];

  // Status Glow & Border
  const glowClasses = {
    thinking: "shadow-cyan-500/40 border-cyan-300 animate-pulse",
    talking: "shadow-blue-500/30 border-blue-300",
    explaining: "shadow-indigo-500/40 border-indigo-300",
    needs_confirmation: "shadow-amber-500/50 border-amber-300 animate-bounce",
    completed: "shadow-emerald-500/40 border-emerald-300",
    declined: "shadow-rose-500/40 border-rose-300",
    error: "shadow-rose-500/40 border-rose-300",
    not_found: "shadow-rose-500/40 border-rose-300",
    idle: "shadow-blue-500/20 border-blue-400/80 hover:border-cyan-300 transition-all",
  }[status];

  // Status Background Gradient
  const bgGradient = {
    thinking: "from-cyan-600 via-blue-600 to-indigo-700",
    talking: "from-blue-600 via-indigo-600 to-cyan-500",
    explaining: "from-indigo-600 via-blue-600 to-cyan-500",
    needs_confirmation: "from-amber-600 via-orange-600 to-amber-700",
    completed: "from-emerald-600 via-teal-600 to-emerald-700",
    declined: "from-rose-600 via-red-600 to-rose-800",
    error: "from-rose-600 via-red-600 to-rose-800",
    not_found: "from-rose-600 via-red-600 to-rose-800",
    idle: "from-blue-600 via-indigo-600 to-cyan-500",
  }[status];

  return (
    <div className="relative inline-block cursor-pointer select-none group" onClick={handlePipClick} title="Click Pip to see his response!">
      {/* Celebration Stars Popup for Completed State */}
      {status === "completed" && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 flex space-x-1 animate-bounce z-40 pointer-events-none">
          <span className="text-xs">✨</span>
          <span className="text-xs">✨</span>
        </div>
      )}

      {/* Puzzled Question Mark Popup for Not Found / Error */}
      {(status === "error" || status === "not_found" || status === "declined") && (
        <div className="absolute -top-6 right-0 z-40 animate-pulse text-xs font-bold bg-amber-400 text-slate-900 rounded-full w-4 h-4 flex items-center justify-center shadow-xs">
          ❓
        </div>
      )}

      {/* Speech Bubble Popup (Sleek floating pill badge centered cleanly under Pip) */}
      {speechBubble && (
        <div className="absolute top-full mt-2.5 left-1/2 -translate-x-1/2 z-50 bg-slate-900/95 dark:bg-slate-800 text-white text-[11px] font-bold px-3.5 py-1.5 rounded-full shadow-2xl border border-blue-400/60 whitespace-nowrap animate-fadeIn flex items-center space-x-1.5 pointer-events-none">
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-900 dark:bg-slate-800 border-l border-t border-blue-400/60 rotate-45"></div>
          <span>🤖</span>
          <span>{speechBubble}</span>
        </div>
      )}

      {/* Main Square Robot Avatar Shell */}
      <div className={`relative ${sizeClasses} rounded-xl bg-gradient-to-tr ${bgGradient} border-2 ${glowClasses} flex items-center justify-center text-white font-bold shadow-md transition-all group-hover:rotate-2 active:scale-95`}>

        {/* Cute Side Ear Bolts */}
        <span className="absolute -left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-3 bg-blue-400/80 rounded-l-md border-y border-l border-white/40"></span>
        <span className="absolute -right-1.5 top-1/2 -translate-y-1/2 w-1.5 h-3 bg-blue-400/80 rounded-r-md border-y border-r border-white/40"></span>

        {/* Antenna Light Bulb */}
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 flex flex-col items-center">
          <span className={`w-2.5 h-2.5 rounded-full border border-white/60 shadow-xs ${status === "thinking"
              ? "bg-cyan-300 animate-ping"
              : status === "needs_confirmation" || status === "explaining"
                ? "bg-amber-300 animate-pulse"
                : status === "completed"
                  ? "bg-emerald-300 animate-bounce"
                  : status === "error" || status === "not_found"
                    ? "bg-rose-400 animate-pulse"
                    : "bg-cyan-300 animate-pulse"
            }`}></span>
          <span className="w-1 h-2 bg-slate-400 rounded-t"></span>
        </div>

        {/* Square Robot Face Expressions */}
        <div className="flex flex-col items-center justify-center space-y-0.5 w-full h-full p-1 relative">

          {/* Cute Rosy Blush Cheeks */}
          <div className="absolute w-full px-2 flex justify-between top-5 pointer-events-none">
            <span className="w-2 h-1 rounded-full bg-pink-300/60 blur-[0.5px]"></span>
            <span className="w-2 h-1 rounded-full bg-pink-300/60 blur-[0.5px]"></span>
          </div>

          {/* Eyes Row */}
          <div className="flex items-center space-x-2.5 z-10">
            {status === "thinking" ? (
              /* 1. THINKING: Scanning Laser Eyes */
              <>
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-200 animate-ping"></div>
                <div className="w-2.5 h-2.5 rounded-full bg-cyan-200 animate-ping"></div>
              </>
            ) : status === "completed" || isBigSmile ? (
              /* 2. CELEBRATION / BIG SMILE: Happy Arc Eyes (^‿^) */
              <>
                <span className="text-white font-bold text-sm font-mono tracking-tighter">^</span>
                <span className="text-white font-bold text-sm font-mono tracking-tighter">^</span>
              </>
            ) : status === "explaining" || status === "needs_confirmation" ? (
              /* 3. EXPLAINING / REVIEW: Wide Animated Eyes */
              <>
                <div className="w-3 h-3 rounded-full bg-white flex items-center justify-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-900 animate-pulse"></div>
                </div>
                <div className="w-3 h-3 rounded-full bg-white flex items-center justify-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-900 animate-pulse"></div>
                </div>
              </>
            ) : status === "declined" || status === "error" || status === "not_found" ? (
              /* 4. CAN'T FIND / PUZZLED: One Raised Eyebrow (•_o) */
              <>
                <div className="w-2.5 h-2.5 rounded-full bg-white flex items-center justify-center">
                  <div className="w-1 h-1 rounded-full bg-slate-900"></div>
                </div>
                <span className="text-white font-bold text-xs font-mono">o</span>
              </>
            ) : (
              /* 5. DEFAULT / IDLE & TALKING: Kawaii Sparkle Eyes */
              <>
                <div className="w-3 h-3 rounded-full bg-white flex items-center justify-center shadow-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-900 relative">
                    <span className="absolute -top-0.5 -right-0.5 w-0.5 h-0.5 bg-white rounded-full"></span>
                  </div>
                </div>
                <div className="w-3 h-3 rounded-full bg-white flex items-center justify-center shadow-xs">
                  <div className="w-1.5 h-1.5 rounded-full bg-slate-900 relative">
                    <span className="absolute -top-0.5 -right-0.5 w-0.5 h-0.5 bg-white rounded-full"></span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Mouth Line */}
          <div className="z-10 pt-0.5">
            {isBigSmile || status === "completed" ? (
              /* Big Open Happy Smile */
              <div className="w-4 h-2 bg-white rounded-b-full shadow-xs"></div>
            ) : status === "thinking" ? (
              /* Animated Wave Mouth Dots [ • • • ] */
              <div className="flex space-x-0.5">
                <span className="w-1 h-1 rounded-full bg-white animate-bounce"></span>
                <span className="w-1 h-1 rounded-full bg-white animate-bounce delay-100"></span>
                <span className="w-1 h-1 rounded-full bg-white animate-bounce delay-200"></span>
              </div>
            ) : status === "talking" ? (
              /* Happy Open Smile Talking Mouth */
              <div className="w-3.5 h-2 bg-white rounded-b-full animate-pulse shadow-xs"></div>
            ) : status === "explaining" || status === "needs_confirmation" ? (
              /* Explaining Open Speech Mouth */
              <div className="w-3.5 h-1.5 rounded-full bg-white"></div>
            ) : status === "declined" || status === "error" || status === "not_found" ? (
              /* Puzzled Wavy Mouth ( ~ ) */
              <div className="w-3.5 h-1 border-b-2 border-dashed border-white"></div>
            ) : (
              /* Cute Joyful Smile Arc */
              <div className="w-3.5 h-1 border-b-2 border-white rounded-b-full"></div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
