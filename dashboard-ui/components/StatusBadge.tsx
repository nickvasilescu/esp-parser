import React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
  FileSearch,
  Calculator,
  Send,
} from "lucide-react";

export type WorkflowStatus =
  | "email_received"
  | "validating_link"
  | "platform_identified"
  | "product_id_extracted"
  | "searching_platform"
  | "scraping_metadata"
  | "vendor_match_complete"
  | "item_master_updated"
  | "calculator_generated"
  | "dual_condition_met"
  | "quote_generated"
  | "awaiting_qa"
  | "completed"
  | "error";

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
  validating_link: {
    label: "Validating Link",
    color: "bg-blue-500/15 text-blue-500 border-blue-500/20",
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  platform_identified: {
    label: "Platform Identified",
    color: "bg-indigo-500/15 text-indigo-500 border-indigo-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  product_id_extracted: {
    label: "ID Extracted",
    color: "bg-indigo-500/15 text-indigo-500 border-indigo-500/20",
    icon: <FileSearch className="w-3.5 h-3.5" />,
  },
  searching_platform: {
    label: "Searching Catalog",
    color: "bg-amber-500/15 text-amber-500 border-amber-500/20",
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  scraping_metadata: {
    label: "Scraping Data",
    color: "bg-amber-500/15 text-amber-500 border-amber-500/20",
    icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
  },
  vendor_match_complete: {
    label: "Vendor Matched",
    color: "bg-emerald-500/15 text-emerald-500 border-emerald-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  item_master_updated: {
    label: "Item Master Updated",
    color: "bg-purple-500/15 text-purple-500 border-purple-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  calculator_generated: {
    label: "Calculator Ready",
    color: "bg-purple-500/15 text-purple-500 border-purple-500/20",
    icon: <Calculator className="w-3.5 h-3.5" />,
  },
  dual_condition_met: {
    label: "Integration Ready",
    color: "bg-purple-500/15 text-purple-500 border-purple-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  quote_generated: {
    label: "Quote Generated",
    color: "bg-pink-500/15 text-pink-500 border-pink-500/20",
    icon: <CheckCircle2 className="w-3.5 h-3.5" />,
  },
  awaiting_qa: {
    label: "Awaiting QA",
    color: "bg-yellow-500/15 text-yellow-500 border-yellow-500/20",
    icon: <AlertCircle className="w-3.5 h-3.5" />,
  },
  completed: {
    label: "Complete",
    color: "bg-emerald-500/15 text-emerald-500 border-emerald-500/20",
    icon: <Send className="w-3.5 h-3.5" />,
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
