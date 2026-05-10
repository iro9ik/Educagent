"use client";

import {
  ArrowUp,
  Brain,
  FileText,
  Globe2,
  Loader2,
  Plus,
  Square,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent, ReactNode } from "react";
import QuizOverlay from "./QuizOverlay";
import { api, Quiz } from "../lib/api";

interface SendOptions {
  searchEnabled: boolean;
  thinkingEnabled: boolean;
  attachedFiles: string[];
}

interface InputAreaProps {
  onSendMessage: (message: string, options: SendOptions) => void;
  uploadedFiles: string[];
  onFilesUploaded: () => void;
  isStreaming: boolean;
  isQuizLoading: boolean;
  isQuizGrading: boolean;
  activeQuiz: Quiz | null;
  onQuizSubmit: (quizId: string, answers: Record<string, string>) => void;
  onQuizClose: () => void;
  onGenerateQuiz: (topic: string, attachedFiles?: string[]) => void;
  onStopGeneration: () => void;
}

function CircularProgress({ progress, size = 32 }: { progress: number; size?: number }) {
  const strokeWidth = size / 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg className="absolute inset-0 transform -rotate-90" width={size} height={size}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="text-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          style={{ strokeDashoffset: offset }}
          strokeLinecap="round"
          className="text-red-500 transition-all duration-300"
        />
      </svg>
      <FileText style={{ width: size * 0.4, height: size * 0.4 }} className="text-white" />
    </div>
  );
}

