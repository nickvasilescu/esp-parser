"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Monitor,
  ChevronDown,
  ChevronUp,
  Maximize2,
  Minimize2,
  Wifi,
  WifiOff,
} from "lucide-react";
import ComputerStream from "./ComputerStream";

interface VMPanelProps {
  className?: string;
}

export default function VMPanel({ className }: VMPanelProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  const vmHost = process.env.NEXT_PUBLIC_ORGO_COMPUTER_HOST || "";
  const vmPassword = process.env.NEXT_PUBLIC_ORGO_COMPUTER_PASSWORD || "";

  return (
    <div
      className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${className}`}
    >
      {/* Panel Header */}
      <div className="px-4 py-3 border-b border-border bg-secondary/30 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-background/50 rounded-md border border-border">
            <Monitor className="w-4 h-4 text-emerald-500" />
          </div>
          <div>
            <span className="text-sm font-semibold text-foreground block">
              Orgo CUA Agent
            </span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Linux VM Stream
            </span>
          </div>
          {/* Connection Status */}
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-medium ${
              isConnected
                ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                : "bg-zinc-500/10 text-zinc-400 border border-zinc-500/20"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isConnected
                  ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)] animate-pulse"
                  : "bg-zinc-500"
              }`}
            />
            {isConnected ? "LIVE" : "OFFLINE"}
          </div>
        </div>

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
              <ComputerStream
                host={vmHost}
                password={vmPassword}
                label="Orgo CUA"
                className="w-full"
                onConnectionChange={(connected) => setIsConnected(connected)}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Collapsed State Indicator */}
      {isCollapsed && (
        <div className="px-4 py-3 text-xs text-muted-foreground flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                isConnected ? "bg-emerald-500 animate-pulse" : "bg-zinc-500"
              }`}
            />
            <span
              className={
                isConnected ? "text-foreground" : "text-muted-foreground"
              }
            >
              {isConnected ? "CUA Agent Active" : "CUA Agent Offline"}
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
