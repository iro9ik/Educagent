"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Square, ChevronDown, ChevronRight, HelpCircle, Loader2 } from "lucide-react";
import AgentTrace from "./AgentTrace";
import { AgentStep } from "../lib/api";

interface MessageItem {
  id?: string;
  role: "user" | "assistant";
  content: string;
  status?: string;
  generation_id?: string | null;
  agentSteps?: AgentStep[];
  reasoning?: string;
  sources?: string[];
  attachedFiles?: string[];
}

interface ChatAreaProps {
  messages: MessageItem[];
  isStreaming: boolean;
  activeGenerationId: string | null;
  onStopGeneration: () => void;
}

export default function ChatArea({
  messages,
  isStreaming,
  activeGenerationId,
  onStopGeneration,
}: ChatAreaProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const userScrolledUp = useRef(false);

  useEffect(() => {
    if (!userScrolledUp.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isStreaming]);

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    userScrolledUp.current = distanceFromBottom > 100;
  };

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-4">
        <h1 className="text-3xl font-semibold mb-8 text-center text-[var(--color-foreground)]">
          What do you want to learn today?
        </h1>
      </div>
    );
  }

  const visibleMessages = messages.filter(
    (msg) =>
      msg.role === "user" ||
      msg.content.length > 0 ||
      (msg.agentSteps && msg.agentSteps.length > 0)
  );

  return (
    <div
      ref={scrollContainerRef}
      onScroll={handleScroll}
      className="flex-1 overflow-y-auto w-full pb-48 pt-8"
    >
      <div className="max-w-3xl mx-auto flex flex-col space-y-6 px-4">
        {visibleMessages.map((msg, index) => {
          const isStreamingMsg =
            msg.generation_id === activeGenerationId &&
            msg.status === "streaming";

          return (
            <div
              key={msg.id || index}
              className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
            >
              {msg.role === "user" && msg.attachedFiles && msg.attachedFiles.length > 0 && (
                <div className="mb-2 flex flex-wrap justify-end gap-2 max-w-[85%]">
                  {msg.attachedFiles.map((file) => (
                    <div
                      key={file}
                      className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/40 p-2 pr-4 text-left"
                    >
                      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-[#ff4d4d]">
                        <FileText className="h-5 w-5 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white" title={file}>
                          {file}
                        </p>
                        <p className="text-[10px] text-gray-400">PDF</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div
                className={`${
                  msg.role === "user"
                    ? `max-w-[85%] rounded-3xl ${
                        msg.content.startsWith("/quiz ") ? "bg-transparent p-0" : "bg-[#2f2f2f] px-6 py-2.5"
                      } text-[var(--color-foreground)]`
                    : "max-w-none bg-transparent text-[var(--color-foreground)]"
                }`}
              >
                {msg.role === "assistant" && (
                  <div className="flex items-center gap-2 mb-2 text-sm font-semibold text-gray-300">
                    <div
                      className={`w-6 h-6 rounded-full bg-[var(--color-brand)] flex items-center justify-center ${
                        isStreamingMsg ? "animate-pulse" : ""
                      }`}
                    >
                      <span className="text-xs text-white">AI</span>
                    </div>
                    EducAgent
                  </div>
                )}

                <div className="prose prose-invert max-w-none text-sm md:text-base leading-relaxed">
                  {msg.role === "user" ? (
                    <div className="whitespace-pre-wrap m-0">
                      {renderUserContent(msg.content)}
                    </div>
                  ) : (
                    <>
                      <AgentTrace
                        steps={msg.agentSteps || []}
                        reasoning={msg.reasoning || ""}
                        sources={msg.sources || []}
                        isActive={isStreamingMsg}
                      />
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                      {isStreamingMsg && (
                        <span className="inline-block w-[2px] h-[1.1em] bg-gray-300 ml-0.5 animate-pulse align-text-bottom" />
                      )}
                    </>
                  )}
                </div>

                {msg.status === "failed" && (
                  <div className="mt-2 text-xs text-red-400 flex items-center gap-1">
                    <span>Generation failed</span>
                  </div>
                )}

                {msg.status === "stopped" && (
                  <div className="mt-2 text-xs text-yellow-400/60 flex items-center gap-1">
                    <span>Generation stopped</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isStreaming &&
          (visibleMessages.length === 0 ||
            visibleMessages[visibleMessages.length - 1]?.role === "user") && (
            <div className="flex justify-start">
              <div className="max-w-[85%] px-5 py-3 text-[var(--color-foreground)]">
                <div className="flex items-center gap-2 mb-2 text-sm font-semibold text-gray-300">
                  <div className="w-6 h-6 rounded-full bg-[var(--color-brand)] flex items-center justify-center animate-pulse">
                    <span className="text-xs text-white">AI</span>
                  </div>
                  EducAgent
                </div>
                <AgentTrace steps={[]} isActive />
              </div>
            </div>
          )}

        {isStreaming && (
          <div className="flex justify-center">
            <button
              onClick={onStopGeneration}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[#2f2f2f] border border-white/10 text-gray-300 hover:text-white hover:bg-[#3a3a3a] transition-colors text-sm"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              Stop generating
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function QuizAccordion({ topic, content }: { topic: string; content: string }) {
  const [isOpen, setIsOpen] = useState(false);

  // Parse questions and answers from the log
  // Format: "1. Question\nAnswer\n2. Question\nAnswer..."
  const lines = content.split("\n");
  const qaPairs: { q: string; a: string }[] = [];
  let currentQ = "";
  let currentA = "";

  lines.forEach((line) => {
    if (/^\d+\.\s/.test(line)) {
      if (currentQ) qaPairs.push({ q: currentQ, a: currentA });
      currentQ = line;
      currentA = "";
    } else if (line.trim()) {
      currentA += (currentA ? "\n" : "") + line;
    }
  });
  if (currentQ) qaPairs.push({ q: currentQ, a: currentA });

  return (
    <div className="w-full space-y-2">
      <div className="flex items-center gap-2 mb-2">
        <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full text-xs font-mono">
          /quiz
        </span>
        <span className="text-sm font-medium text-gray-300">{topic}</span>
      </div>

      <div className="rounded-2xl border border-white/10 bg-[#2f2f2f] overflow-hidden">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center justify-between p-4 text-left hover:bg-white/5 transition-colors"
        >
          <div className="flex items-center gap-3 text-gray-200 font-medium">
            <HelpCircle className="w-5 h-5 text-blue-400" />
            <span>Quiz Results</span>
          </div>
          {isOpen ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
        </button>

        {isOpen && (
          <div className="p-4 pt-0 space-y-4 border-t border-white/5 bg-black/20">
            {qaPairs.map((pair, i) => (
              <div key={i} className="space-y-1.5 border-b border-white/5 pb-3 last:border-0 last:pb-0">
                <p className="text-gray-200 font-medium text-sm leading-snug">
                  {pair.q}
                </p>
                <p className="text-blue-400 text-sm pl-4 border-l-2 border-blue-500/30">
                  {pair.a}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function renderUserContent(content: string) {
  if (content.startsWith("/quiz ")) {
    const firstNewline = content.indexOf("\n");
    if (firstNewline === -1) return content;

    const header = content.slice(0, firstNewline);
    const topicMatch = header.match(/"([^"]+)"/);
    const topic = topicMatch ? topicMatch[1] : "Quiz";
    const body = content.slice(firstNewline + 1);

    return <QuizAccordion topic={topic} content={body} />;
  }
  return content;
}
