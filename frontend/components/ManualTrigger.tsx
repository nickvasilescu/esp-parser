"use client";

import React, { useState } from "react";
import { Play, Loader2, CheckCircle, AlertCircle } from "lucide-react";

const ESP_PATTERN = /^https:\/\/portal\.mypromooffice\.com\/presentations\/\d+\?accessCode=[a-f0-9]+$/;
const SAGE_PATTERN = /^https:\/\/www\.viewpresentation\.com\/\d+$/;

type Status = "idle" | "loading" | "success" | "error";

export default function ManualTrigger() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  function detectPlatform(u: string): string | null {
    if (ESP_PATTERN.test(u.trim())) return "ESP";
    if (SAGE_PATTERN.test(u.trim())) return "SAGE";
    return null;
  }

  async function handleTrigger() {
    const trimmed = url.trim();
    if (!trimmed) return;

    const platform = detectPlatform(trimmed);
    if (!platform) {
      setStatus("error");
      setMessage("Invalid URL. Must be an ESP or SAGE presentation link.");
      return;
    }

    setStatus("loading");
    setMessage("");

    try {
      const res = await fetch("/api/workflows/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });

      const data = await res.json();

      if (res.ok) {
        setStatus("success");
        setMessage(`${data.platform} workflow started`);
        setUrl("");
        // Reset after a few seconds
        setTimeout(() => {
          setStatus("idle");
          setMessage("");
        }, 4000);
      } else {
        setStatus("error");
        setMessage(data.error || "Failed to trigger workflow");
      }
    } catch {
      setStatus("error");
      setMessage("Network error — is the server running?");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && status !== "loading") {
      handleTrigger();
    }
  }

  const platform = url.trim() ? detectPlatform(url.trim()) : null;

  return (
    <div className="bg-card rounded-lg border border-border p-3 mb-4">
      <div className="flex items-center gap-3">
        <div className="flex-1 relative">
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (status === "error") setStatus("idle");
            }}
            onKeyDown={handleKeyDown}
            placeholder="Paste ESP or SAGE presentation URL..."
            className="w-full bg-secondary text-foreground text-sm rounded-md px-3 py-2 pr-16 border border-border focus:outline-none focus:ring-1 focus:ring-primary placeholder:text-muted-foreground"
            disabled={status === "loading"}
          />
          {platform && status === "idle" && (
            <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground bg-background px-1.5 py-0.5 rounded">
              {platform}
            </span>
          )}
        </div>
        <button
          onClick={handleTrigger}
          disabled={!url.trim() || status === "loading"}
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {status === "loading" ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          Run Workflow
        </button>
      </div>
      {message && (
        <div
          className={`flex items-center gap-1.5 mt-2 text-xs ${
            status === "success"
              ? "text-emerald-500"
              : status === "error"
              ? "text-red-400"
              : "text-muted-foreground"
          }`}
        >
          {status === "success" && <CheckCircle className="w-3 h-3" />}
          {status === "error" && <AlertCircle className="w-3 h-3" />}
          {message}
        </div>
      )}
    </div>
  );
}
