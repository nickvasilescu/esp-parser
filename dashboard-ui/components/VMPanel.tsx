"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Monitor, Columns2, ChevronDown, ChevronUp } from "lucide-react";
import ComputerStream from "./ComputerStream";

type ViewMode = "agent1" | "agent2" | "split";

interface AgentStatus {
  agent1: boolean;
  agent2: boolean;
}

interface VMPanelProps {
  className?: string;
}

export default function VMPanel({ className }: VMPanelProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("agent1");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({
    agent1: false,
    agent2: false,
  });

  const agent1Host = process.env.NEXT_PUBLIC_ORGO_COMPUTER_HOST || "";
  const agent1Password = process.env.NEXT_PUBLIC_ORGO_COMPUTER_PASSWORD || "";
  const agent2Host = process.env.NEXT_PUBLIC_ORGO_COMPUTER_HOST_2 || agent1Host;
  const agent2Password = process.env.NEXT_PUBLIC_ORGO_COMPUTER_PASSWORD_2 || agent1Password;

  const activeCount = (agentStatus.agent1 ? 1 : 0) + (agentStatus.agent2 ? 1 : 0);

  return (
    <div className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${className}`}>
      {/* Panel Header */}
      <div className="px-3 py-2 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Live VM Streams</span>
          {/* Quick status summary in header */}
          <div className="flex items-center gap-1 ml-1">
            <StatusDot connected={agentStatus.agent1} size="sm" />
            <StatusDot connected={agentStatus.agent2} size="sm" />
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {/* View Mode Tabs */}
          <div className="flex items-center bg-background/50 rounded-md border border-border p-0.5">
            <TabButton 
              active={viewMode === "agent1"} 
              onClick={() => setViewMode("agent1")}
              label="Agent 1"
              connected={agentStatus.agent1}
            />
            <TabButton 
              active={viewMode === "agent2"} 
              onClick={() => setViewMode("agent2")}
              label="Agent 2"
              connected={agentStatus.agent2}
            />
            <button
              onClick={() => setViewMode("split")}
              className={`p-1.5 rounded transition-colors ${
                viewMode === "split" 
                  ? "bg-primary text-primary-foreground" 
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary"
              }`}
              title="Split View"
            >
              <Columns2 className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-1.5 hover:bg-background rounded-md text-muted-foreground hover:text-foreground transition-colors"
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

      {/* Panel Content */}
      <AnimatePresence initial={false}>
        {!isCollapsed && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="p-3">
              {viewMode === "split" ? (
                /* Split View - Two streams side by side */
                <div className="grid grid-cols-2 gap-3">
                  <ComputerStream
                    host={agent1Host}
                    password={agent1Password}
                    label="Agent 1"
                    className="w-full"
                    onConnectionChange={(connected) => 
                      setAgentStatus(prev => ({ ...prev, agent1: connected }))
                    }
                  />
                  <ComputerStream
                    host={agent2Host}
                    password={agent2Password}
                    label="Agent 2"
                    className="w-full"
                    onConnectionChange={(connected) => 
                      setAgentStatus(prev => ({ ...prev, agent2: connected }))
                    }
                  />
                </div>
              ) : (
                /* Single View - Tabbed */
                <AnimatePresence mode="wait">
                  <motion.div
                    key={viewMode}
                    initial={{ opacity: 0, x: viewMode === "agent1" ? -20 : 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: viewMode === "agent1" ? 20 : -20 }}
                    transition={{ duration: 0.15 }}
                  >
                    <ComputerStream
                      host={viewMode === "agent1" ? agent1Host : agent2Host}
                      password={viewMode === "agent1" ? agent1Password : agent2Password}
                      label={viewMode === "agent1" ? "Agent 1" : "Agent 2"}
                      className="w-full max-w-lg mx-auto"
                      onConnectionChange={(connected) => 
                        setAgentStatus(prev => ({ 
                          ...prev, 
                          [viewMode]: connected 
                        }))
                      }
                    />
                  </motion.div>
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Collapsed State Indicator */}
      {isCollapsed && (
        <div className="px-3 py-2 text-xs text-muted-foreground flex items-center gap-4">
          <AgentStatusPill label="Agent 1" connected={agentStatus.agent1} />
          <AgentStatusPill label="Agent 2" connected={agentStatus.agent2} />
          <span className="ml-auto text-[10px] opacity-60">
            {activeCount}/2 active
          </span>
        </div>
      )}
    </div>
  );
}

function StatusDot({ connected, size = "md" }: { connected: boolean; size?: "sm" | "md" }) {
  const sizeClasses = size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2";
  
  return (
    <span
      className={`${sizeClasses} rounded-full transition-colors ${
        connected 
          ? "bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.5)]" 
          : "bg-zinc-500/50"
      }`}
    />
  );
}

function AgentStatusPill({ label, connected }: { label: string; connected: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <StatusDot connected={connected} size="md" />
      <span className={connected ? "text-foreground" : "text-muted-foreground"}>
        {label}
      </span>
      <span className={`text-[10px] ${connected ? "text-emerald-500" : "text-muted-foreground/60"}`}>
        {connected ? "LIVE" : "OFFLINE"}
      </span>
    </div>
  );
}

function TabButton({ 
  active, 
  onClick, 
  label,
  connected 
}: { 
  active: boolean; 
  onClick: () => void; 
  label: string;
  connected: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-xs font-medium rounded transition-colors flex items-center gap-1.5 ${
        active 
          ? "bg-primary text-primary-foreground" 
          : "text-muted-foreground hover:text-foreground hover:bg-secondary"
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          connected 
            ? "bg-emerald-400 shadow-[0_0_4px_rgba(16,185,129,0.6)]" 
            : active 
              ? "bg-primary-foreground/40" 
              : "bg-muted-foreground/40"
        }`}
      />
      {label}
    </button>
  );
}
