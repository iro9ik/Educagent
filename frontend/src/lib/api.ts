const API_BASE = "http://localhost:8000/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  status?: string;
  generation_id?: string | null;
  agent_steps?: AgentStep[];
  reasoning?: string;
  sources?: string[];
  attached_files?: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  updatedAt: string;
}

export interface ChatSummary {
  chat_id: string;
  title: string;
  updated_at: string;
}

export interface QuizQuestion {
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
}

export interface Quiz {
  id: string;
  topic: string;
  questions: QuizQuestion[];
}

export interface GenerationResult {
  generation_id: string;
  message_id: string;
  chat_id: string;
}

export interface AgentStep {
  agent: string;
  status: "running" | "completed" | "error";
  label: string;
  detail?: string;
  duration_ms?: number;
  startedAt: number;
}

export interface StreamEvent {
  type: "token" | "agent_status" | "reasoning" | "sources" | "completed" | "stopped" | "error";
  chunk?: string;
  seq?: number;
  error?: string;
  agent?: string;
  status?: "running" | "completed" | "error";
  label?: string;
  detail?: string;
  duration_ms?: number;
  content?: string;
  files?: string[];
}

export interface ActiveGenerationState {
  generation_id: string;
  message_id: string;
  chat_id: string;
  status: string;
  seq: string;
}

export interface GlobalSettings {
  provider: string;
  base_url: string;
  api_key: string;
  model: string;
  embed_model: string;
}

export const api = {
  async startChat(topic?: string) {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: topic }),
    });
    if (!res.ok) throw new Error("Failed to start chat");
    return res.json(); // { chat_id, ... }
  },

  async getHistory() {
    const res = await fetch(`${API_BASE}/chats`);
    if (!res.ok) throw new Error("Failed to get history");
    const data = await res.json();
    return data.chats || [];
  },

  async getChat(chatId: string) {
    const res = await fetch(`${API_BASE}/chat/${chatId}`);
    if (!res.ok) throw new Error("Failed to get chat");
    return res.json();
  },

  async renameChat(chatId: string, title: string) {
    const res = await fetch(`${API_BASE}/chat/${chatId}/rename`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error("Failed to rename chat");
    return res.json();
  },

  async deleteChat(chatId: string) {
    const res = await fetch(`${API_BASE}/chat/${chatId}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete chat");
    return res.json();
  },
  
  async saveMessage(chatId: string, role: "user" | "assistant", content: string) {
    const res = await fetch(`${API_BASE}/chat/${chatId}/save-message`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role, content }),
    });
    if (!res.ok) throw new Error("Failed to save message");
    return res.json();
  },

  // ─── New Generation API ─────────────────────────────────────────

  async startGeneration(
    chatId: string,
    content: string,
    searchEnabled = false,
    thinkingEnabled = false,
    attachedFiles: string[] = []
  ): Promise<GenerationResult> {
    const res = await fetch(`${API_BASE}/chat/${chatId}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content,
        search_enabled: searchEnabled,
        thinking_enabled: thinkingEnabled,
        attached_files: attachedFiles,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to start generation");
    }
    return res.json();
  },

  subscribeToStream(
    generationId: string,
    lastSeq: number,
    onEvent: (event: StreamEvent) => void,
    signal?: AbortSignal
  ) {
    const url = `${API_BASE}/stream/${generationId}?last_seq=${lastSeq}`;

    const eventSource = new EventSource(url);

    // Handle abort signal
    if (signal) {
      signal.addEventListener("abort", () => {
        eventSource.close();
      });
    }

    eventSource.onmessage = (e) => {
      try {
        const data: StreamEvent = JSON.parse(e.data);
        onEvent(data);

        // Auto-close on terminal events
        if (data.type === "completed" || data.type === "stopped" || data.type === "error") {
          eventSource.close();
        }
      } catch (err) {
        console.error("Error parsing stream event:", err);
      }
    };

    eventSource.onerror = () => {
      // EventSource will auto-reconnect, but if aborted we close
      if (signal?.aborted) {
        eventSource.close();
      }
    };

    return eventSource;
  },

  async stopGeneration(generationId: string) {
    const res = await fetch(`${API_BASE}/stream/${generationId}/stop`, {
      method: "POST",
    });
    if (!res.ok) throw new Error("Failed to stop generation");
    return res.json();
  },

  async getActiveGeneration(chatId: string) {
    const res = await fetch(`${API_BASE}/chat/${chatId}/active-generation`);
    if (!res.ok) return null;
    const data = await res.json();
    // Returns { generation_id, message_id, status, ... } or { active: false }
    if (data.active === false) return null;
    return data;
  },

  // ─── Quiz API ──────────────────────────────────────────────────

  async generateQuiz(
    topic: string,
    chatId?: string | null,
    attachedFiles: string[] = [],
    difficulty: string = "medium"
  ) {
    const res = await fetch(`${API_BASE}/quiz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic,
        difficulty,
        chat_id: chatId,
        attached_files: attachedFiles,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to generate quiz");
    }
    return res.json();
  },

  async evaluateQuiz(
    answers: Array<{ question: string; given_answer: string; correct_answer: string }>
  ) {
    const res = await fetch(`${API_BASE}/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      // Surface structured validation errors
      if (res.status === 422 && err.detail?.status === "FAILED_VALIDATION") {
        const error = new Error(err.detail.reason || "Quiz validation failed") as Error & { isValidationError: boolean };
        error.isValidationError = true;
        throw error;
      }
      throw new Error(err.detail || "Failed to evaluate quiz");
    }
    return res.json();
  },

  // ─── Settings ──────────────────────────────────────────────────

  async getSettings() {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error("Failed to get settings");
    return res.json();
  },

  async updateSettings(settings: GlobalSettings) {
    const res = await fetch(`${API_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    if (!res.ok) throw new Error("Failed to update settings");
    return res.json();
  },

  // ─── Uploads ───────────────────────────────────────────────────

  async uploadDocuments(files: FileList) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("files", files[i]);
    }
    const res = await fetch(`${API_BASE}/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to upload documents");
    }
    return res.json();
  },

  async getUploadedFiles(): Promise<string[]> {
    const res = await fetch(`${API_BASE}/files`);
    if (!res.ok) throw new Error("Failed to list uploaded files");
    const data = await res.json();
    return data.files || [];
  },

  async deleteDocument(filename: string) {
    const res = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Failed to delete document");
    }
    return res.json();
  },

  async checkOllamaHealth(baseUrl?: string) {
    try {
      const url = baseUrl ? `${API_BASE}/health/ollama?base_url=${encodeURIComponent(baseUrl)}` : `${API_BASE}/health/ollama`;
      const res = await fetch(url);
      if (!res.ok) return false;
      const data = await res.json();
      return data.status === "ok";
    } catch {
      return false;
    }
  },
};
