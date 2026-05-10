"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Quiz } from "../lib/api";
import { useState } from "react";

interface QuizOverlayProps {
  quiz: Quiz | null;
  onClose: () => void;
  onSubmit: (quizId: string, answers: Record<string, string>) => void;
}

export default function QuizOverlay({
  quiz,
  onClose,
  onSubmit,
}: QuizOverlayProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [isSubmitted, setIsSubmitted] = useState(false);

  if (!quiz || !quiz.questions || quiz.questions.length === 0) return null;

  const currentQuestion = quiz.questions[currentIndex];
  if (!currentQuestion) return null;

  const isLastQuestion = currentIndex === quiz.questions.length - 1;
  const isFirstQuestion = currentIndex === 0;

  // Guard against null options
  const options = currentQuestion.options || [];
  const hasOptions = options.length > 0;

  const handleNext = () => {
    if (isLastQuestion) {
      setIsSubmitted(true);
      onSubmit(quiz.id, answers);
    } else {
      setCurrentIndex((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    if (isFirstQuestion) {
      onClose();
    } else {
      setCurrentIndex((prev) => prev - 1);
    }
  };

  const handleSelectOption = (option: string) => {
    if (isSubmitted) return;
    setAnswers((prev) => ({
      ...prev,
      [currentIndex]: option,
    }));
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.95 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        className="w-full bg-[#1e1e1e] rounded-xl border border-white/10 shadow-2xl overflow-hidden flex flex-col"
        style={{
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7)",
        }}
      >
        {/* Header */}
        <div className="px-5 py-3 border-b border-white/5 bg-[#252525] flex items-center justify-between">
          <h3 className="text-[var(--color-foreground)] font-medium text-sm">
            Question {currentIndex + 1} of {quiz.questions.length}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white text-xs transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-5 flex-1">
          <p className="text-[var(--color-foreground)] font-medium mb-4">
            {currentQuestion.question}
          </p>

          {hasOptions ? (
            <div className="space-y-2.5">
              {options.map((option, idx) => {
                const isSelected = answers[currentIndex] === option;

                return (
                  <div
                    key={idx}
                    onClick={() => handleSelectOption(option)}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all border ${
                      isSubmitted
                        ? "cursor-not-allowed opacity-60 border-white/5 bg-white/[0.02]"
                        : isSelected
                        ? "cursor-pointer border-blue-500/50 bg-blue-500/10"
                        : "cursor-pointer border-white/5 bg-white/[0.02] hover:bg-white/5 hover:border-white/10"
                    }`}
                  >
                    <div className="relative flex items-center justify-center">
                      <div
                        className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${
                          isSelected
                            ? "border-blue-400 bg-blue-400"
                            : "border-gray-500 group-hover:border-gray-400"
                        }`}
                      >
                        {isSelected && (
                          <div className="w-1.5 h-1.5 rounded-full bg-white"></div>
                        )}
                      </div>
                    </div>
                    <span
                      className={`text-sm ${
                        isSelected
                          ? "text-white font-medium"
                          : "text-gray-300"
                      }`}
                    >
                      {option}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            /* Open-ended question — text input */
            <div className="mt-2">
              <textarea
                value={answers[currentIndex] || ""}
                onChange={(e) =>
                  setAnswers((prev) => ({
                    ...prev,
                    [currentIndex]: e.target.value,
                  }))
                }
                placeholder="Type your answer..."
                disabled={isSubmitted}
                className="w-full bg-[#2a2a2a] border border-white/10 rounded-lg p-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-white/20 resize-none disabled:opacity-60 disabled:cursor-not-allowed"
                rows={3}
              />
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`px-5 py-3 flex items-center justify-between border-t border-white/5 bg-[#1a1a1a] ${
          isSubmitted ? "opacity-50 pointer-events-none" : ""
        }`}>
          <button
            onClick={handleBack}
            className="px-4 py-1.5 bg-[#333] hover:bg-[#444] text-[var(--color-foreground)] text-sm rounded-md transition-colors"
          >
            {isFirstQuestion ? "Cancel" : "Back"}
          </button>

          {/* Pagination Dots */}
          <div className="flex items-center gap-1.5">
            {quiz.questions.map((_, idx) => (
              <div
                key={idx}
                className={`h-1.5 rounded-full transition-all ${
                  idx === currentIndex
                    ? "bg-blue-400 w-4"
                    : idx < currentIndex && answers[idx]
                    ? "bg-green-400 w-1.5"
                    : "bg-gray-600 w-1.5"
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            disabled={!answers[currentIndex] || isSubmitted}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
              answers[currentIndex] && !isSubmitted
                ? isLastQuestion
                  ? "bg-green-600 hover:bg-green-500 text-white font-medium"
                  : "bg-blue-600 hover:bg-blue-500 text-white"
                : "bg-[#222] text-gray-500 cursor-not-allowed"
            }`}
          >
            {isLastQuestion ? (isSubmitted ? "Submitting..." : "Submit") : "Next"}
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
