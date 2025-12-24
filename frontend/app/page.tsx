"use client";

import React, { useState } from "react";
import { AnimatePresence } from "framer-motion";
import Layout from "../components/Layout";
import VMPanel from "../components/VMPanel";
import JobsTable from "../components/JobsTable";
import JobDetailView from "../components/JobDetailView";
import AgentThoughts from "../components/AgentThoughts";
import { useActiveJob } from "../hooks/useActiveJob";
import { FileText, Timer, Package, CheckCircle, Loader2 } from "lucide-react";

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

export default function Home() {
  const [selectedJob, setSelectedJob] = useState<JobFromAPI | null>(null);

  // Fetch real jobs from the API
  const { allJobs, isLoading } = useActiveJob(2000);

  // ==========================================================================
  // METRIC CALCULATIONS (using real data)
  // ==========================================================================

  // 1. QUOTES GENERATED (cumulative)
  // Count jobs that have completed with zoho_quote enabled
  // (Backend doesn't always set zoho_quote_link, so infer from status + feature flag)
  const quotesGenerated = allJobs.filter(
    (job) =>
      job.zoho_quote_link !== null ||
      ((job.status === "completed" || job.status === "partial_success") &&
        job.features.zoho_quote)
  ).length;

  // 2. PRODUCTS PARSED (cumulative)
  // Sum of total_items across all jobs that have it
  const productsParsed = allJobs.reduce(
    (acc, job) => acc + (job.total_items || 0),
    0
  );

  // 3. HOURS SAVED (estimated human effort saved)
  // Estimate 15-20 minutes saved per product for manual quoting
  // Using 15 min as a conservative estimate
  const MINUTES_PER_PRODUCT = 15;
  const hoursSaved = ((productsParsed * MINUTES_PER_PRODUCT) / 60).toFixed(1);

  // 4. SUCCESS RATE
  // (completed + partial_success) / (completed + partial_success + error) × 100
  const terminalJobs = allJobs.filter(
    (job) =>
      job.status === "completed" ||
      job.status === "partial_success" ||
      job.status === "error"
  );
  const successfulJobs = terminalJobs.filter(
    (job) => job.status === "completed" || job.status === "partial_success"
  );
  const successRate =
    terminalJobs.length > 0
      ? ((successfulJobs.length / terminalJobs.length) * 100).toFixed(1)
      : "--";

  return (
    <Layout>
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <SummaryCard
          label="Quotes Generated"
          value={quotesGenerated}
          icon={<FileText className="w-4 h-4 text-emerald-500" />}
          color="border-l-4 border-l-emerald-500"
        />
        <SummaryCard
          label="Hours Saved"
          value={`${hoursSaved} hrs`}
          icon={<Timer className="w-4 h-4 text-blue-500" />}
          color="border-l-4 border-l-blue-500"
        />
        <SummaryCard
          label="Products Parsed"
          value={productsParsed}
          icon={<Package className="w-4 h-4 text-purple-500" />}
          color="border-l-4 border-l-purple-500"
        />
        <SummaryCard
          label="Success Rate"
          value={successRate === "--" ? "--" : `${successRate}%`}
          icon={<CheckCircle className="w-4 h-4 text-amber-500" />}
          color="border-l-4 border-l-amber-500"
        />
      </div>

      {/* Main Content: VM Panel + Active Workflows side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4 xl:grid-rows-[1fr]">
        {/* VM Panel - Left/Top */}
        <VMPanel className="h-full" />

        {/* Active Workflows Table - Right/Bottom */}
        <JobsTable
          jobs={allJobs}
          onSelectJob={setSelectedJob}
          className="h-full"
          isLoading={isLoading}
        />
      </div>

      {/* Agent Reasoning Stream - Full width below */}
      <AgentThoughts />

      {/* Slide-over Detail View */}
      <AnimatePresence>
        {selectedJob && (
          <JobDetailView
            job={selectedJob}
            onClose={() => setSelectedJob(null)}
          />
        )}
      </AnimatePresence>
    </Layout>
  );
}

function SummaryCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div
      className={`bg-card p-3 rounded-lg border border-border shadow-sm ${color}`}
    >
      <div className="flex items-center justify-between mb-1">
        <p className="text-[10px] text-muted-foreground uppercase tracking-wider">
          {label}
        </p>
        <div className="p-1 bg-secondary rounded">{icon}</div>
      </div>
      <p className="text-lg font-bold text-foreground">{value}</p>
    </div>
  );
}
