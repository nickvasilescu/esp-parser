"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Sparkles,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Eye,
  MousePointer2,
  Zap,
  Wrench,
} from "lucide-react";
import { useActiveJob } from "../hooks/useActiveJob";
import {
  useThoughtsPolling,
  ThoughtEntry,
  AgentType,
  EventType,
} from "../hooks/useThoughtsPolling";

interface AgentThoughtsProps {
  className?: string;
}

export default function AgentThoughts({ className }: AgentThoughtsProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Get active job and poll for its thoughts
  const { activeJobId, isStale } = useActiveJob();
  const { thoughts, isLoading, error } = useThoughtsPolling(activeJobId);

  const isStreaming = activeJobId !== null && thoughts.length > 0 && !isStale;

  // Auto-scroll to bottom when new thoughts arrive
  useEffect(() => {
    if (scrollRef.current && !isCollapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts, isCollapsed]);

  const getTypeIcon = (type: EventType) => {
    switch (type) {
      case "thought":
        return <Brain className="w-3.5 h-3.5" />;
      case "action":
        return <MousePointer2 className="w-3.5 h-3.5" />;
      case "observation":
        return <Eye className="w-3.5 h-3.5" />;
      case "checkpoint":
        return <Zap className="w-3.5 h-3.5" />;
      case "tool_use":
        return <Wrench className="w-3.5 h-3.5" />;
      case "error":
        return <AlertCircle className="w-3.5 h-3.5" />;
      case "success":
        return <CheckCircle2 className="w-3.5 h-3.5" />;
      default:
        return <Brain className="w-3.5 h-3.5" />;
    }
  };

  const getTypeStyles = (type: EventType) => {
    switch (type) {
      case "thought":
        return "text-violet-400 bg-violet-500/10 border-violet-500/20";
      case "action":
        return "text-blue-400 bg-blue-500/10 border-blue-500/20";
      case "observation":
        return "text-cyan-400 bg-cyan-500/10 border-cyan-500/20";
      case "checkpoint":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "tool_use":
        return "text-indigo-400 bg-indigo-500/10 border-indigo-500/20";
      case "error":
        return "text-red-400 bg-red-500/10 border-red-500/20";
      case "success":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      default:
        return "text-gray-400 bg-gray-500/10 border-gray-500/20";
    }
  };

  const getAgentLabel = (agent: AgentType) => {
    switch (agent) {
      case "orchestrator":
        return "Orchestrator";
      case "cua_presentation":
        return "CUA: Presentation";
      case "cua_product":
        return "CUA: Product";
      case "claude_parser":
        return "Claude Parser";
      case "sage_api":
        return "SAGE API";
      case "zoho_item_agent":
        return "Zoho: Items";
      case "zoho_quote_agent":
        return "Zoho: Quote";
      case "calculator_agent":
        return "Calculator";
      default:
        return agent;
    }
  };

  const getAgentColor = (agent: AgentType) => {
    switch (agent) {
      case "orchestrator":
        return "text-purple-400";
      case "cua_presentation":
        return "text-emerald-400";
      case "cua_product":
        return "text-blue-400";
      case "claude_parser":
        return "text-orange-400";
      case "sage_api":
        return "text-teal-400";
      case "zoho_item_agent":
        return "text-rose-400";
      case "zoho_quote_agent":
        return "text-pink-400";
      case "calculator_agent":
        return "text-yellow-400";
      default:
        return "text-gray-400";
    }
  };

  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch {
      return "--:--:--";
    }
  };

  const formatDetails = (thought: ThoughtEntry): string | null => {
    if (thought.details) {
      return Object.entries(thought.details)
        .map(([key, value]) => `${key}: ${value}`)
        .join(" | ");
    }
    if (thought.metadata) {
      return Object.entries(thought.metadata)
        .map(([key, value]) => `${key}: ${value}`)
        .join(" | ");
    }
    return null;
  };

  return (
    <div
      className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${
        className || ""
      }`}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-violet-500/10 rounded-md border border-violet-500/20">
            <Sparkles className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <span className="text-sm font-semibold text-foreground block">
              Agent Reasoning Stream
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
              {activeJobId
                ? `Job: ${activeJobId.slice(0, 12)}...`
                : "No active job"}
            </span>
          </div>
          {/* Streaming indicator */}
          {isStreaming && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
              LIVE
            </div>
          )}
          {isStale && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              STALE
            </div>
          )}
          {isLoading && !isStreaming && !isStale && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
              <Loader2 className="w-3 h-3 animate-spin" />
              LOADING
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Entry count */}
          <span className="text-xs text-muted-foreground font-mono">
            {thoughts.length} entries
          </span>
          {/* Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-2 hover:bg-background rounded-md text-muted-foreground hover:text-foreground transition-colors"
            title={isCollapsed ? "Expand" : "Collapse"}
          >
            {isCollapsed ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronUp className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div
              ref={scrollRef}
              className="max-h-[300px] overflow-y-auto p-3 space-y-2 font-mono text-xs bg-black/20"
            >
              {thoughts.length === 0 && !isLoading && (
                <div className="text-center text-muted-foreground py-8">
                  <Brain className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  <p>No agent activity yet</p>
                  <p className="text-[10px] mt-1">
                    Thoughts will appear here when a job starts
                  </p>
                </div>
              )}

              {thoughts.map((thought, index) => (
                <motion.div
                  key={thought.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{
                    duration: 0.2,
                    delay: index > thoughts.length - 4 ? 0.1 : 0,
                  }}
                  className="flex gap-2"
                >
                  {/* Timestamp */}
                  <span className="text-muted-foreground/50 shrink-0 w-16">
                    {formatTime(thought.timestamp)}
                  </span>

                  {/* Type badge */}
                  <div
                    className={`shrink-0 p-1 rounded border ${getTypeStyles(
                      thought.event_type
                    )}`}
                  >
                    {getTypeIcon(thought.event_type)}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span
                        className={`font-semibold ${getAgentColor(
                          thought.agent
                        )}`}
                      >
                        [{getAgentLabel(thought.agent)}]
                      </span>
                      <span className="text-foreground">{thought.content}</span>
                    </div>
                    {formatDetails(thought) && (
                      <p className="text-muted-foreground/70 text-[10px] pl-0">
                        → {formatDetails(thought)}
                      </p>
                    )}
                  </div>
                </motion.div>
              ))}

              {/* Typing indicator when streaming */}
              {isStreaming && (
                <div className="flex items-center gap-2 text-muted-foreground/50 pt-2">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  <span className="text-[10px]">Agent processing...</span>
                </div>
              )}

              {/* Error display */}
              {error && (
                <div className="flex items-center gap-2 text-red-400 pt-2">
                  <AlertCircle className="w-3 h-3" />
                  <span className="text-[10px]">{error}</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Collapsed State */}
      {isCollapsed && (
        <div className="px-4 py-3 text-xs text-muted-foreground flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isStreaming && (
              <Loader2 className="w-3 h-3 animate-spin text-violet-400" />
            )}
            {isStale && (
              <span className="w-2 h-2 rounded-full bg-amber-500" />
            )}
            <span>
              {thoughts.length > 0
                ? thoughts[thoughts.length - 1]?.content.slice(0, 60) + "..."
                : "No agent activity"}
            </span>
          </div>
          <span className="text-[10px] text-muted-foreground/60">
            Click to expand
          </span>
        </div>
      )}
    </div>
  );
}
