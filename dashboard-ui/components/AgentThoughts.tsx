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
  FileText,
  Search,
  Download,
  Zap,
} from "lucide-react";

interface ThoughtEntry {
  id: string;
  timestamp: Date;
  type:
    | "thought"
    | "action"
    | "observation"
    | "checkpoint"
    | "error"
    | "success";
  agent: "orchestrator" | "cua_presentation" | "cua_product" | "claude_parser";
  content: string;
  details?: string;
}

// Helper to create stable mock timestamps
const createMockTimestamp = (secondsAgo: number): Date => {
  // Use a fixed base time for SSR consistency
  const baseTime = new Date("2024-12-04T10:30:00.000Z");
  return new Date(baseTime.getTime() - secondsAgo * 1000);
};

// Mock thoughts data simulating real-time agent activity
const initialMockThoughts: ThoughtEntry[] = [
  {
    id: "1",
    timestamp: createMockTimestamp(45),
    type: "checkpoint",
    agent: "orchestrator",
    content: "Pipeline initiated for presentation 500183020",
    details: "Client: Sarah Johnson | Platform: ESP",
  },
  {
    id: "2",
    timestamp: createMockTimestamp(42),
    type: "thought",
    agent: "orchestrator",
    content: "Analyzing presentation URL structure...",
    details: "Detected ESP portal format with accessCode parameter",
  },
  {
    id: "3",
    timestamp: createMockTimestamp(40),
    type: "action",
    agent: "cua_presentation",
    content: "Navigating to presentation portal",
    details: "URL: https://portal.mypromooffice.com/presentations/500183020",
  },
  {
    id: "4",
    timestamp: createMockTimestamp(35),
    type: "observation",
    agent: "cua_presentation",
    content: "Page loaded successfully - detected 25 products in presentation",
  },
  {
    id: "5",
    timestamp: createMockTimestamp(32),
    type: "action",
    agent: "cua_presentation",
    content: "Clicking 'Download PDF' button",
    details: "Element found at coordinates (1245, 89)",
  },
  {
    id: "6",
    timestamp: createMockTimestamp(28),
    type: "success",
    agent: "cua_presentation",
    content: "Presentation PDF downloaded successfully",
    details: "File size: 2.4 MB | Pages: 28",
  },
  {
    id: "7",
    timestamp: createMockTimestamp(25),
    type: "checkpoint",
    agent: "orchestrator",
    content: "Step 2 complete - Starting presentation parsing",
  },
  {
    id: "8",
    timestamp: createMockTimestamp(22),
    type: "thought",
    agent: "claude_parser",
    content: "Analyzing PDF structure using Claude Opus 4.5...",
    details: "Extracting product information from 28 pages",
  },
  {
    id: "9",
    timestamp: createMockTimestamp(18),
    type: "observation",
    agent: "claude_parser",
    content: "Identified 25 unique products with CPNs",
    details: "Vendors detected: A Plus Wine Designs, Prime Line, Hit Promo",
  },
  {
    id: "10",
    timestamp: createMockTimestamp(15),
    type: "success",
    agent: "claude_parser",
    content: "Presentation parsing complete",
    details: "25 products extracted with full metadata",
  },
  {
    id: "11",
    timestamp: createMockTimestamp(12),
    type: "checkpoint",
    agent: "orchestrator",
    content: "Step 3 starting - Sequential product lookup (1/25)",
  },
  {
    id: "12",
    timestamp: createMockTimestamp(10),
    type: "action",
    agent: "cua_product",
    content: "Opening Firefox and navigating to ESP+",
    details: "Target: CPN-564949909 (Wine Opener Deluxe)",
  },
  {
    id: "13",
    timestamp: createMockTimestamp(7),
    type: "observation",
    agent: "cua_product",
    content: "ESP+ login page detected - checking session status",
  },
  {
    id: "14",
    timestamp: createMockTimestamp(5),
    type: "thought",
    agent: "cua_product",
    content: "Session active from previous run - proceeding to search",
  },
  {
    id: "15",
    timestamp: createMockTimestamp(3),
    type: "action",
    agent: "cua_product",
    content: "Entering product search query: CPN-564949909",
  },
  {
    id: "16",
    timestamp: createMockTimestamp(1),
    type: "thought",
    agent: "cua_product",
    content: "Waiting for search results to load...",
    details: "Expected: Product details page with distributor report option",
  },
];

