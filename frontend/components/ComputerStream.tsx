"use client";

import React, { useState } from "react";
import { ComputerDisplay } from "orgo-vnc";
import { Monitor, Wifi, WifiOff, Maximize2, Minimize2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface ComputerStreamProps {
  className?: string;
  host?: string;
  password?: string;
  label?: string;
  onConnectionChange?: (connected: boolean) => void;
}

export default function ComputerStream({
  className,
  host = process.env.NEXT_PUBLIC_ORGO_COMPUTER_HOST || "",
  password = process.env.NEXT_PUBLIC_ORGO_COMPUTER_PASSWORD || "",
  label,
  onConnectionChange,
}: ComputerStreamProps) {
  const [connected, setConnected] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleConnect = () => {
    setConnected(true);
    onConnectionChange?.(true);
  };

  const handleDisconnect = () => {
    setConnected(false);
    onConnectionChange?.(false);
  };

  // Common wrapper style for expanded vs normal state
  // Using 4:3 aspect ratio to match Orgo VM resolution (1024x768)
  const wrapperStyle = expanded
    ? "fixed inset-4 z-50 shadow-2xl w-full h-full max-w-[1280px] mx-auto max-h-[90vh]"
    : `aspect-[4/3] ${className}`;

  const inlineStyle = expanded ? { aspectRatio: "4/3" } : undefined;

  // If no credentials are provided, show the placeholder image as a demo
  if (!host) {
    const content = (
      <motion.div
        layout
        className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${wrapperStyle}`}
        style={inlineStyle}
      >
        <div className="px-2.5 py-1.5 border-b border-border flex items-center justify-between bg-secondary/30 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-zinc-500/50" />
            <span className="text-xs font-medium text-foreground truncate">
              {label || "VM Stream"}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-background/50 border border-border text-[9px] font-mono text-muted-foreground">
              <WifiOff className="w-2.5 h-2.5" />
              DEMO
            </div>
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 hover:bg-background rounded text-muted-foreground hover:text-foreground transition-colors"
            >
              {expanded ? (
                <Minimize2 className="w-3.5 h-3.5" />
              ) : (
                <Maximize2 className="w-3.5 h-3.5" />
              )}
            </button>
          </div>
        </div>

        <div className="flex-1 bg-black relative min-h-0">
          {/* Placeholder Image as Demo */}
          <div className="absolute inset-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/images/vm-placeholder.jpg"
              alt="VM Demo"
              className="w-full h-full object-cover"
            />
          </div>
          {/* Demo overlay */}
          <div className="absolute inset-0 bg-black/20 flex items-end justify-center pb-4">
            <div className="px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full text-[10px] text-white/70 font-mono">
              Demo Mode - No VNC Connected
            </div>
          </div>
        </div>
      </motion.div>
    );

    if (expanded) {
      return (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8"
          onClick={() => setExpanded(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full flex justify-center"
          >
            {content}
          </div>
        </div>
      );
    }

    return content;
  }

  // Live VNC Stream View
  const content = (
    <motion.div
      layout
      className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${wrapperStyle}`}
      style={inlineStyle}
    >
      <div className="px-2.5 py-1.5 border-b border-border flex items-center justify-between bg-secondary/30 shrink-0">
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              connected
                ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.4)]"
                : "bg-amber-500/50 animate-pulse"
            }`}
          />
          <span className="text-xs font-medium text-foreground truncate">
            {connected
              ? label
                ? label
                : host
              : label
              ? `${label}...`
              : "Connecting..."}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-background/50 border border-border text-[9px] font-mono text-muted-foreground">
            {connected ? (
              <Wifi className="w-2.5 h-2.5" />
            ) : (
              <WifiOff className="w-2.5 h-2.5" />
            )}
            {connected ? "LIVE" : "..."}
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1 hover:bg-background rounded text-muted-foreground hover:text-foreground transition-colors"
          >
            {expanded ? (
              <Minimize2 className="w-3.5 h-3.5" />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      <div className="flex-1 bg-black relative min-h-0">
        {/* Background Placeholder Image */}
        <div className="absolute inset-0 z-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/vm-placeholder.jpg"
            alt="VM Background"
            className="w-full h-full object-cover opacity-50"
          />
        </div>

        {/* Actual VNC Display */}
        <div className="relative z-10 h-full w-full">
          <ComputerDisplay
            hostname={host}
            password={password}
            background="#000000"
            readOnly={true} // Always read-only for dashboard view
            onConnect={handleConnect}
            onDisconnect={handleDisconnect}
            scaleViewport={true}
            clipViewport={false}
            qualityLevel={8}
            compressionLevel={2}
          />
        </div>

        {/* Overlay when disconnected */}
        <AnimatePresence>
          {!connected && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 flex items-center justify-center bg-black/50 backdrop-blur-sm z-20"
            >
              <div className="flex flex-col items-center gap-2">
                <Loader />
                <p className="text-xs text-white/70">Connecting...</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );

  if (expanded) {
    return (
      <div
        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 sm:p-8"
        onClick={() => setExpanded(false)}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className="w-full flex justify-center"
        >
          {content}
        </div>
      </div>
    );
  }

  return content;
}

function Loader() {
  return (
    <div className="relative w-6 h-6">
      <div className="absolute inset-0 border-2 border-emerald-500/20 rounded-full"></div>
      <div className="absolute inset-0 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
  );
}
