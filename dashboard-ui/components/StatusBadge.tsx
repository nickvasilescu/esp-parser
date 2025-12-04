import React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  FileSearch,
  Download,
  FileText,
  Bot,
  Send,
} from "lucide-react";

// Workflow statuses matching the actual ESP/Sage pipeline
export type WorkflowStatus =
  | "email_received" // Initial presentation link received
  | "downloading_presentation" // CUA 1: Downloading presentation PDF from portal
  | "parsing_presentation" // Claude: Extracting product list from presentation
  | "downloading_product_pdfs" // CUA 2: Sequential agents downloading distributor reports
  | "parsing_product_pdfs" // Claude: Parsing product PDFs for full details
  | "generating_output" // Creating final Zoho-ready JSON output
  | "awaiting_qa" // Manual review required
  | "completed" // Pipeline complete, ready for Zoho
  | "error"; // Pipeline failed

interface StatusBadgeProps {
  status: WorkflowStatus;
  className?: string;
  showIcon?: boolean;
}

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const statusConfig: Record<
  WorkflowStatus,
  { label: string; color: string; icon: React.ReactNode }
> = {
  email_received: {
    label: "Email Received",
    color: "bg-blue-500/15 text-blue-500 border-blue-500/20",
    icon: <Clock className="w-3.5 h-3.5" />,
  },
  downloading_presentation: {
    label: "Downloading Presentation",
    color: "bg-indigo-500/15 text-indigo-500 border-indigo-500/20",
    icon: <Download className="w-3.5 h-3.5 animate-pulse" />,
  },
  parsing_presentation: {
    label: "Parsing Presentation",
    color: "bg-purple-500/15 text-purple-500 border-purple-500/20",
    icon: <Bot className="w-3.5 h-3.5 animate-pulse" />,
  },
  downloading_product_pdfs: {
    label: "Downloading Product PDFs",
    color: "bg-amber-500/15 text-amber-500 border-amber-500/20",
    icon: <FileText className="w-3.5 h-3.5 animate-pulse" />,
  },
  parsing_product_pdfs: {
    label: "Parsing Product PDFs",
    color: "bg-orange-500/15 text-orange-500 border-orange-500/20",
    icon: <FileSearch className="w-3.5 h-3.5 animate-pulse" />,
  },
  generating_output: {
    label: "Generating Output",
    color: "bg-pink-500/15 text-pink-500 border-pink-500/20",
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  awaiting_qa: {
    label: "Awaiting QA",
    color: "bg-yellow-500/15 text-yellow-500 border-yellow-500/20",
    icon: <AlertCircle className="w-3.5 h-3.5" />,
  },
  completed: {
    label: "Complete",
    color: "bg-emerald-500/15 text-emerald-500 border-emerald-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  error: {
    label: "Failed",
    color: "bg-red-500/15 text-red-500 border-red-500/20",
    icon: <AlertCircle className="w-3.5 h-3.5" />,
  },
};

export default function StatusBadge({
  status,
  className,
  showIcon = true,
}: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.email_received;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-all",
        config.color,
        className
      )}
    >
      {showIcon && config.icon}
      {config.label}
    </span>
  );
}
