"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Job, JobFeatures } from "../data/mockData";
import { WorkflowStatus } from "../components/StatusBadge";

// Job state from Python backend (matches job_state.py JobState)
interface JobStateFromBackend {
  job_id: string;
  status: WorkflowStatus;
  platform: "ESP" | "SAGE";
  progress: number;
  current_item?: number;
  total_items?: number;
  current_item_name?: string;
  features: {
    zoho_upload: boolean;
    zoho_quote: boolean;
    calculator: boolean;
  };
  started_at: string;
  updated_at: string;
  presentation_pdf_url?: string;
  output_json_url?: string;
  zoho_item_link?: string;
  zoho_quote_link?: string;
  calculator_link?: string;
  errors: Array<{
    step: string;
    message: string;
    product_id?: string;
    recoverable: boolean;
  }>;
}

interface UseJobPollingOptions {
  /** Base URL for fetching job state files (default: /api/jobs) */
  baseUrl?: string;
  /** Polling interval in milliseconds (default: 5000) */
  interval?: number;
  /** Whether polling is enabled (default: true) */
  enabled?: boolean;
  /** Callback when a job state updates */
  onJobUpdate?: (job: JobStateFromBackend) => void;
  /** Callback when polling encounters an error */
  onError?: (error: Error) => void;
}

interface UseJobPollingReturn {
  /** Current jobs state (merged with existing jobs) */
  jobs: Map<string, JobStateFromBackend>;
  /** Whether currently polling */
  isPolling: boolean;
  /** Last error encountered */
  error: Error | null;
  /** Force refresh all jobs */
  refresh: () => Promise<void>;
  /** Start polling */
  startPolling: () => void;
  /** Stop polling */
  stopPolling: () => void;
}

/**
 * Hook for polling job state files from the backend.
 *
 * In production, this would poll the output directory for job_*_state.json files.
 * For the mockup, it simulates polling with the mock data.
 *
 * Usage:
 * ```tsx
 * const { jobs, isPolling, refresh } = useJobPolling({
 *   interval: 5000,
 *   onJobUpdate: (job) => console.log('Job updated:', job.job_id),
 * });
 * ```
 */
export function useJobPolling(
  options: UseJobPollingOptions = {}
): UseJobPollingReturn {
  const {
    baseUrl = "/api/jobs",
    interval = 5000,
    enabled = true,
    onJobUpdate,
    onError,
  } = options;

  const [jobs, setJobs] = useState<Map<string, JobStateFromBackend>>(new Map());
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const mountedRef = useRef(true);

  // Fetch all active job states
  const fetchJobStates = useCallback(async () => {
    try {
      const response = await fetch(`${baseUrl}/active`);

      if (!response.ok) {
        throw new Error(`Failed to fetch jobs: ${response.statusText}`);
      }

      const data: JobStateFromBackend[] = await response.json();

      if (!mountedRef.current) return;

      setJobs((prevJobs) => {
        const newJobs = new Map(prevJobs);

        data.forEach((jobState) => {
          const existingJob = newJobs.get(jobState.job_id);

          // Only trigger update callback if job actually changed
          if (
            !existingJob ||
            existingJob.status !== jobState.status ||
            existingJob.progress !== jobState.progress ||
            existingJob.current_item !== jobState.current_item
          ) {
            onJobUpdate?.(jobState);
          }

          newJobs.set(jobState.job_id, jobState);
        });

        return newJobs;
      });

      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;

      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onError?.(error);
    }
  }, [baseUrl, onJobUpdate, onError]);

  // Fetch single job state by ID
  const fetchJobState = useCallback(
    async (jobId: string) => {
      try {
        const response = await fetch(`${baseUrl}/${jobId}`);

        if (!response.ok) {
          throw new Error(`Failed to fetch job ${jobId}: ${response.statusText}`);
        }

        const jobState: JobStateFromBackend = await response.json();

        if (!mountedRef.current) return;

        setJobs((prevJobs) => {
          const newJobs = new Map(prevJobs);
          const existingJob = newJobs.get(jobId);

          if (
            !existingJob ||
            existingJob.status !== jobState.status ||
            existingJob.progress !== jobState.progress
          ) {
            onJobUpdate?.(jobState);
          }

          newJobs.set(jobId, jobState);
          return newJobs;
        });

        setError(null);
      } catch (err) {
        if (!mountedRef.current) return;

        const error = err instanceof Error ? err : new Error(String(err));
        setError(error);
        onError?.(error);
      }
    },
    [baseUrl, onJobUpdate, onError]
  );

  // Start polling
  const startPolling = useCallback(() => {
    if (intervalRef.current) return;

    setIsPolling(true);
    fetchJobStates();

    intervalRef.current = setInterval(fetchJobStates, interval);
  }, [fetchJobStates, interval]);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  // Manual refresh
  const refresh = useCallback(async () => {
    await fetchJobStates();
  }, [fetchJobStates]);

  // Auto-start polling when enabled
  useEffect(() => {
    mountedRef.current = true;

    if (enabled) {
      startPolling();
    }

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
  }, [enabled, startPolling, stopPolling]);

  return {
    jobs,
    isPolling,
    error,
    refresh,
    startPolling,
    stopPolling,
  };
}

/**
 * Convert backend job state to frontend Job interface.
 * Useful for merging polled state with existing mock data.
 */
export function mergeJobState(
  existingJob: Job,
  backendState: JobStateFromBackend
): Job {
  return {
    ...existingJob,
    status: backendState.status,
    progress: backendState.progress,
    platform: backendState.platform,
    current_item: backendState.current_item,
    total_items: backendState.total_items,
    current_item_name: backendState.current_item_name,
    updated_at: backendState.updated_at,
    features: backendState.features,
    presentation_pdf_url: backendState.presentation_pdf_url ?? existingJob.presentation_pdf_url,
    output_json_url: backendState.output_json_url ?? existingJob.output_json_url,
    zoho_item_link: backendState.zoho_item_link ?? existingJob.zoho_item_link,
    zoho_quote_link: backendState.zoho_quote_link ?? existingJob.zoho_quote_link,
    calculator_link: backendState.calculator_link ?? existingJob.calculator_link,
    errors: backendState.errors.map((e) => e.message),
  };
}

export default useJobPolling;
