"use client";

import {
  MessageSquare,
  Plus,
  User,
  Settings,
  MoreHorizontal,
  Edit2,
  Trash2,
  Cpu,
  Cloud,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { twMerge } from "tailwind-merge";
import { ChatSummary, api } from "@/lib/api";

interface SidebarProps {
  sessions: ChatSummary[];
  currentSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onOpenSettings: () => void;
  onRenameChat: (id: string, newTitle: string) => void;
  onDeleteChat: (id: string) => void;
  settingsRevision?: number;
}

export default function Sidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onOpenSettings,
  onRenameChat,
  onDeleteChat,
  settingsRevision = 0,
}: SidebarProps) {
  const [isOpen] = useState(true);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [modelInfo, setModelInfo] = useState<{
    provider: string;
    model: string;
  } | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown if clicked outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
      ) {
        setActiveMenuId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [settingsRevision]);

  // Fetch current model info independently
  useEffect(() => {
    async function fetchModelInfo() {
      try {
        const settings = await api.getSettings();
        setModelInfo({
          provider: settings.provider,
          model: settings.model,
        });
      } catch {
        // silent fail — non-critical
      }
    }
    fetchModelInfo();
  }, []);

  const handleRename = (id: string, currentTitle: string) => {
    const newTitle = prompt("Enter new name for the chat:", currentTitle);
    if (newTitle && newTitle.trim() !== "") {
      onRenameChat(id, newTitle.trim());
    }
    setActiveMenuId(null);
  };

  const handleDelete = (id: string) => {
    if (window.confirm("Are you sure you want to delete this chat?")) {
      onDeleteChat(id);
    }
    setActiveMenuId(null);
  };

  const isLocal = modelInfo?.provider === "ollama";

  return (
    <div
      className={twMerge(
        "bg-[var(--color-sidebar)] text-white h-screen flex-shrink-0 transition-all duration-300 ease-in-out flex flex-col",
        isOpen ? "w-[260px]" : "w-0 overflow-hidden"
      )}
    >
      <div className="p-3 flex items-center justify-between h-[60px]">
        <button
          onClick={onNewChat}
          className="flex-1 flex items-center gap-2 hover:bg-white/5 p-2 rounded-md transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          New chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        <div className="text-xs font-semibold text-gray-500 mb-3 px-2">
          Recent
        </div>
        {sessions.map((session) => (
          <div key={session.chat_id} className="relative group">
            <button
              onClick={() => onSelectSession(session.chat_id)}
              className={twMerge(
                "w-full text-left flex items-center gap-3 p-2 rounded-md hover:bg-white/5 transition-colors text-sm truncate",
                currentSessionId === session.chat_id ? "bg-white/10" : ""
              )}
            >
              <MessageSquare className="w-4 h-4 shrink-0" />
              <span className="truncate flex-1">
                {session.title || `Chat ${session.chat_id.slice(0, 8)}...`}
              </span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActiveMenuId(
                  activeMenuId === session.chat_id ? null : session.chat_id
                );
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-md opacity-0 group-hover:opacity-100 hover:bg-white/10 transition-all"
            >
              <MoreHorizontal className="w-4 h-4 text-gray-300" />
            </button>

            {activeMenuId === session.chat_id && (
              <div
                ref={menuRef}
                className="absolute right-2 top-10 bg-[#2f2f2f] border border-white/10 rounded-md shadow-xl py-1 z-50 w-32"
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRename(session.chat_id, session.title || "");
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 flex items-center gap-2 text-gray-200"
                >
                  <Edit2 className="w-4 h-4" />
                  Rename
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(session.chat_id);
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 flex items-center gap-2 text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Model Indicator + Profile / Settings Section */}
      <div className="p-3 border-t border-white/10 space-y-2">
        {/* Model indicator badge */}
        {modelInfo && (
          <div className="flex items-center gap-2 px-2 py-1.5 bg-white/[0.03] rounded-lg">
            {isLocal ? (
              <Cpu className="w-3.5 h-3.5 text-green-400" />
            ) : (
              <Cloud className="w-3.5 h-3.5 text-blue-400" />
            )}
            <span className="text-[11px] text-gray-400 truncate flex-1">
              {isLocal ? "Local" : "Cloud"} ·{" "}
              <span className="text-gray-300">
                {modelInfo.model.length > 20
                  ? modelInfo.model.slice(0, 20) + "…"
                  : modelInfo.model}
              </span>
            </span>
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isLocal ? "bg-green-400" : "bg-blue-400"
              }`}
            />
          </div>
        )}

        <button
          onClick={onOpenSettings}
          className="flex items-center gap-3 hover:bg-white/5 w-full p-2 rounded-md text-sm transition-colors group"
        >
          <div className="w-8 h-8 flex items-center justify-center">
            <Settings className="w-5 h-5 text-white" />
          </div>
          <span className="flex-1 text-left font-medium">Settings</span>
        </button>
      </div>
    </div>
  );
}
