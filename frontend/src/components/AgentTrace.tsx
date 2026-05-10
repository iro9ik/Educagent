"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  FileText,
  Loader2,
} from "lucide-react";
import { AgentStep } from "../lib/api";

interface AgentTraceProps {
  steps: AgentStep[];
  reasoning?: string;
  sources?: string[];
  isActive: boolean;
}

function CircularProgress({ progress }: { progress: number }) {
  const size = 16;
  const strokeWidth = 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative w-4 h-4 flex items-center justify-center">
      <svg className="absolute inset-0 w-4 h-4 transform -rotate-90">
        <circle
          cx="8"
          cy="8"
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="text-white/10"
        />
        <circle
          cx="8"
          cy="8"
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          style={{ strokeDashoffset: offset }}
          strokeLinecap="round"
          className="text-[var(--color-brand)] transition-all duration-300"
        />
      </svg>
      <FileText className="w-[7px] h-[7px] text-red-400" />
    </div>
  );
}

export default function AgentTrace({
  steps,
  reasoning = "",
  sources = [],
  isActive,
}: AgentTraceProps) {
  const [expanded, setExpanded] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (!isActive) return;
    const id = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(id);
  }, [isActive]);

  const elapsedMs = useMemo(() => {
    const startedAt = steps[0]?.startedAt;
    if (!startedAt) return 0;
    const completed = steps.reduce((sum, step) => sum + (step.duration_ms || 0), 0);
    return isActive ? (now || Date.now()) - startedAt : completed;
  }, [isActive, now, steps]);

  const hasRunningStep = steps.some((step) => step.status === "running");
  
  // Fake progress for the final streaming phase
  const streamProgress = useMemo(() => {
    if (!isActive || hasRunningStep) return 0;
    // Slow progress that caps at 95% until finished
    return Math.min(95, (elapsedMs / 15000) * 100);
  }, [isActive, hasRunningStep, elapsedMs]);

  const summary = hasRunningStep || isActive
    ? `Thinking... ${formatDuration(elapsedMs)}`
    : `Thought for ${formatDuration(elapsedMs)}`;

  if (steps.length === 0 && !reasoning && sources.length === 0 && !isActive) {
    return null;
  }

  return (
    <div className="mb-3 text-sm text-gray-300">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="group inline-flex items-center gap-2 rounded-md px-1 py-1 text-gray-400 hover:text-gray-100 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4" />
        ) : (
          <ChevronRight className="w-4 h-4" />
        )}
        
        {hasRunningStep ? (
          <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />
        ) : isActive ? (
          <CircularProgress progress={streamProgress} />
        ) : null}

        <span className={hasRunningStep || isActive ? "text-shimmer" : ""}>{summary}</span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-2 border-l border-white/10 pl-4">
          {steps.map((step) => (
            <div key={step.agent} className="trace-step-enter">
              <div className="flex items-center gap-2 text-gray-300">
                <StepIcon status={step.status} />
                <span className={step.status === "running" ? "text-shimmer" : ""}>
                  {step.label}
                </span>
                {step.duration_ms !== undefined && (
                  <span className="text-xs text-gray-500">
                    {formatDuration(step.duration_ms)}
                  </span>
                )}
              </div>
              {step.detail && (
                <div className="ml-6 mt-1 text-xs text-red-300">{step.detail}</div>
              )}
              {step.agent === "rag" && sources.length > 0 && (
                <div className="ml-6 mt-2 flex flex-wrap gap-2">
                  {sources.map((source) => (
                    <span
                      key={source}
                      className="inline-flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-gray-400"
                    >
                      <FileText className="w-3.5 h-3.5 text-red-300" />
                      {source}
                    </span>
                  ))}
                </div>
              )}
              {step.agent === "thinking" && reasoning && (
                <div className="ml-6 mt-2">
                  <button
                    type="button"
                    onClick={() => setReasoningOpen((value) => !value)}
                    className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-gray-100"
                  >
                    {reasoningOpen ? (
                      <ChevronDown className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5" />
                    )}
                    Show reasoning
                  </button>
                  {reasoningOpen && (
                    <div className="prose prose-invert prose-sm mt-2 max-w-none rounded-md border border-white/10 bg-black/20 p-3 text-gray-300">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {reasoning}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StepIcon({ status }: { status: AgentStep["status"] }) {
  if (status === "completed") {
    return <Check className="w-4 h-4 text-green-400" />;
  }

  if (status === "error") {
    return <AlertTriangle className="w-4 h-4 text-red-400" />;
  }

  return <Loader2 className="w-3.5 h-3.5 text-gray-400 animate-spin" />;
}

function formatDuration(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "0s";
  const seconds = ms / 1000;
  if (seconds < 10) return `${seconds.toFixed(1)}s`;
  return `${Math.round(seconds)}s`;
}