interface AgentThoughtsProps {
  className?: string;
}

export default function AgentThoughts({ className }: AgentThoughtsProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [thoughts, setThoughts] = useState<ThoughtEntry[]>(initialMockThoughts);
  const [isStreaming, setIsStreaming] = useState(true);
  const [isMounted, setIsMounted] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Handle client-side mounting
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Auto-scroll to bottom when new thoughts arrive
  useEffect(() => {
    if (scrollRef.current && !isCollapsed) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts, isCollapsed]);

  // Simulate new thoughts coming in
  useEffect(() => {
    if (!isStreaming) return;

    const newThoughts: ThoughtEntry[] = [
      {
        id: "sim_1",
        timestamp: new Date(),
        type: "observation",
        agent: "cua_product",
        content: "Search results loaded - found matching product",
      },
      {
        id: "sim_2",
        timestamp: new Date(),
        type: "action",
        agent: "cua_product",
        content: "Clicking on product to view details",
      },
      {
        id: "sim_3",
        timestamp: new Date(),
        type: "thought",
        agent: "cua_product",
        content: "Looking for 'Print' button to generate distributor report...",
      },
    ];

    let index = 0;
    const interval = setInterval(() => {
      if (index < newThoughts.length) {
        setThoughts((prev) => [
          ...prev,
          {
            ...newThoughts[index],
            id: `live_${Date.now()}`,
            timestamp: new Date(),
          },
        ]);
        index++;
      }
    }, 4000);

    return () => clearInterval(interval);
  }, [isStreaming]);

  const getTypeIcon = (type: ThoughtEntry["type"]) => {
    switch (type) {
      case "thought":
        return <Brain className="w-3.5 h-3.5" />;
      case "action":
        return <MousePointer2 className="w-3.5 h-3.5" />;
      case "observation":
        return <Eye className="w-3.5 h-3.5" />;
      case "checkpoint":
        return <Zap className="w-3.5 h-3.5" />;
      case "error":
        return <AlertCircle className="w-3.5 h-3.5" />;
      case "success":
        return <CheckCircle2 className="w-3.5 h-3.5" />;
    }
  };

  const getTypeStyles = (type: ThoughtEntry["type"]) => {
    switch (type) {
      case "thought":
        return "text-violet-400 bg-violet-500/10 border-violet-500/20";
      case "action":
        return "text-blue-400 bg-blue-500/10 border-blue-500/20";
      case "observation":
        return "text-cyan-400 bg-cyan-500/10 border-cyan-500/20";
      case "checkpoint":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "error":
        return "text-red-400 bg-red-500/10 border-red-500/20";
      case "success":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
    }
  };

  const getAgentLabel = (agent: ThoughtEntry["agent"]) => {
    switch (agent) {
      case "orchestrator":
        return "Orchestrator";
      case "cua_presentation":
        return "CUA: Presentation";
      case "cua_product":
        return "CUA: Product";
      case "claude_parser":
        return "Claude Parser";
    }
  };

  const getAgentColor = (agent: ThoughtEntry["agent"]) => {
    switch (agent) {
      case "orchestrator":
        return "text-purple-400";
      case "cua_presentation":
        return "text-emerald-400";
      case "cua_product":
        return "text-blue-400";
      case "claude_parser":
        return "text-orange-400";
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
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
              Chain of Thought • Live
            </span>
          </div>
          {/* Streaming indicator */}
          {isStreaming && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse" />
              STREAMING
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
                      thought.type
                    )}`}
                  >
                    {getTypeIcon(thought.type)}
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
                    {thought.details && (
                      <p className="text-muted-foreground/70 text-[10px] pl-0">
                        → {thought.details}
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
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Collapsed State */}
      {isCollapsed && (
        <div className="px-4 py-3 text-xs text-muted-foreground flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Loader2 className="w-3 h-3 animate-spin text-violet-400" />
            <span>
              {thoughts[thoughts.length - 1]?.content.slice(0, 60)}...
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
