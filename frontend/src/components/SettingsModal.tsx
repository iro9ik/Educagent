"use client";

import { X, Globe, Cpu, Key, Save, Loader2 } from "lucide-react";
import { useCallback, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

const MODELS = [
  { id: "local", name: "Local Model (Ollama)", provider: "ollama" },
  { id: "nvidia/nemotron-3-super-120b-a12b:free", name: "Nvidia Nemotron 3 (Free)", provider: "custom" },
  { id: "google/gemma-4-31b-it:free", name: "Google Gemma 4 (Free)", provider: "custom" },
  { id: "minimax/minimax-m2.5:free", name: "Minimax M2.5 (Free)", provider: "custom" },
  { id: "z-ai/glm-4.5-air:free", name: "GLM-4.5 Air (Free)", provider: "custom" },
];

export default function SettingsModal({ isOpen, onClose, onSaved }: SettingsModalProps) {
  const [settings, setSettings] = useState({
    provider: "ollama",
    base_url: "http://localhost:11434/v1",
    api_key: "",
    model: "qwen3:8b",
    embed_model: "nomic-embed-text",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"local" | "cloud">("local");
  const [ollamaHealth, setOllamaHealth] = useState<boolean | null>(null);

  const checkOllama = useCallback(async (url?: string) => {
    setOllamaHealth(null);
    const isHealthy = await api.checkOllamaHealth(url || "http://localhost:11434");
    setOllamaHealth(isHealthy);
  }, []);

  const loadSettings = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await api.getSettings();
      setSettings(data);
      if (data.provider === "custom") {
        setActiveTab("cloud");
      } else {
        setActiveTab("local");
      }
    } catch (e) {
      console.error("Failed to load settings", e);
      setError("Failed to connect to the server. Please ensure the backend is running.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      const id = window.setTimeout(() => {
        loadSettings();
      }, 0);
      return () => window.clearTimeout(id);
    }
  }, [isOpen, loadSettings]);

  useEffect(() => {
    if (isOpen && activeTab === "local") {
      checkOllama("http://localhost:11434");
    }
  }, [isOpen, activeTab, checkOllama]);

  const handleSave = async () => {
    try {
      setIsSaving(true);
      
      const payload = { ...settings };
      if (activeTab === "local") {
        payload.provider = "ollama";
        payload.model = "qwen3:8b";
        payload.base_url = "http://localhost:11434/v1";
        payload.api_key = "";
      } else {
        payload.provider = "custom";
        if (payload.model === "qwen3:8b" || payload.model === "") {
          payload.model = MODELS[1].id;
        }
      }

      await api.updateSettings(payload);
      onSaved?.();
      onClose();
    } catch (e) {
      console.error("Failed to save settings", e);
      alert("Failed to save settings. Make sure the backend is running.");
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="bg-[#2f2f2f] border border-white/10 rounded-xl w-full max-w-md overflow-hidden shadow-2xl"
        >
          <div className="flex items-center justify-between p-4 border-b border-white/5">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-blue-400" />
              AI Settings
            </h2>
            <button onClick={onClose} className="p-1 hover:bg-white/5 rounded-full text-gray-400 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 space-y-6">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center py-10 space-y-4">
                <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                <p className="text-sm text-gray-400">Loading current configuration...</p>
              </div>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-10 space-y-4 text-center">
                <div className="p-3 bg-red-500/10 rounded-full">
                  <X className="w-6 h-6 text-red-500" />
                </div>
                <p className="text-sm text-red-400 max-w-[240px]">{error}</p>
                <button 
                  onClick={loadSettings}
                  className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm text-white transition-colors"
                >
                  Try Again
                </button>
              </div>
            ) : (
              <>
                <div className="flex bg-white/5 p-1 rounded-lg">
                  <button
                    onClick={() => setActiveTab("local")}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      activeTab === "local" ? "bg-[#3f3f3f] text-white shadow" : "text-gray-400 hover:text-white"
                    }`}
                  >
                    Local Model
                  </button>
                  <button
                    onClick={() => setActiveTab("cloud")}
                    className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors ${
                      activeTab === "cloud" ? "bg-[#3f3f3f] text-white shadow" : "text-gray-400 hover:text-white"
                    }`}
                  >
                    Cloud API
                  </button>
                </div>

                {activeTab === "local" && (
                  <div className="space-y-4 pt-2">
                    <div className="p-4 bg-white/5 rounded-lg border border-white/10 flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-medium text-white">Ollama (Qwen3:8B)</h3>
                        <p className="text-xs text-gray-400 mt-1">Local inference engine</p>
                      </div>
                      <div className="flex items-center gap-2">
                        {ollamaHealth === null ? (
                          <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
                        ) : ollamaHealth ? (
                          <span className="flex items-center gap-1.5 text-xs font-medium text-green-400 bg-green-400/10 px-2.5 py-1 rounded-full">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                            Connected
                          </span>
                        ) : (
                          <span className="flex items-center gap-1.5 text-xs font-medium text-red-400 bg-red-400/10 px-2.5 py-1 rounded-full">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                            Disconnected
                          </span>
                        )}
                      </div>
                    </div>
                    {ollamaHealth === false && (
                      <p className="text-xs text-red-400/80 px-1">
                        Please ensure Ollama is downloaded, running, and accessible at localhost:11434.
                      </p>
                    )}
                  </div>
                )}

                {activeTab === "cloud" && (
                  <div className="space-y-4 pt-2">
                    <div className="space-y-2">
                      <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">Model Selection</label>
                      <select
                        value={settings.model === "qwen3:8b" && settings.provider === "ollama" ? MODELS[1].id : settings.model}
                        onChange={(e) => {
                          setSettings({ ...settings, provider: "custom", model: e.target.value });
                        }}
                        className="w-full bg-[#3f3f3f] border border-white/10 rounded-lg p-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                      >
                        {MODELS.filter(m => m.id !== "local").map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">API Base URL</label>
                      <div className="relative">
                        <Globe className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                        <input
                          type="text"
                          value={settings.base_url}
                          onChange={(e) => setSettings({ ...settings, base_url: e.target.value })}
                          placeholder="https://openrouter.ai/api/v1"
                          className="w-full bg-[#3f3f3f] border border-white/10 rounded-lg py-2 pl-10 pr-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label className="text-xs font-medium text-gray-400 uppercase tracking-wider">API Key</label>
                      <div className="relative">
                        <Key className="absolute left-3 top-2.5 w-4 h-4 text-gray-500" />
                        <input
                          type="password"
                          value={settings.api_key}
                          onChange={(e) => setSettings({ ...settings, api_key: e.target.value })}
                          placeholder="sk-or-v1-..."
                          className="w-full bg-[#3f3f3f] border border-white/10 rounded-lg py-2 pl-10 pr-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div className="pt-4 border-t border-white/5 flex gap-3">
                  <button
                    onClick={onClose}
                    disabled={isSaving}
                    className="flex-1 px-4 py-2 bg-transparent border border-white/10 hover:bg-white/5 disabled:opacity-50 rounded-lg text-sm text-white transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isSaving || (activeTab === "local" && ollamaHealth === false)}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm text-white font-medium transition-all shadow-lg shadow-blue-900/20"
                  >
                    {isSaving ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    {isSaving ? "Saving..." : "Save Config"}
                  </button>
                </div>
              </>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
