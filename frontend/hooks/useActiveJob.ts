"use client";

import { useState, useEffect, useCallback } from "react";

interface JobFromAPI {
  id: string;
  status: string;
  platform: string;
  progress: number;
  current_item: number | null;
  total_items: number | null;
  current_item_name: string | null;
  features: {
    zoho_upload: boolean;
    zoho_quote: boolean;
    calculator: boolean;
  };
  started_at: string;
  updated_at: string;
  presentation_pdf_url: string | null;
  output_json_url: string | null;
  zoho_item_link: string | null;
  zoho_quote_link: string | null;
  calculator_link: string | null;
  errors: string[];
}

/**
 * Hook to track the currently active job (in-progress workflow).
 *
 * Polls the jobs API to find jobs that are not in terminal states
 * (completed, error, partial_success).
 */
export function useActiveJob(pollInterval: number = 2000) {
  const [activeJob, setActiveJob] = useState<JobFromAPI | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [allJobs, setAllJobs] = useState<JobFromAPI[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStale, setIsStale] = useState(false);

  const fetchJobs = useCallback(async () => {
    try {
      const response = await fetch("/api/jobs");
      if (!response.ok) return;

      const data = await response.json();
      const jobs: JobFromAPI[] = data.jobs || [];
      setAllJobs(jobs);

      // Terminal states - these jobs are no longer "active"
      const terminalStates = [
        "completed",
        "error",
        "partial_success",
        "awaiting_qa",
      ];

      // Consider a job "stale" if not updated in 2 minutes (likely terminated abnormally)
      const STALE_THRESHOLD_MS = 2 * 60 * 1000;
      const now = Date.now();

      // Find the first non-terminal job
      const nonTerminalJob = jobs.find((job) => !terminalStates.includes(job.status));

      // Check if that job is stale
      const jobIsStale = nonTerminalJob
        ? now - new Date(nonTerminalJob.updated_at).getTime() > STALE_THRESHOLD_MS
        : false;

      // Only set as active if not stale
      const active = nonTerminalJob && !jobIsStale ? nonTerminalJob : null;

      setActiveJob(active);
      setActiveJobId(active?.id || null);
      setIsStale(jobIsStale);
    } catch (err) {
      console.error("Error fetching jobs:", err);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    setIsLoading(true);
    fetchJobs().finally(() => setIsLoading(false));

    // Poll for changes
    const interval = setInterval(fetchJobs, pollInterval);
    return () => clearInterval(interval);
  }, [fetchJobs, pollInterval]);

  return { activeJob, activeJobId, allJobs, isLoading, isStale };
}

export default useActiveJob;
