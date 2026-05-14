export const storage = {
  getSessions(): string[] {
    if (typeof window === "undefined") return [];
    const sessions = localStorage.getItem("chat_sessions");
    return sessions ? JSON.parse(sessions) : [];
  },

  addSession(sessionId: string) {
    if (typeof window === "undefined") return;
    const sessions = this.getSessions();
    if (!sessions.includes(sessionId)) {
      sessions.push(sessionId);
      localStorage.setItem("chat_sessions", JSON.stringify(sessions));
    }
  },

  removeSession(sessionId: string) {
    if (typeof window === "undefined") return;
    const sessions = this.getSessions();
    const updated = sessions.filter(id => id !== sessionId);
    localStorage.setItem("chat_sessions", JSON.stringify(updated));
  },

  getCurrentSession(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("current_session");
  },

  setCurrentSession(sessionId: string) {
    if (typeof window === "undefined") return;
    localStorage.setItem("current_session", sessionId);
  }
};
