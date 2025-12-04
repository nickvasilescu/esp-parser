"use client";

import React, { useState } from "react";
import { AnimatePresence } from "framer-motion";
import Layout from "../components/Layout";
import VMPanel from "../components/VMPanel";
import JobsTable from "../components/JobsTable";
import JobDetailView from "../components/JobDetailView";
import AgentThoughts from "../components/AgentThoughts";
import { mockJobs, Job } from "../data/mockData";
import { Activity, DollarSign, Timer, Zap } from "lucide-react";

export default function Home() {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // Calculate stats
  const completedJobs = mockJobs.filter((j) => j.status === "completed");
  const activeJobs = mockJobs.filter(
    (j) => j.status !== "completed" && j.status !== "error"
  );

  // Business Metrics
  const pipelineValue = activeJobs.reduce(
    (acc, job) => acc + (job.value || 0),
    0
  );
  const processedValue = completedJobs.reduce(
    (acc, job) => acc + (job.value || 0),
    0
  );
  const hoursSaved = (completedJobs.length * 0.5).toFixed(1);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <Layout>
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <SummaryCard
          label="$ Processed"
          value={formatCurrency(processedValue)}
          icon={<DollarSign className="w-4 h-4 text-emerald-500" />}
          color="border-l-4 border-l-emerald-500"
        />
        <SummaryCard
          label="Pipeline Value"
          value={formatCurrency(pipelineValue)}
          icon={<Activity className="w-4 h-4 text-blue-500" />}
          color="border-l-4 border-l-blue-500"
        />
        <SummaryCard
          label="Hours Saved"
          value={`${hoursSaved} hrs`}
          icon={<Timer className="w-4 h-4 text-purple-500" />}
          color="border-l-4 border-l-purple-500"
        />
        <SummaryCard
          label="Bot Efficiency"
          value="99.8%"
          icon={<Zap className="w-4 h-4 text-amber-500" />}
          color="border-l-4 border-l-amber-500"
        />
      </div>

      {/* Main Content: VM Panel + Active Workflows side by side */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 mb-4">
        {/* VM Panel - Left/Top */}
        <VMPanel />

        {/* Active Workflows Table - Right/Bottom */}
        <JobsTable
          jobs={mockJobs}
          onSelectJob={setSelectedJob}
          className="max-h-[400px]"
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
