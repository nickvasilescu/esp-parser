"use client";

import React from "react";
import StatusBadge, { WorkflowStatus } from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import { ChevronRight, Search, Loader2 } from "lucide-react";

// Job type from the API
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

// Format time consistently to avoid hydration mismatches
function formatTime(isoString: string): string {
  const date = new Date(isoString);
  const hours = date.getUTCHours();
  const minutes = date.getUTCMinutes();
  const ampm = hours >= 12 ? "PM" : "AM";
  const displayHours = hours % 12 || 12;
  const displayMinutes = minutes.toString().padStart(2, "0");
  return `${displayHours}:${displayMinutes} ${ampm}`;
}

// Format relative time for job display
function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

// Format status for display
function formatStatus(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface JobsTableProps {
  jobs: JobFromAPI[];
  onSelectJob: (job: JobFromAPI) => void;
  className?: string;
  isLoading?: boolean;
}

export default function JobsTable({
  jobs,
  onSelectJob,
  className,
  isLoading,
}: JobsTableProps) {
  return (
    <div
      className={`bg-card rounded-lg border border-border overflow-hidden flex flex-col ${
        className || ""
      }`}
    >
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-medium text-foreground">Active Workflows</h3>
          {isLoading && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
          <span className="text-xs text-muted-foreground">({jobs.length})</span>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-1.5 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search jobs..."
            className="pl-9 pr-4 py-1.5 bg-secondary rounded-md border border-border text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-emerald-500 w-64"
          />
        </div>
      </div>

      <div className="overflow-auto flex-1">
        <table className="w-full text-sm text-left">
          <thead className="bg-secondary/50 text-muted-foreground font-medium">
            <tr>
              <th className="px-4 py-3 w-[180px]">Status</th>
              <th className="px-4 py-3">Platform</th>
              <th className="px-4 py-3">Started</th>
              <th className="px-4 py-3 w-[200px]">Progress</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">
                  No active workflows
                </td>
              </tr>
            )}
            {jobs.map((job) => (
              <tr
                key={job.id}
                className="hover:bg-secondary/30 transition-colors cursor-pointer group"
                onClick={() => onSelectJob(job)}
              >
                <td className="px-4 py-3">
                  <StatusBadge status={job.status as WorkflowStatus} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        job.platform === "ESP" ? "bg-red-500" : "bg-green-500"
                      }`}
                    />
                    <span className="font-medium">{job.platform}</span>
                  </div>
                </td>
                <td className="px-4 py-3" suppressHydrationWarning>
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-foreground">
                      {formatRelativeTime(job.started_at)}
                    </span>
                    <div className="flex items-center gap-1 mt-1">
                      <span
                        className="text-[10px] text-muted-foreground font-mono cursor-help"
                        title={job.id}
                      >
                        {job.id.slice(-8)}
                      </span>
                      {job.features.zoho_upload && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded">
                          Zoho
                        </span>
                      )}
                      {job.features.calculator && (
                        <span className="text-[9px] px-1.5 py-0.5 bg-purple-500/10 text-purple-400 rounded">
                          Calc
                        </span>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        {job.current_item !== null && job.total_items !== null
                          ? `${job.current_item}/${job.total_items}`
                          : ""}
                      </span>
                      <span>{job.progress}%</span>
                    </div>
                    <ProgressBar progress={job.progress} />
                    {job.current_item_name && (
                      <span className="text-xs text-muted-foreground truncate max-w-[180px]">
                        {job.current_item_name}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <button className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary rounded-md opacity-0 group-hover:opacity-100 transition-all">
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
