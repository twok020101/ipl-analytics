"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { fetchAIChat } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { BrainCircuit, Send, Loader2, User, Bot, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const exampleQuestions = [
  "How does Virat Kohli perform against spin?",
  "Which venue favors batting the most?",
  "Compare CSK and MI historically",
  "Who are the best death bowlers in IPL?",
  "What is the best batting strategy at Wankhede?",
  "Which team performs best while chasing?",
];

export default function AIInsightsPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const chatMutation = useMutation({
    mutationFn: fetchAIChat,
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || data.preview || data.report || "No response", timestamp: new Date() },
      ]);
    },
    onError: () => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "I apologize, but the AI service is currently unavailable. Please ensure the API server is running and try again.",
          timestamp: new Date(),
        },
      ]);
    },
  });

  const handleSend = (question?: string) => {
    const q = question || input.trim();
    if (!q) return;

    setMessages((prev) => [...prev, { role: "user", content: q, timestamp: new Date() }]);
    setInput("");
    chatMutation.mutate(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BrainCircuit className="h-6 w-6 text-purple-400" />
          AI Insights
        </h1>
        <p className="text-muted-foreground mt-1">
          Ask any question about IPL cricket and get intelligent answers
        </p>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-purple-500/10 mb-4">
              <Sparkles className="h-8 w-8 text-purple-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Ask me anything about IPL</h2>
            <p className="text-muted-foreground text-sm mb-6 text-center max-w-md">
              I can answer questions about player performance, team statistics, match predictions, and strategic insights.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-2xl">
              {exampleQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="text-left p-3 rounded-xl border border-border bg-card text-sm text-muted-foreground hover:text-foreground hover:border-border-strong hover:bg-muted transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            className={cn(
              "flex gap-3 max-w-3xl animate-fade-in",
              msg.role === "user" ? "ml-auto flex-row-reverse" : ""
            )}
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                msg.role === "user" ? "bg-primary/10" : "bg-purple-500/10"
              )}
            >
              {msg.role === "user" ? (
                <User className="h-4 w-4 text-primary" />
              ) : (
                <Bot className="h-4 w-4 text-purple-400" />
              )}
            </div>
            <div
              className={cn(
                "rounded-2xl px-4 py-3 max-w-[80%]",
                msg.role === "user"
                  ? "bg-primary text-white"
                  : "bg-muted text-foreground"
              )}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
              <p className="text-[10px] opacity-50 mt-1">
                {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
            </div>
          </div>
        ))}

        {chatMutation.isPending && (
          <div className="flex gap-3 max-w-3xl animate-fade-in">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-purple-500/10">
              <Bot className="h-4 w-4 text-purple-400" />
            </div>
            <div className="bg-muted rounded-2xl px-4 py-3">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Thinking...
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-border pt-4">
        <div className="flex items-center gap-3 max-w-3xl mx-auto">
          <Input
            placeholder="Ask about IPL stats, players, teams..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1"
            disabled={chatMutation.isPending}
          />
          <Button
            onClick={() => handleSend()}
            disabled={!input.trim() || chatMutation.isPending}
            size="icon"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
