import React from "react";
import StatusBadge from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import {
  X,
  ExternalLink,
  FileText,
  Calculator,
  ShoppingCart,
  Package,
  AlertCircle,
  Clock,
  CheckCircle2,
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
                <StatusBadge status={job.status} />
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

          {/* Generated Artifacts */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              Generated Artifacts
            </h3>
            <div className="space-y-2">
              <ArtifactLink
                label="Presentation PDF"
                url={job.presentation_pdf_url}
                icon={<FileText className="w-4 h-4" />}
              />
              <ArtifactLink
                label="Output JSON"
                url={job.output_json_url}
                icon={<FileText className="w-4 h-4" />}
              />
            </div>
          </section>

          {/* Zoho Integration Links */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              Zoho Integration
            </h3>
            <div className="space-y-2">
              <ResourceLink
                label="Zoho Item Master"
                url={job.zoho_item_link}
                icon={<FileText className="w-4 h-4" />}
                disabled={!job.zoho_item_link}
              />
              <ResourceLink
                label="Price Calculator"
                url={job.calculator_link}
                icon={<Calculator className="w-4 h-4" />}
                disabled={!job.calculator_link}
              />
              <ResourceLink
                label="Zoho Quote"
                url={job.zoho_quote_link}
                icon={<ShoppingCart className="w-4 h-4" />}
                disabled={!job.zoho_quote_link}
                highlight
              />
            </div>
          </section>
        </div>
      </motion.div>
    </div>
  );
}

function ArtifactLink({
  label,
  url,
  icon,
}: {
  label: string;
  url: string | null;
  icon: React.ReactNode;
}) {
  if (!url) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/10 opacity-50">
        <div className="flex items-center gap-3">
          {icon}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <span className="text-xs text-muted-foreground">Not generated</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/30">
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <span className="text-sm font-medium block">{label}</span>
          <span className="text-xs text-muted-foreground font-mono truncate block max-w-[200px]">
            {url.split("/").pop()}
          </span>
        </div>
      </div>
      <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    </div>
  );
}

function ResourceLink({
  label,
  url,
  icon,
  disabled,
  highlight,
}: {
  label: string;
  url: string | null;
  icon: React.ReactNode;
  disabled?: boolean;
  highlight?: boolean;
}) {
  if (disabled) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-secondary/10 opacity-50 cursor-not-allowed">
        <div className="flex items-center gap-3">
          {icon}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <span className="text-xs">Pending</span>
      </div>
    );
  }

  return (
    <a
      href={url!}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-center justify-between p-3 rounded-lg border transition-all ${
        highlight
          ? "bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20 text-emerald-500"
          : "bg-card border-border hover:bg-secondary text-foreground"
      }`}
    >
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <ExternalLink className="w-4 h-4 opacity-50" />
    </a>
  );
}
