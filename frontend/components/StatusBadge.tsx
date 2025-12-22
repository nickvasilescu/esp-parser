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
  Upload,
  Database,
  Users,
  FileSpreadsheet,
  Cloud,
  Merge,
  AlertTriangle,
  Globe,
  Settings,
} from "lucide-react";

// Extended workflow statuses for ESP, SAGE, and Zoho integration
export type WorkflowStatus =
  // === INITIALIZATION ===
  | "queued"
  | "detecting_source"

  // === ESP PIPELINE ===
  | "esp_downloading_presentation"
  | "esp_uploading_to_s3"
  | "esp_parsing_presentation"
  | "esp_looking_up_products"
  | "esp_downloading_products"
  | "esp_parsing_products"
  | "esp_merging_data"

  // === SAGE PIPELINE ===
  | "sage_calling_api"
  | "sage_parsing_response"
  | "sage_enriching_products"

  // === NORMALIZATION (SHARED) ===
  | "normalizing"
  | "saving_output"

  // === ZOHO INTEGRATION (OPTIONAL) ===
  | "zoho_searching_customer"
  | "zoho_discovering_fields"
  | "zoho_uploading_items"
  | "zoho_uploading_images"
  | "zoho_creating_quote"

  // === CALCULATOR (OPTIONAL) ===
  | "calc_generating"
  | "calc_uploading"

  // === REVIEW & TERMINAL ===
  | "awaiting_qa"
  | "completed"
  | "error"
  | "partial_success";

// State categories for grouping in UI
export const STATE_CATEGORIES = {
  initialization: ["queued", "detecting_source"],
  esp_acquisition: [
    "esp_downloading_presentation",
    "esp_uploading_to_s3",
    "esp_parsing_presentation",
    "esp_looking_up_products",
    "esp_downloading_products",
    "esp_parsing_products",
    "esp_merging_data",
  ],
  sage_acquisition: [
    "sage_calling_api",
    "sage_parsing_response",
    "sage_enriching_products",
  ],
  normalization: ["normalizing", "saving_output"],
  zoho_integration: [
    "zoho_searching_customer",
    "zoho_discovering_fields",
    "zoho_uploading_items",
    "zoho_uploading_images",
    "zoho_creating_quote",
  ],
  calculator: ["calc_generating", "calc_uploading"],
  terminal: ["awaiting_qa", "completed", "error", "partial_success"],
};

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
  // === INITIALIZATION ===
  queued: {
    label: "Queued",
    color: "bg-slate-500/15 text-slate-500 border-slate-500/20",
    icon: <Clock className="w-3.5 h-3.5" />,
  },
  detecting_source: {
    label: "Detecting Source",
    color: "bg-blue-500/15 text-blue-500 border-blue-500/20",
    icon: <Globe className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === ESP PIPELINE ===
  esp_downloading_presentation: {
    label: "Downloading Presentation",
    color: "bg-indigo-500/15 text-indigo-500 border-indigo-500/20",
    icon: <Download className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_uploading_to_s3: {
    label: "Uploading to Cloud",
    color: "bg-sky-500/15 text-sky-500 border-sky-500/20",
    icon: <Cloud className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_parsing_presentation: {
    label: "Parsing Presentation",
    color: "bg-purple-500/15 text-purple-500 border-purple-500/20",
    icon: <Bot className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_looking_up_products: {
    label: "Looking Up Products",
    color: "bg-amber-500/15 text-amber-500 border-amber-500/20",
    icon: <FileSearch className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_downloading_products: {
    label: "Downloading Products",
    color: "bg-orange-500/15 text-orange-500 border-orange-500/20",
    icon: <Download className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_parsing_products: {
    label: "Parsing Products",
    color: "bg-rose-500/15 text-rose-500 border-rose-500/20",
    icon: <FileText className="w-3.5 h-3.5 animate-pulse" />,
  },
  esp_merging_data: {
    label: "Merging Data",
    color: "bg-fuchsia-500/15 text-fuchsia-500 border-fuchsia-500/20",
    icon: <Merge className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === SAGE PIPELINE ===
  sage_calling_api: {
    label: "Calling SAGE API",
    color: "bg-green-500/15 text-green-500 border-green-500/20",
    icon: <Globe className="w-3.5 h-3.5 animate-pulse" />,
  },
  sage_parsing_response: {
    label: "Parsing Response",
    color: "bg-teal-500/15 text-teal-500 border-teal-500/20",
    icon: <FileText className="w-3.5 h-3.5 animate-pulse" />,
  },
  sage_enriching_products: {
    label: "Enriching Products",
    color: "bg-cyan-500/15 text-cyan-500 border-cyan-500/20",
    icon: <Database className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === NORMALIZATION ===
  normalizing: {
    label: "Normalizing",
    color: "bg-violet-500/15 text-violet-500 border-violet-500/20",
    icon: <Settings className="w-3.5 h-3.5 animate-spin" />,
  },
  saving_output: {
    label: "Saving Output",
    color: "bg-pink-500/15 text-pink-500 border-pink-500/20",
    icon: <Upload className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === ZOHO INTEGRATION ===
  zoho_searching_customer: {
    label: "Finding Customer",
    color: "bg-blue-600/15 text-blue-600 border-blue-600/20",
    icon: <Users className="w-3.5 h-3.5 animate-pulse" />,
  },
  zoho_discovering_fields: {
    label: "Discovering Fields",
    color: "bg-indigo-600/15 text-indigo-600 border-indigo-600/20",
    icon: <Settings className="w-3.5 h-3.5 animate-spin" />,
  },
  zoho_uploading_items: {
    label: "Uploading Items",
    color: "bg-purple-600/15 text-purple-600 border-purple-600/20",
    icon: <Upload className="w-3.5 h-3.5 animate-pulse" />,
  },
  zoho_uploading_images: {
    label: "Uploading Images",
    color: "bg-violet-600/15 text-violet-600 border-violet-600/20",
    icon: <Upload className="w-3.5 h-3.5 animate-pulse" />,
  },
  zoho_creating_quote: {
    label: "Creating Quote",
    color: "bg-fuchsia-600/15 text-fuchsia-600 border-fuchsia-600/20",
    icon: <FileSpreadsheet className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === CALCULATOR ===
  calc_generating: {
    label: "Generating Calculator",
    color: "bg-lime-500/15 text-lime-500 border-lime-500/20",
    icon: <FileSpreadsheet className="w-3.5 h-3.5 animate-pulse" />,
  },
  calc_uploading: {
    label: "Uploading Calculator",
    color: "bg-green-600/15 text-green-600 border-green-600/20",
    icon: <Cloud className="w-3.5 h-3.5 animate-pulse" />,
  },

  // === TERMINAL STATES ===
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
  partial_success: {
    label: "Partial Success",
    color: "bg-amber-600/15 text-amber-600 border-amber-600/20",
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
  },
};

export default function StatusBadge({
  status,
  className,
  showIcon = true,
}: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.queued;

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
