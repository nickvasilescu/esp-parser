"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export type AgentType =
  | "orchestrator"
  | "cua_presentation"
  | "cua_product"
  | "claude_parser"
  | "sage_api"
  | "zoho_item_agent"
  | "zoho_quote_agent"
  | "calculator_agent";

export type EventType =
  | "thought"
  | "action"
  | "observation"
  | "checkpoint"
  | "tool_use"
  | "error"
  | "success";

export interface ThoughtEntry {
  id: string;
  timestamp: string;
  job_id: string;
  agent: AgentType;
  event_type: EventType;
  content: string;
  details?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

interface ThoughtsResponse {
  thoughts: ThoughtEntry[];
  total_lines: number;
  next_offset: number;
  error?: string;
}

/**
 * Hook to poll for agent thoughts from the backend.
 *
 * Fetches new thoughts incrementally using offset-based pagination.
 * New thoughts are appended to the existing array.
 */
export function useThoughtsPolling(
  jobId: string | null,
  pollInterval: number = 1500
) {
  const [thoughts, setThoughts] = useState<ThoughtEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastOffsetRef = useRef(0);
  const previousJobIdRef = useRef<string | null>(null);

  const fetchThoughts = useCallback(async () => {
    if (!jobId) return;

    try {
      const response = await fetch(
        `/api/jobs/${jobId}/thoughts?after=${lastOffsetRef.current}&limit=50`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to fetch thoughts`);
      }

      const data: ThoughtsResponse = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      if (data.thoughts.length > 0) {
        setThoughts((prev) => [...prev, ...data.thoughts]);
        lastOffsetRef.current = data.next_offset;
      }

      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error";
      // Only log error, don't set error state for common "file not found" scenarios
      if (!errorMessage.includes("404")) {
        setError(errorMessage);
      }
    }
  }, [jobId]);

  // Reset when job changes
  useEffect(() => {
    if (jobId !== previousJobIdRef.current) {
      setThoughts([]);
      lastOffsetRef.current = 0;
      setError(null);
      previousJobIdRef.current = jobId;
    }
  }, [jobId]);

  // Start polling when jobId is available
  useEffect(() => {
    if (!jobId) {
      return;
    }

    setIsLoading(true);
    fetchThoughts().finally(() => setIsLoading(false));

    const interval = setInterval(fetchThoughts, pollInterval);
    return () => clearInterval(interval);
  }, [jobId, fetchThoughts, pollInterval]);

  const clearThoughts = useCallback(() => {
    setThoughts([]);
    lastOffsetRef.current = 0;
  }, []);

  return { thoughts, isLoading, error, clearThoughts };
}

export default useThoughtsPolling;
