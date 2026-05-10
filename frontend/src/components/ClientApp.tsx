"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  ActiveGenerationState,
  AgentStep,
  api,
  ChatSummary,
  StreamEvent,
  Quiz,
} from "../lib/api";
import Sidebar from "./Sidebar";
import ChatArea from "./ChatArea";
import InputArea from "./InputArea";
import SettingsModal from "./SettingsModal";

interface Message {
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

interface SendOptions {
  searchEnabled: boolean;
  thinkingEnabled: boolean;
  attachedFiles?: string[];
}

interface ActiveGeneration {
  generationId: string;
  messageId: string;
  chatId: string;
  seq: number;
  eventSource?: EventSource;
}

interface ApiMessage {
  role: "user" | "assistant";
  content: string;
  status?: string;
  generation_id?: string | null;
  agent_steps?: AgentStep[];
  reasoning?: string;
  sources?: string[];
  attached_files?: string[];
}

interface ClientAppProps {
  initialChatId?: string | null;
}

export default function ClientApp({ initialChatId }: ClientAppProps) {
  // Core state
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(
    initialChatId || null
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatList, setChatList] = useState<ChatSummary[]>([]);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsRevision, setSettingsRevision] = useState(0);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);

  // Generation state — tracked per chat, not globally
  const [activeGeneration, setActiveGeneration] =
    useState<ActiveGeneration | null>(null);
  const activeGenRef = useRef<ActiveGeneration | null>(null);

  // Quiz state
  const [isQuizLoading, setIsQuizLoading] = useState(false);
  const [isQuizGrading, setIsQuizGrading] = useState(false);
  const [activeQuiz, setActiveQuiz] = useState<Quiz | null>(null);

  // Keep ref in sync with state
  useEffect(() => {
    activeGenRef.current = activeGeneration;
  }, [activeGeneration]);

  // ─── Chat List ────────────────────────────────────────────────

  const refreshChatList = useCallback(async () => {
    try {
      const chats = await api.getHistory();
      setChatList(chats);
    } catch (err) {
      console.error("Failed to refresh chat list:", err);
    }
  }, []);

  const refreshUploadedFiles = useCallback(async () => {
    try {
      setUploadedFiles(await api.getUploadedFiles());
    } catch (err) {
      console.error("Failed to refresh uploaded files:", err);
    }
  }, []);

  // Load chat list on mount
  useEffect(() => {
    refreshChatList();
    refreshUploadedFiles();
  }, [refreshChatList, refreshUploadedFiles]);

  // ─── Load Chat Messages ──────────────────────────────────────

  const loadChat = useCallback(
    async (chatId: string) => {
      try {
        const chat = await api.getChat(chatId);
        const msgs: Message[] = ((chat.messages || []) as ApiMessage[]).map((m) => ({
          role: m.role,
          content: m.content,
          status: m.status || "completed",
          generation_id: m.generation_id,
          agentSteps: m.agent_steps || [],
          reasoning: m.reasoning || "",
          sources: m.sources || [],
          attachedFiles: m.attached_files || [],
        }));
        setMessages(msgs);

        // Check if this chat has an active generation we should reconnect to
        const activeGen = await api.getActiveGeneration(chatId);
        if (activeGen && activeGen.generation_id) {
          reconnectToGeneration(chatId, activeGen);
        }
      } catch (err) {
        console.error("Failed to load chat:", err);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // ─── Handle Chat Selection ──────────────────────────────────

  const handleSelectSession = useCallback(
    (chatId: string, navigate = true) => {
      // Close any existing SSE connection (but DON'T stop the generation)
      if (activeGenRef.current?.eventSource) {
        activeGenRef.current.eventSource.close();
      }
      setActiveGeneration(null);

      setCurrentSessionId(chatId);
      if (navigate) {
        window.history.replaceState(null, "", `/chat/${chatId}`);
      }
      loadChat(chatId);
    },
    [loadChat]
  );

  // ─── Initial Load ────────────────────────────────────────────

  useEffect(() => {
    if (initialChatId) {
      setCurrentSessionId(initialChatId);
      loadChat(initialChatId);
    } else {
      setCurrentSessionId(null);
      setMessages([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialChatId]);

  // ─── Reconnect to Existing Generation ────────────────────────

  const reconnectToGeneration = useCallback(
    (chatId: string, genState: ActiveGenerationState) => {
      const generationId = genState.generation_id;
      const messageId = genState.message_id;
      const currentSeq = parseInt(genState.seq || "0", 10);

      // Find or create the streaming message in the message list
      setMessages((prev) => {
        const hasStreamingMsg = prev.some(
          (m) => m.generation_id === generationId
        );
        if (!hasStreamingMsg) {
          return [
            ...prev,
            {
              role: "assistant" as const,
              content: "",
              status: "streaming",
              generation_id: generationId,
              agentSteps: [],
              reasoning: "",
              sources: [],
            },
          ];
        }
        return prev;
      });

      // Subscribe to the stream — replay from seq 0 since we already
      // get the current content from loadChat
      const controller = new AbortController();

      const eventSource = api.subscribeToStream(
        generationId,
        currentSeq,
        (event: StreamEvent) => {
          applyStreamEvent(generationId, event);
          if (event.type === "completed" || event.type === "stopped" || event.type === "error") {
            setActiveGeneration(null);
            refreshChatList();
          }
        },
        controller.signal
      );

      setActiveGeneration({
        generationId,
        messageId,
        chatId,
        seq: currentSeq,
        eventSource,
      });
    },
    [refreshChatList]
  );

  // ─── Send Message ────────────────────────────────────────────

  const handleSendMessage = useCallback(
    async (content: string, options: SendOptions) => {
      if (!content.trim()) return;

      let chatId = currentSessionId;

      // Create new chat if needed
      if (!chatId) {
        try {
          const chat = await api.startChat(content.slice(0, 40));
          chatId = chat.chat_id;
          setCurrentSessionId(chatId);
          window.history.replaceState(null, "", `/chat/${chatId}`);
          await refreshChatList();
        } catch (err) {
          console.error("Failed to create chat:", err);
          return;
        }
      }

      if (!chatId) return;

      // Add user message to UI immediately
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content,
          status: "completed",
          attachedFiles: options.attachedFiles || [],
        },
      ]);

      try {
        // Start generation — this returns immediately
        const result = await api.startGeneration(
          chatId,
          content,
          options.searchEnabled,
          options.thinkingEnabled,
          options.attachedFiles || []
        );

        // Add streaming assistant placeholder
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "",
            status: "streaming",
            generation_id: result.generation_id,
            agentSteps: [],
            reasoning: "",
            sources: [],
          },
        ]);

        // Subscribe to the token stream via SSE
        const controller = new AbortController();

        const eventSource = api.subscribeToStream(
          result.generation_id,
          0,
          (event: StreamEvent) => {
            applyStreamEvent(result.generation_id, event);
            if (event.type === "completed" || event.type === "stopped" || event.type === "error") {
              setActiveGeneration(null);
              refreshChatList();
            }
          },
          controller.signal
        );

        setActiveGeneration({
          generationId: result.generation_id,
          messageId: result.message_id,
          chatId: chatId,
          seq: 0,
          eventSource,
        });
      } catch (err) {
        console.error("Failed to start generation:", err);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
            status: "failed",
          },
        ]);
      }
    },
    [currentSessionId, refreshChatList]
  );

  function applyStreamEvent(generationId: string, event: StreamEvent) {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.generation_id !== generationId) return m;

        switch (event.type) {
          case "token":
            return event.chunk ? { ...m, content: m.content + event.chunk } : m;
          case "agent_status":
            if (!event.agent || !event.status) return m;
            return {
              ...m,
              agentSteps: mergeAgentStep(m.agentSteps || [], event),
            };
          case "reasoning":
            return { ...m, reasoning: event.content || "" };
          case "sources":
            return { ...m, sources: event.files || [] };
          case "completed":
          case "stopped":
          case "error":
            return {
              ...m,
              status: event.type === "error" ? "failed" : event.type,
              content:
                event.type === "error" && !m.content
                  ? `Error: ${event.error || "Generation failed"}`
                  : m.content,
            };
          default:
            return m;
        }
      })
    );

    if (event.type === "token") {
      setActiveGeneration((prev) =>
        prev ? { ...prev, seq: event.seq || prev.seq } : prev
      );
    }
  }

  // ─── Stop Generation ─────────────────────────────────────────

  const handleStopGeneration = useCallback(async () => {
    if (!activeGeneration) return;

    try {
      await api.stopGeneration(activeGeneration.generationId);
    } catch (err) {
      console.error("Failed to stop generation:", err);
    }

    // The SSE stream will receive a 'stopped' event which handles cleanup
  }, [activeGeneration]);

  // ─── New Chat ────────────────────────────────────────────────

  const handleNewChat = useCallback(() => {
    // Close SSE but don't stop generation
    if (activeGenRef.current?.eventSource) {
      activeGenRef.current.eventSource.close();
    }
    setActiveGeneration(null);
    setCurrentSessionId(null);
    setMessages([]);
    setActiveQuiz(null);
    window.history.replaceState(null, "", "/");
  }, []);

  // ─── Delete Chat ─────────────────────────────────────────────

  const handleDeleteChat = useCallback(
    async (chatId: string) => {
      try {
        await api.deleteChat(chatId);
        await refreshChatList();
        if (currentSessionId === chatId) {
          handleNewChat();
        }
      } catch (err) {
        console.error("Failed to delete chat:", err);
      }
    },
    [currentSessionId, refreshChatList, handleNewChat]
  );

  // ─── Rename Chat ─────────────────────────────────────────────

  const handleRenameChat = useCallback(
    async (chatId: string, title: string) => {
      try {
        await api.renameChat(chatId, title);
        await refreshChatList();
      } catch (err) {
        console.error("Failed to rename chat:", err);
      }
    },
    [refreshChatList]
  );

  // ─── Quiz Handlers ──────────────────────────────────────────

  const handleGenerateQuiz = useCallback(async (topic: string, attachedFiles: string[] = []) => {
    setIsQuizLoading(true);
    try {
      let chatId = currentSessionId;
      if (!chatId) {
        const chat = await api.startChat(`/quiz ${topic}`.slice(0, 40));
        chatId = chat.chat_id;
        setCurrentSessionId(chatId);
        window.history.replaceState(null, "", `/chat/${chatId}`);
        await refreshChatList();
      }

      const result = await api.generateQuiz(topic, chatId, attachedFiles);
      
      // Add the user command to local state
      setMessages((prev) => [
        ...prev,
        { role: "user", content: `/quiz ${topic}`, status: "completed" },
      ]);
      
      setActiveQuiz({
        id: `quiz_${Date.now()}`,
        topic: result.topic,
        questions: result.questions,
      });
    } catch (err) {
      console.error("Failed to generate quiz:", err);
      alert(err instanceof Error ? err.message : "Failed to generate quiz. Please check if your AI model is running.");
    } finally {
      setIsQuizLoading(false);
    }
  }, [currentSessionId, refreshChatList]);

  const handleQuizSubmit = useCallback(
    async (quizId: string, answers: Record<string, string>) => {
      if (!activeQuiz) return;
      setIsQuizGrading(true);

      try {
        const answerPayload = activeQuiz.questions.map((q, idx) => ({
          question: q.question,
          given_answer: answers[idx] || "",
          correct_answer: q.correct_answer || "",
        }));

        const result = await api.evaluateQuiz(answerPayload);

        const resultText = `📊 **Quiz Results: ${activeQuiz.topic}**\n\nScore: **${result.percentage || 0}%** (${result.total_score || 0}/${result.max_score || 0})\n\n${result.feedback || ""}`;

        // Format user's quiz answers for the chat history
        let userMessageText = `/quiz "${activeQuiz.topic}"\n`;
        activeQuiz.questions.forEach((q, idx) => {
          userMessageText += `${idx + 1}. ${q.question}\n`;
          userMessageText += `${answers[idx] || "No answer provided"}\n`;
        });

        // Persist to backend if we have a session
        if (currentSessionId) {
          await api.saveMessage(currentSessionId, "user", userMessageText);
          await api.saveMessage(currentSessionId, "assistant", resultText);
        }
 
         setMessages((prev) => [
           ...prev,
           { role: "user", content: userMessageText, status: "completed" },
           { role: "assistant", content: resultText, status: "completed" },
         ]);
      } catch (err) {
        console.error("Failed to evaluate quiz:", err);
        const isValidationError = err instanceof Error && (err as Error & { isValidationError?: boolean }).isValidationError;
        const errorMessage = isValidationError
          ? `⚠️ **Quiz Validation Error**\n\n${err instanceof Error ? err.message : "Quiz validation failed."}\n\nThis quiz was generated with incomplete answer keys. Please generate a new quiz and try again.`
          : `❌ **Quiz Evaluation Failed**\n\n${err instanceof Error ? err.message : "An unexpected error occurred."}\n\nPlease try again.`;

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: errorMessage,
            status: "failed",
          },
        ]);
      } finally {
        setIsQuizGrading(false);
        setActiveQuiz(null);
      }
    },
    [activeQuiz]
  );

  const handleQuizClose = useCallback(() => {
    setActiveQuiz(null);
  }, []);

  // ─── Cleanup on unmount ──────────────────────────────────────

  useEffect(() => {
    return () => {
      // Close SSE on unmount (generation continues in background)
      if (activeGenRef.current?.eventSource) {
        activeGenRef.current.eventSource.close();
      }
    };
  }, []);

  // ─── Determine streaming state for current chat ──────────────

  const isStreaming =
    activeGeneration !== null &&
    activeGeneration.chatId === currentSessionId;

  return (
    <div className="flex h-screen bg-[var(--color-background)]">
      <Sidebar
        sessions={chatList}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        onRenameChat={handleRenameChat}
        onOpenSettings={() => setIsSettingsOpen(true)}
        settingsRevision={settingsRevision}
      />

      <main className="flex-1 flex flex-col relative overflow-hidden">
        <ChatArea
          messages={messages}
          isStreaming={isStreaming}
          activeGenerationId={activeGeneration?.generationId || null}
          onStopGeneration={handleStopGeneration}
        />

        <InputArea
          onSendMessage={handleSendMessage}
          uploadedFiles={uploadedFiles}
          onFilesUploaded={refreshUploadedFiles}
          isStreaming={isStreaming}
          isQuizLoading={isQuizLoading}
          isQuizGrading={isQuizGrading}
          activeQuiz={activeQuiz}
          onQuizSubmit={handleQuizSubmit}
          onQuizClose={handleQuizClose}
          onGenerateQuiz={handleGenerateQuiz}
          onStopGeneration={handleStopGeneration}
        />
      </main>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSaved={() => setSettingsRevision((value) => value + 1)}
      />
    </div>
  );
}

function mergeAgentStep(steps: AgentStep[], event: StreamEvent): AgentStep[] {
  if (!event.agent || !event.status) return steps;

  const existing = steps.find((step) => step.agent === event.agent);
  const nextStep: AgentStep = {
    agent: event.agent,
    status: event.status,
    label: event.label || existing?.label || titleCase(event.agent),
    detail: event.detail || existing?.detail,
    duration_ms: event.duration_ms ?? existing?.duration_ms,
    startedAt: existing?.startedAt || Date.now(),
  };

  if (existing) {
    return steps.map((step) => (step.agent === event.agent ? nextStep : step));
  }

  return [...steps, nextStep];
}

function titleCase(value: string) {
  return value
    .split(/[_-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
