import React from "react";
import StatusBadge, { WorkflowStatus } from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import {
  X,
  FileText,
  Calculator,
  ShoppingCart,
  Package,
  AlertCircle,
  Clock,
  CheckCircle2,
  Download,
  Search,
  FileSearch,
  FileOutput,
  Upload,
  Globe,
  Circle,
  Loader2,
} from "lucide-react";
import { motion } from "framer-motion";

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

interface JobDetailViewProps {
  job: JobFromAPI;
  onClose: () => void;
}

// Workflow step definition
interface WorkflowStep {
  status: string;
  name: string;
  icon: React.ReactNode;
}

// Get workflow steps based on platform and features
function getWorkflowSteps(
  platform: string,
  features: { zoho_upload: boolean; zoho_quote: boolean; calculator: boolean }
): WorkflowStep[] {
  const steps: WorkflowStep[] = [
    { status: "queued", name: "Queued", icon: <Circle className="w-3.5 h-3.5" /> },
    { status: "detecting_source", name: "Detecting Source", icon: <Search className="w-3.5 h-3.5" /> },
  ];

  if (platform === "SAGE") {
    steps.push(
      { status: "sage_calling_api", name: "Calling SAGE API", icon: <Globe className="w-3.5 h-3.5" /> },
      { status: "sage_enriching_products", name: "Enriching Products", icon: <Package className="w-3.5 h-3.5" /> }
    );
  } else {
    // ESP workflow
    steps.push(
      { status: "esp_downloading_presentation", name: "Downloading Presentation", icon: <Download className="w-3.5 h-3.5" /> },
      { status: "esp_uploading_to_s3", name: "Uploading to S3", icon: <Upload className="w-3.5 h-3.5" /> },
      { status: "esp_parsing_presentation", name: "Parsing Presentation", icon: <FileSearch className="w-3.5 h-3.5" /> },
      { status: "esp_looking_up_products", name: "Looking Up Products", icon: <Search className="w-3.5 h-3.5" /> },
      { status: "esp_parsing_products", name: "Parsing Products", icon: <FileText className="w-3.5 h-3.5" /> }
    );
  }

  steps.push(
    { status: "normalizing", name: "Normalizing Data", icon: <FileOutput className="w-3.5 h-3.5" /> }
  );

  if (features.zoho_upload) {
    steps.push({ status: "zoho_uploading_items", name: "Uploading to Zoho", icon: <Upload className="w-3.5 h-3.5" /> });
  }

  if (features.zoho_quote) {
    steps.push({ status: "zoho_creating_quote", name: "Creating Quote", icon: <ShoppingCart className="w-3.5 h-3.5" /> });
  }

  if (features.calculator) {
    steps.push({ status: "calc_generating", name: "Generating Calculator", icon: <Calculator className="w-3.5 h-3.5" /> });
  }

  steps.push({ status: "completed", name: "Completed", icon: <CheckCircle2 className="w-3.5 h-3.5" /> });

  return steps;
}

// Get the index of the current step
function getCurrentStepIndex(steps: WorkflowStep[], currentStatus: string): number {
  const idx = steps.findIndex((s) => s.status === currentStatus);
  // If status not found in steps (might be in error or partial_success), find the closest match
  if (idx === -1) {
    if (currentStatus === "error" || currentStatus === "partial_success") {
      // Find where we were before the error
      return steps.length - 1; // Assume we were at the end
    }
    return 0;
  }
  return idx;
}

