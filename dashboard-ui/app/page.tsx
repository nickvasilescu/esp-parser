"use client";

import React, { useState } from "react";
import { AnimatePresence } from "framer-motion";
import Layout from "../components/Layout";
import VMPanel from "../components/VMPanel";
import JobsTable from "../components/JobsTable";
import JobDetailView from "../components/JobDetailView";
import { mockJobs, Job } from "../data/mockData";
import { Activity, CheckCircle2, Clock, DollarSign, Timer, Zap } from "lucide-react";

export default function Home() {
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  // Calculate stats
  const totalJobs = mockJobs.length;
  const completedJobs = mockJobs.filter((j) => j.status === "completed");
  const activeJobs = mockJobs.filter(
    (j) => j.status !== "completed" && j.status !== "error"
  );

  // Business Metrics
  const pipelineValue = activeJobs.reduce((acc, job) => acc + (job.value || 0), 0);
  const processedValue = completedJobs.reduce((acc, job) => acc + (job.value || 0), 0);
  const hoursSaved = (completedJobs.length * 0.5).toFixed(1); // Assuming 30 mins saved per quote

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <Layout>
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="$ Processed (In Quotes)"
          value={formatCurrency(processedValue)}
          icon={<DollarSign className="w-5 h-5 text-emerald-500" />}
          color="border-l-4 border-l-emerald-500"
        />
        <SummaryCard
          label="Active Pipeline Value"
          value={formatCurrency(pipelineValue)}
          icon={<Activity className="w-5 h-5 text-blue-500" />}
          color="border-l-4 border-l-blue-500"
        />
        <SummaryCard
          label="Hours Saved"
          value={`${hoursSaved} hrs`}
          icon={<Timer className="w-5 h-5 text-purple-500" />}
          color="border-l-4 border-l-purple-500"
        />
        <SummaryCard
          label="Bot Efficiency"
          value="99.8%"
          icon={<Zap className="w-5 h-5 text-amber-500" />}
          color="border-l-4 border-l-amber-500"
        />
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        {/* Jobs Table - Takes more space */}
        <div className="xl:col-span-3">
          <JobsTable jobs={mockJobs} onSelectJob={setSelectedJob} />
        </div>

        {/* VM Panel - Tabbed viewer on the side */}
        <div className="xl:col-span-2">
          <VMPanel className="sticky top-4" />
        </div>
      </div>

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
      className={`bg-card p-4 rounded-lg border border-border shadow-sm flex items-center justify-between ${color}`}
    >
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
      </div>
      <div className="p-3 bg-secondary rounded-full">{icon}</div>
    </div>
  );
}
