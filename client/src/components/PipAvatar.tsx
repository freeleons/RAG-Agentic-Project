import React, { useState } from "react";

export type PipStatusState =
  | "idle"
  | "thinking"
  | "talking"
  | "explaining"
  | "needs_confirmation"
  | "completed"
  | "stopped"
  | "error"
  | "not_found";

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
      case "stopped":
        return [
          "Workflow halted on command! 🛑",
          "Request cancelled—standing by! ⏸️",
          "Ready whenever you want to try again! ⚡",
        ];
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

  // Proportional geometry dimensions for all sizes
  const sizeConfig = {
    xs: {
      outer: "w-7 h-7 rounded-lg text-[10px]",
      eye: "w-1.5 h-1.5",
      pupil: "w-1 h-1",
      mouthOpen: "w-2.5 h-1.5",
      mouthArc: "w-2.5 h-1",
      mouthStraight: "w-2 h-[2px]",
      earLeft: "w-1 h-2 -left-1",
      earRight: "w-1 h-2 -right-1",
      antennaOuter: "w-1.5 h-1.5",
      antennaInner: "w-0.5 h-1",
      spacing: "space-x-1",
      blush: "top-3 px-1",
      blushCircle: "w-1 h-0.5",
      eyebrow: "text-[8px]",
    },
    sm: {
      outer: "w-9 h-9 rounded-xl text-xs",
      eye: "w-2.5 h-2.5",
      pupil: "w-1 h-1",
      mouthOpen: "w-3 h-1.5",
      mouthArc: "w-3 h-1",
      mouthStraight: "w-2.5 h-[2px]",
      earLeft: "w-1 h-2.5 -left-1",
      earRight: "w-1 h-2.5 -right-1",
      antennaOuter: "w-2 h-2",
      antennaInner: "w-0.5 h-1.5",
      spacing: "space-x-1.5",
      blush: "top-4 px-1.5",
      blushCircle: "w-1.5 h-0.5",
      eyebrow: "text-[10px]",
    },
    md: {
      outer: "w-12 h-12 rounded-xl text-base",
      eye: "w-3 h-3",
      pupil: "w-1.5 h-1.5",
      mouthOpen: "w-4 h-2",
      mouthArc: "w-3.5 h-1.5",
      mouthStraight: "w-3 h-[2px]",
      earLeft: "w-1.5 h-3 -left-1.5",
      earRight: "w-1.5 h-3 -right-1.5",
      antennaOuter: "w-2.5 h-2.5",
      antennaInner: "w-1 h-2",
      spacing: "space-x-2.5",
      blush: "top-5 px-2",
      blushCircle: "w-2 h-1",
      eyebrow: "text-xs",
    },
    lg: {
      outer: "w-16 h-16 rounded-2xl text-lg",
      eye: "w-4 h-4",
      pupil: "w-2 h-2",
      mouthOpen: "w-5 h-2.5",
      mouthArc: "w-4 h-2",
      mouthStraight: "w-4 h-[3px]",
      earLeft: "w-2 h-4 -left-2",
      earRight: "w-2 h-4 -right-2",
      antennaOuter: "w-3 h-3",
      antennaInner: "w-1 h-2.5",
      spacing: "space-x-3",
      blush: "top-7 px-2.5",
      blushCircle: "w-3 h-1",
      eyebrow: "text-base",
    },
    xl: {
      outer: "w-24 h-24 text-2xl rounded-3xl",
      eye: "w-6 h-6",
      pupil: "w-3 h-3",
      mouthOpen: "w-8 h-4",
      mouthArc: "w-7 h-3",
      mouthStraight: "w-6 h-[4px]",
      earLeft: "w-2.5 h-6 -left-2.5",
      earRight: "w-2.5 h-6 -right-2.5",
      antennaOuter: "w-4 h-4",
      antennaInner: "w-1.5 h-3",
      spacing: "space-x-4",
      blush: "top-10 px-3.5",
      blushCircle: "w-4 h-1.5",
      eyebrow: "text-xl",
    },
  }[size];

  const glowClasses = {
    thinking: "shadow-cyan-500/40 border-cyan-300 animate-pulse",
    talking: "shadow-blue-500/30 border-blue-300",
    explaining: "shadow-indigo-500/40 border-indigo-300",
    needs_confirmation: "shadow-amber-500/50 border-amber-300 animate-bounce",
    completed: "shadow-emerald-500/40 border-emerald-300",
    stopped: "shadow-slate-500/40 border-slate-400",
    error: "shadow-rose-500/40 border-rose-300",
    not_found: "shadow-rose-500/40 border-rose-300",
    idle: "shadow-blue-500/20 border-blue-400/80 hover:border-cyan-300 transition-all",
  }[status];

  const bgGradient = {
    thinking: "from-cyan-600 via-blue-600 to-indigo-700",
    talking: "from-blue-600 via-indigo-600 to-cyan-500",
    explaining: "from-indigo-600 via-blue-600 to-cyan-500",
    needs_confirmation: "from-amber-600 via-orange-600 to-amber-700",
    completed: "from-emerald-600 via-teal-600 to-emerald-700",
    stopped: "from-slate-600 via-slate-700 to-slate-800",
    error: "from-rose-600 via-red-600 to-rose-800",
    not_found: "from-rose-600 via-red-600 to-rose-800",
    idle: "from-blue-600 via-indigo-600 to-cyan-500",
  }[status];

  return (
    <div
      className="relative inline-block cursor-pointer select-none group"
      onClick={handlePipClick}
      title="Click Pip to see his response!"
    >
      {/* Celebration Stars Popup */}
      {status === "completed" && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 flex space-x-1 animate-bounce z-40 pointer-events-none">
          <span className="text-xs">✨</span>
          <span className="text-xs">✨</span>
        </div>
      )}

      {/* Stop / Halt Indicator Badge */}
      {status === "stopped" && (
        <div className="absolute -top-6 left-1/2 -translate-x-1/2 z-40 text-xs font-bold bg-slate-800 text-slate-200 border border-slate-600 rounded-full px-2 py-0.5 shadow-md flex items-center space-x-1">
          <span>⏹️</span>
          <span className="text-[10px]">Stopped</span>
        </div>
      )}

      {/* Question Mark Popup for Error / Not Found */}
      {(status === "error" || status === "not_found") && (
        <div className="absolute -top-6 right-0 z-40 animate-pulse text-xs font-bold bg-amber-400 text-slate-900 rounded-full w-4 h-4 flex items-center justify-center shadow-xs">
          ❓
        </div>
      )}

      {/* Speech Bubble Popup */}
      {speechBubble && (
        <div className="absolute top-full mt-2.5 left-1/2 -translate-x-1/2 z-50 bg-slate-900/95 dark:bg-slate-800 text-white text-[11px] font-bold px-3.5 py-1.5 rounded-full shadow-2xl border border-blue-400/60 whitespace-nowrap animate-fadeIn flex items-center space-x-1.5 pointer-events-none">
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-slate-900 dark:bg-slate-800 border-l border-t border-blue-400/60 rotate-45"></div>
          <span>🤖</span>
          <span>{speechBubble}</span>
        </div>
      )}

      {/* Main Square Robot Avatar Shell */}
      <div
        className={`relative ${sizeConfig.outer} bg-gradient-to-tr ${bgGradient} border-2 ${glowClasses} flex items-center justify-center text-white font-bold shadow-md transition-all group-hover:rotate-2 active:scale-95`}
      >
        {/* Side Ear Bolts */}
        <span
          className={`absolute ${sizeConfig.earLeft} top-1/2 -translate-y-1/2 bg-blue-400/80 rounded-l-md border-y border-l border-white/40`}
        ></span>
        <span
          className={`absolute ${sizeConfig.earRight} top-1/2 -translate-y-1/2 bg-blue-400/80 rounded-r-md border-y border-r border-white/40`}
        ></span>

        {/* Antenna Light Bulb */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full flex flex-col items-center">
          <span
            className={`rounded-full border border-white/60 shadow-xs ${sizeConfig.antennaOuter} ${status === "thinking"
                ? "bg-cyan-300 animate-ping"
                : status === "needs_confirmation" || status === "explaining"
                  ? "bg-amber-300 animate-pulse"
                  : status === "completed"
                    ? "bg-emerald-300 animate-bounce"
                    : status === "stopped"
                      ? "bg-slate-400"
                      : status === "error" || status === "not_found"
                        ? "bg-rose-400 animate-pulse"
                        : "bg-cyan-300 animate-pulse"
              }`}
          ></span>
          <span className={`${sizeConfig.antennaInner} bg-slate-400 rounded-t`}></span>
        </div>

        {/* Face Expressions */}
        <div className="flex flex-col items-center justify-center space-y-1 w-full h-full relative">
          {/* Blush Cheeks */}
          <div className={`absolute w-full flex justify-between pointer-events-none ${sizeConfig.blush}`}>
            <span className={`${sizeConfig.blushCircle} rounded-full bg-pink-300/60 blur-[0.5px]`}></span>
            <span className={`${sizeConfig.blushCircle} rounded-full bg-pink-300/60 blur-[0.5px]`}></span>
          </div>

          {/* Eyes Row */}
          <div className={`flex items-center ${sizeConfig.spacing} z-10`}>
            {status === "thinking" ? (
              /* 1. THINKING: Scanning Laser Eyes */
              <>
                <div className={`${sizeConfig.eye} rounded-full bg-cyan-200 animate-ping`}></div>
                <div className={`${sizeConfig.eye} rounded-full bg-cyan-200 animate-ping`}></div>
              </>
            ) : status === "completed" || isBigSmile ? (
              /* 2. CELEBRATION / BIG SMILE: Happy Arc Eyes (^‿^) */
              <>
                <span className={`text-white font-bold font-mono tracking-tighter ${sizeConfig.eyebrow}`}>^</span>
                <span className={`text-white font-bold font-mono tracking-tighter ${sizeConfig.eyebrow}`}>^</span>
              </>
            ) : status === "stopped" ? (
              /* 3. STOPPED: Neutral Flat Line Eyes (-_-) */
              <>
                <div className={`${sizeConfig.mouthStraight} bg-white rounded-full`}></div>
                <div className={`${sizeConfig.mouthStraight} bg-white rounded-full`}></div>
              </>
            ) : status === "explaining" || status === "needs_confirmation" ? (
              /* 4. EXPLAINING: Wide Animated Pupil Eyes */
              <>
                <div className={`${sizeConfig.eye} rounded-full bg-white flex items-center justify-center`}>
                  <div className={`${sizeConfig.pupil} rounded-full bg-slate-900 animate-pulse`}></div>
                </div>
                <div className={`${sizeConfig.eye} rounded-full bg-white flex items-center justify-center`}>
                  <div className={`${sizeConfig.pupil} rounded-full bg-slate-900 animate-pulse`}></div>
                </div>
              </>
            ) : status === "error" || status === "not_found" ? (
              /* 5. PUZZLED / ERROR: One Raised Eyebrow (•_o) */
              <>
                <div className={`${sizeConfig.eye} rounded-full bg-white flex items-center justify-center`}>
                  <div className={`${sizeConfig.pupil} rounded-full bg-slate-900`}></div>
                </div>
                <span className={`text-white font-bold font-mono ${sizeConfig.eyebrow}`}>o</span>
              </>
            ) : (
              /* 6. DEFAULT / IDLE & TALKING: Kawaii Sparkle Eyes */
              <>
                <div className={`${sizeConfig.eye} rounded-full bg-white flex items-center justify-center shadow-xs`}>
                  <div className={`${sizeConfig.pupil} rounded-full bg-slate-900 relative`}>
                    <span className="absolute -top-0.5 -right-0.5 w-1 h-1 bg-white rounded-full"></span>
                  </div>
                </div>
                <div className={`${sizeConfig.eye} rounded-full bg-white flex items-center justify-center shadow-xs`}>
                  <div className={`${sizeConfig.pupil} rounded-full bg-slate-900 relative`}>
                    <span className="absolute -top-0.5 -right-0.5 w-1 h-1 bg-white rounded-full"></span>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Mouth Line */}
          <div className="z-10">
            {isBigSmile || status === "completed" ? (
              /* Big Happy Open Smile */
              <div className={`${sizeConfig.mouthOpen} bg-white rounded-b-full shadow-xs`}></div>
            ) : status === "thinking" ? (
              /* Animated Wave Dots [ • • • ] */
              <div className="flex space-x-0.5">
                <span className="w-1 h-1 rounded-full bg-white animate-bounce"></span>
                <span className="w-1 h-1 rounded-full bg-white animate-bounce delay-100"></span>
                <span className="w-1 h-1 rounded-full bg-white animate-bounce delay-200"></span>
              </div>
            ) : status === "talking" ? (
              /* Talking Happy Open Mouth */
              <div className={`${sizeConfig.mouthOpen} bg-white rounded-b-full animate-pulse shadow-xs`}></div>
            ) : status === "stopped" ? (
              /* Neutral Straight Mouth (-) */
              <div className={`${sizeConfig.mouthStraight} bg-white rounded-full`}></div>
            ) : status === "explaining" || status === "needs_confirmation" ? (
              /* Open Speech Oval Mouth */
              <div className={`${sizeConfig.mouthOpen} rounded-full bg-white`}></div>
            ) : status === "error" || status === "not_found" ? (
              /* Puzzled Wavy Mouth ( ~ ) */
              <div className={`${sizeConfig.mouthArc} border-b-2 border-dashed border-white`}></div>
            ) : (
              /* Default Cute Smile Arc */
              <div className={`${sizeConfig.mouthArc} border-b-2 border-white rounded-b-full`}></div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};