// Workflow Pipeline Component
function WorkflowPipeline({ status, platform, features }: {
  status: string;
  platform: string;
  features: { zoho_upload: boolean; zoho_quote: boolean; calculator: boolean };
}) {
  const steps = getWorkflowSteps(platform, features);
  const currentIndex = getCurrentStepIndex(steps, status);
  const isComplete = status === "completed" || status === "partial_success";
  const isError = status === "error";

  return (
    <div className="space-y-1">
      {steps.map((step, idx) => {
        const isCompleted = idx < currentIndex || (isComplete && idx === steps.length - 1);
        const isCurrent = idx === currentIndex && !isComplete && !isError;
        const isPending = idx > currentIndex || (isError && idx >= currentIndex);

        return (
          <div
            key={step.status}
            className={`flex items-center gap-3 px-3 py-2 rounded-md transition-all ${
              isCompleted
                ? "bg-emerald-500/10 text-emerald-400"
                : isCurrent
                ? "bg-blue-500/10 text-blue-400 border border-blue-500/30"
                : isError && idx === currentIndex
                ? "bg-red-500/10 text-red-400 border border-red-500/30"
                : "bg-secondary/30 text-muted-foreground opacity-50"
            }`}
          >
            <div className="shrink-0">
              {isCompleted ? (
                <CheckCircle2 className="w-3.5 h-3.5" />
              ) : isCurrent ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : isError && idx === currentIndex ? (
                <AlertCircle className="w-3.5 h-3.5" />
              ) : (
                step.icon
              )}
            </div>
            <span className="text-xs font-medium">{step.name}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function JobDetailView({ job, onClose }: JobDetailViewProps) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 25, stiffness: 200 }}
        className="relative w-full max-w-lg bg-card border-l border-border shadow-2xl h-full overflow-y-auto flex flex-col"
      >
        {/* Header */}
        <div className="p-6 border-b border-border sticky top-0 bg-card z-10">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              {/* Platform Badge & Job ID */}
              <div className="flex items-center gap-2 mb-3">
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    job.platform === "ESP"
                      ? "bg-red-500/10 text-red-500 border border-red-500/20"
                      : "bg-green-500/10 text-green-500 border border-green-500/20"
                  }`}
                >
                  {job.platform}
                </span>
                <span className="text-xs text-muted-foreground font-mono">
                  {job.id}
                </span>
              </div>

              {/* Features enabled */}
              <div className="flex gap-2">
                {job.features.zoho_upload && (
                  <span className="text-[10px] px-2 py-1 bg-blue-500/10 text-blue-400 rounded border border-blue-500/20">
                    Zoho Upload
                  </span>
                )}
                {job.features.zoho_quote && (
                  <span className="text-[10px] px-2 py-1 bg-green-500/10 text-green-400 rounded border border-green-500/20">
                    Zoho Quote
                  </span>
                )}
                {job.features.calculator && (
                  <span className="text-[10px] px-2 py-1 bg-purple-500/10 text-purple-400 rounded border border-purple-500/20">
                    Calculator
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-secondary rounded-full text-muted-foreground hover:text-foreground transition-colors ml-4"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 flex-1">
          {/* Current Status & Progress */}
          <section>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Current Status
              </h3>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(job.updated_at).toLocaleTimeString()}
              </span>
            </div>
            <div className="bg-secondary/30 rounded-lg p-4 border border-border">
              <div className="flex items-center justify-between mb-4">
                <StatusBadge status={job.status as WorkflowStatus} />
                <span className="font-bold text-xl text-emerald-500">
                  {job.progress}%
                </span>
              </div>
              <ProgressBar progress={job.progress} showLabel={false} />

              {/* Product Progress */}
              {job.total_items !== null && job.total_items > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground flex items-center gap-2">
                      <Package className="w-4 h-4" />
                      Products Processed
                    </span>
                    <span className="font-mono font-medium text-foreground">
                      {job.current_item || 0}/{job.total_items}
                    </span>
                  </div>
                  {job.current_item_name && (
                    <p className="text-xs text-muted-foreground mt-2 truncate">
                      Current: {job.current_item_name}
                    </p>
                  )}
                </div>
              )}
            </div>
          </section>

          {/* Workflow Pipeline */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              Workflow Pipeline
            </h3>
            <WorkflowPipeline
              status={job.status}
              platform={job.platform}
              features={job.features}
            />
          </section>

          {/* Timeline */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              Timeline
            </h3>
            <div className="bg-secondary/30 rounded-lg p-4 border border-border space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Started</span>
                <span className="font-mono text-foreground">
                  {new Date(job.started_at).toLocaleString()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Last Updated</span>
                <span className="font-mono text-foreground">
                  {new Date(job.updated_at).toLocaleString()}
                </span>
              </div>
            </div>
          </section>

          {/* Errors */}
          {job.errors && job.errors.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-red-500 uppercase tracking-wider mb-3">
                Errors
              </h3>
              <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4">
                <ul className="space-y-2">
                  {job.errors.map((error, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-red-400 flex items-start gap-2"
                    >
                      <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                      {typeof error === "string" ? error : JSON.stringify(error)}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </div>
      </motion.div>
    </div>
  );
}