export default function InputArea({
  onSendMessage,
  uploadedFiles,
  onFilesUploaded,
  isStreaming,
  isQuizLoading,
  isQuizGrading,
  activeQuiz,
  onQuizSubmit,
  onQuizClose,
  onGenerateQuiz,
  onStopGeneration,
}: InputAreaProps) {
  const [input, setInput] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [searchEnabled, setSearchEnabled] = useState(false);
  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isUploading) {
      setUploadProgress(0);
      interval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + 5;
        });
      }, 200);
    } else {
      setUploadProgress(100);
    }
    return () => clearInterval(interval);
  }, [isUploading]);

  const isQuizCommand = input.trimStart().toLowerCase().startsWith("/quiz ");

  const resizeTextarea = () => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
  };

  const handleInput = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    resizeTextarea();
  };

  const handleSubmit = async (e?: FormEvent) => {
    e?.preventDefault();
    if (isUploading) return;

    const currentInput = input.trim();
    const isQuiz = isQuizCommand;
    const topic = isQuiz ? currentInput.slice(6).trim() : currentInput;
    const attachedFiles = selectedFiles.map((file) => file.name);

    setInput("");
    setSelectedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    if (isQuiz) {
      onGenerateQuiz(topic || "general", attachedFiles);
      return;
    }

    onSendMessage(topic, {
      searchEnabled,
      thinkingEnabled,
      attachedFiles,
    });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    const newFiles = Array.from(e.target.files);
    setSelectedFiles((prev) => [...prev, ...newFiles]);
    
    setIsUploading(true);
    try {
      await api.uploadDocuments(e.target.files);
      onFilesUploaded();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed";
      console.error(err);
      alert(`Error uploading: ${message}`);
      setSelectedFiles((prev) => prev.filter(f => !newFiles.includes(f)));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const newFiles = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => [...prev, ...newFiles]);
      
      setIsUploading(true);
      try {
        await api.uploadDocuments(e.dataTransfer.files);
        onFilesUploaded();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Upload failed";
        alert(`Error uploading: ${message}`);
        setSelectedFiles((prev) => prev.filter(f => !newFiles.includes(f)));
      } finally {
        setIsUploading(false);
      }
    }
  };

  const removeFile = async (nameToRemove: string) => {
    setSelectedFiles((prev) => prev.filter((file) => file.name !== nameToRemove));
    try {
      await api.deleteDocument(nameToRemove);
    } catch (err) {
      console.error("Failed to delete document from server:", err);
    }
  };

  const isSendDisabled = (input.trim() === "" && selectedFiles.length === 0) || isStreaming || isUploading || !!activeQuiz || isQuizGrading;

  return (
    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-[var(--color-background)] via-[var(--color-background)] to-transparent pt-10 pb-6 px-4">
      <div className="max-w-3xl mx-auto relative">
        {activeQuiz && (
          <div className="absolute bottom-full left-0 right-0 mb-2">
            <QuizOverlay
              key={activeQuiz.id}
              quiz={activeQuiz}
              onClose={onQuizClose}
              onSubmit={onQuizSubmit}
            />
          </div>
        )}

        {isQuizLoading && (
          <div className="absolute bottom-full left-0 right-0 mb-2 flex items-center justify-center gap-2 py-4 bg-[#1e1e1e] rounded-xl border border-white/10">
            <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
            <span className="text-sm text-gray-400">Generating quiz...</span>
          </div>
        )}

        {isQuizGrading && (
          <div className="absolute bottom-full left-0 right-0 mb-2 flex items-center justify-center gap-2 py-4 bg-[#1e1e1e] rounded-xl border border-white/10">
            <Loader2 className="w-5 h-5 text-green-400 animate-spin" />
            <span className="text-sm text-gray-400">Grading your answers...</span>
          </div>
        )}

        <form
          onSubmit={handleSubmit}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative flex flex-col bg-[#2f2f2f] rounded-2xl shadow-sm border overflow-hidden transition-colors ${
            isDragging ? "border-blue-500 bg-[#353535]" : "border-white/10"
          }`}
        >
          {selectedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 p-3 pb-0">
              {selectedFiles.map((file) => (
                <div
                  key={file.name}
                  className="flex items-center gap-3 bg-[#3f3f3f] border border-white/5 rounded-xl p-2 pr-3 max-w-[220px]"
                >
                  <div className="flex-shrink-0">
                    {isUploading ? (
                      <CircularProgress progress={uploadProgress} />
                    ) : (
                      <div className="w-8 h-8 bg-red-500 rounded-lg flex items-center justify-center">
                        <FileText className="w-4 h-4 text-white" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-white truncate" title={file.name}>
                      {file.name}
                    </p>
                    <p className="text-[10px] text-gray-400 uppercase">
                      {file.name.split('.').pop() || "File"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(file.name)}
                    className="flex-shrink-0 p-1 hover:bg-white/10 rounded-full text-gray-400 hover:text-white transition-colors"
                    title="Remove file"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="flex items-end">
            <div className="flex items-center justify-center p-2 pl-3">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading || !!activeQuiz || isQuizGrading}
                className="p-2 rounded-full hover:bg-white/10 text-gray-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title={`${uploadedFiles.length} uploaded documents`}
              >
                <Plus className="w-5 h-5" />
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".pdf,.docx,.txt,.csv,.json,.md,.pptx"
                multiple
                className="hidden"
              />
            </div>
            <div className="relative flex-1">
              {isQuizCommand && (
                <div className="absolute top-0 left-0 w-full h-full py-4 pr-12 pointer-events-none text-sm whitespace-pre-wrap break-words z-0 font-sans">
                  <span className="bg-blue-500/40 rounded text-transparent">/quiz</span>
                </div>
              )}
              <textarea
                ref={textareaRef}
                value={input}
                onChange={handleInput}
                onKeyDown={handleKeyDown}
                placeholder={
                  isQuizGrading
                    ? "Grading your answers..."
                    : isStreaming
                    ? "AI is responding..."
                    : "Ask anything"
                }
                className="w-full max-h-[200px] py-4 pr-12 bg-transparent text-white placeholder-gray-400 focus:outline-none resize-none m-0 text-sm relative z-10 font-sans disabled:opacity-60 disabled:cursor-not-allowed"
                rows={1}
                disabled={!!activeQuiz || isQuizGrading}
              />
            </div>
            <div className="absolute right-2 bottom-2 flex items-center gap-2">
              {isQuizCommand && (
                <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-medium">
                  Quiz Mode
                </span>
              )}

              {isStreaming ? (
                <button
                  type="button"
                  onClick={onStopGeneration}
                  className="p-2 rounded-full bg-white text-black hover:bg-gray-200 transition-colors"
                  title="Stop generating"
                >
                  <Square className="w-4 h-4 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={isSendDisabled}
                  className={`p-2 rounded-full transition-colors ${
                    !isSendDisabled
                      ? "bg-white text-black hover:bg-gray-200"
                      : "bg-white/10 text-white/40 cursor-not-allowed"
                  }`}
                  title="Send"
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 px-3 pb-3">
            <TogglePill
              active={searchEnabled}
              onClick={() => setSearchEnabled((value) => !value)}
              icon={<Globe2 className="w-3.5 h-3.5" />}
              label="Search"
            />
            <TogglePill
              active={thinkingEnabled}
              onClick={() => setThinkingEnabled((value) => !value)}
              icon={<Brain className="w-3.5 h-3.5" />}
              label="Reason"
            />
          </div>
        </form>
        <div className="text-center text-xs text-gray-500 mt-3">
          EducAgent beta version
        </div>
      </div>
    </div>
  );
}

function TogglePill({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors ${
        active
          ? "toggle-pill-active text-white"
          : "border-white/10 bg-black/10 text-gray-400 hover:text-white"
      }`}
      aria-pressed={active}
    >
      {icon}
      {label}
    </button>
  );
}
