import React from "react";
import { Job, WorkflowStep, ExtractedProduct } from "../data/mockData";
import StatusBadge from "./StatusBadge";
import ProgressBar from "./ProgressBar";
import {
  X,
  ExternalLink,
  FileText,
  Calculator,
  ShoppingCart,
  Globe,
  Mail,
  Building2,
  User,
  Link2,
  CheckCircle2,
  Circle,
  Loader2,
  AlertCircle,
  Package,
  Download,
  FileSearch,
  FileOutput,
  ClipboardCheck,
  ChevronRight,
  Clock,
} from "lucide-react";
import { motion } from "framer-motion";

interface JobDetailViewProps {
  job: Job;
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

              {/* Client Info */}
              <div className="space-y-1">
                <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
                  <User className="w-5 h-5 text-emerald-500" />
                  {job.client_name || "Unknown Client"}
                </h2>
                {job.client_company && (
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <Building2 className="w-4 h-4" />
                    {job.client_company}
                  </p>
                )}
                {job.client_email && (
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <Mail className="w-4 h-4" />
                    {job.client_email}
                  </p>
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
          {/* Presentation Link */}
          <section className="bg-secondary/30 rounded-lg p-4 border border-border">
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Link2 className="w-4 h-4" />
              <span className="font-medium uppercase tracking-wider text-xs">
                Presentation Link
              </span>
            </div>
            <a
              href={job.source_link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-emerald-500 hover:text-emerald-400 flex items-center gap-2 break-all"
            >
              {job.source_link}
              <ExternalLink className="w-3 h-3 shrink-0" />
            </a>
          </section>

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
              {job.total_products > 0 && (
                <div className="mt-3 pt-3 border-t border-border">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground flex items-center gap-2">
                      <Package className="w-4 h-4" />
                      Products Processed
                    </span>
                    <span className="font-mono font-medium text-foreground">
                      {job.products_processed}/{job.total_products}
                    </span>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Workflow Pipeline */}
          <section>
            <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              Workflow Pipeline
            </h3>
            <div className="space-y-1">
              {job.workflow_steps?.map((step, idx) => (
                <WorkflowStepItem
                  key={idx}
                  step={step}
                  isLast={idx === job.workflow_steps.length - 1}
                />
              ))}
            </div>
          </section>

          {/* Extracted Products */}
          {job.products_extracted && job.products_extracted.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
                Extracted Products ({job.products_extracted.length})
              </h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {job.products_extracted.map((product, idx) => (
                  <ProductItem key={idx} product={product} />
                ))}
              </div>
            </section>
          )}

          {/* Action Items */}
          {job.action_items.length > 0 && (
            <section>
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
                Current Actions
              </h3>
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4">
                <ul className="space-y-2">
                  {job.action_items.map((item, idx) => (
                    <li
                      key={idx}
                      className="text-sm text-amber-500 flex items-start gap-2"
                    >
                      <ChevronRight className="w-4 h-4 mt-0.5 shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

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
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          {/* Vendor & Product Info */}
          {(job.vendor || job.mpn) && (
            <section className="grid grid-cols-2 gap-3">
              <div className="bg-secondary/30 p-3 rounded-lg border border-border">
                <p className="text-xs text-muted-foreground mb-1">
                  Primary Vendor
                </p>
                <p className="font-medium text-foreground truncate">
                  {job.vendor || "Pending..."}
                </p>
              </div>
              <div className="bg-secondary/30 p-3 rounded-lg border border-border">
                <p className="text-xs text-muted-foreground mb-1">MPN</p>
                <p className="font-medium text-foreground font-mono truncate">
                  {job.mpn || "Pending..."}
                </p>
              </div>
            </section>
          )}

          {/* S3 Artifacts */}
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
                icon={<FileOutput className="w-4 h-4" />}
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
                label="Vendor Website"
                url={job.vendor_website}
                icon={<Globe className="w-4 h-4" />}
                disabled={!job.vendor_website}
              />
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

          {/* Quote Value */}
          {job.value > 0 && (
            <section className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-emerald-400">
                  Estimated Quote Value
                </span>
                <span className="text-2xl font-bold text-emerald-500">
                  $
                  {job.value.toLocaleString("en-US", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </span>
              </div>
            </section>
          )}
        </div>
      </motion.div>
    </div>
  );
}

function WorkflowStepItem({
  step,
  isLast,
}: {
  step: WorkflowStep;
  isLast: boolean;
}) {
  const getStepIcon = (stepNum: number) => {
    const icons: Record<number, React.ReactNode> = {
      1: <Mail className="w-3 h-3" />,
      2: <Download className="w-3 h-3" />,
      3: <FileSearch className="w-3 h-3" />,
      4: <Download className="w-3 h-3" />,
      5: <FileSearch className="w-3 h-3" />,
      6: <FileOutput className="w-3 h-3" />,
      7: <ClipboardCheck className="w-3 h-3" />,
    };
    return icons[stepNum] || <Circle className="w-3 h-3" />;
  };

  const getStatusStyles = () => {
    switch (step.status) {
      case "completed":
        return {
          bg: "bg-emerald-500",
          text: "text-foreground",
          icon: <CheckCircle2 className="w-4 h-4 text-emerald-500" />,
        };
      case "in_progress":
        return {
          bg: "bg-blue-500 animate-pulse",
          text: "text-foreground font-medium",
          icon: <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />,
        };
      case "error":
        return {
          bg: "bg-red-500",
          text: "text-red-400",
          icon: <AlertCircle className="w-4 h-4 text-red-500" />,
        };
      default:
        return {
          bg: "bg-muted",
          text: "text-muted-foreground",
          icon: <Circle className="w-4 h-4 text-muted-foreground" />,
        };
    }
  };

  const styles = getStatusStyles();

  return (
    <div className="flex items-start gap-3">
      {/* Step indicator */}
      <div className="flex flex-col items-center">
        <div
          className={`w-6 h-6 rounded-full ${styles.bg} flex items-center justify-center text-white text-xs`}
        >
          {step.status === "completed" ? (
            <CheckCircle2 className="w-4 h-4" />
          ) : step.status === "in_progress" ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : step.status === "error" ? (
            <AlertCircle className="w-4 h-4" />
          ) : (
            <span>{step.step}</span>
          )}
        </div>
        {!isLast && (
          <div
            className={`w-0.5 h-6 ${
              step.status === "completed" ? "bg-emerald-500" : "bg-muted"
            }`}
          />
        )}
      </div>

      {/* Step content */}
      <div className="flex-1 pb-4">
        <div className="flex items-center gap-2">
          {getStepIcon(step.step)}
          <span className={`text-sm ${styles.text}`}>{step.name}</span>
        </div>
        {step.details && step.status === "in_progress" && (
          <p className="text-xs text-muted-foreground mt-1 ml-5">
            {step.details}
          </p>
        )}
        {step.completed_at && step.status === "completed" && (
          <p className="text-xs text-muted-foreground mt-1 ml-5">
            Completed at {new Date(step.completed_at).toLocaleTimeString()}
          </p>
        )}
      </div>
    </div>
  );
}

function ProductItem({ product }: { product: ExtractedProduct }) {
  return (
    <div className="bg-secondary/30 rounded-lg p-3 border border-border">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="font-mono text-xs text-muted-foreground">
            {product.cpn}
          </p>
          <p className="text-sm font-medium text-foreground truncate">
            {product.name}
          </p>
          <p className="text-xs text-muted-foreground">
            {product.vendor} · {product.mpn}
          </p>
        </div>
        <div className="flex items-center gap-1 ml-2">
          <span
            className={`w-2 h-2 rounded-full ${
              product.pdf_downloaded ? "bg-emerald-500" : "bg-muted"
            }`}
            title="PDF Downloaded"
          />
          <span
            className={`w-2 h-2 rounded-full ${
              product.pdf_parsed ? "bg-emerald-500" : "bg-muted"
            }`}
            title="PDF Parsed"
          />
        </div>
      </div>
      {product.error && (
        <p className="text-xs text-red-400 mt-2 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {product.error}
        </p>
      )}
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
