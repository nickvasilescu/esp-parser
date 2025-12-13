import { WorkflowStatus } from "../components/StatusBadge";

// Workflow step details for tracking progress
export interface WorkflowStep {
  step: number;
  name: string;
  status: "pending" | "in_progress" | "completed" | "error";
  started_at?: string;
  completed_at?: string;
  details?: string;
}

// Product extracted from presentation
export interface ExtractedProduct {
  cpn: string;
  name: string;
  vendor: string;
  mpn: string;
  pdf_downloaded: boolean;
  pdf_parsed: boolean;
  error?: string;
}

// Feature flags for tracking which optional steps are enabled
export interface JobFeatures {
  zoho_upload: boolean;
  zoho_quote: boolean;
  calculator: boolean;
}

export interface Job {
  id: string;
  source_link: string;
  platform: "ESP" | "SAGE";
  product_id: string;
  status: WorkflowStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  // Client information
  client_name: string | null;
  client_email: string | null;
  client_company: string | null;
  // Product/vendor info (from parsing)
  mpn: string | null;
  vendor: string | null;
  vendor_website: string | null;
  // Zoho integration links
  zoho_item_link: string | null;
  zoho_quote_link: string | null;
  calculator_link: string | null;
  // Workflow tracking
  action_items: string[];
  value: number;
  // NEW: Sub-progress tracking for multi-item states
  current_item?: number;
  total_items?: number;
  current_item_name?: string;
  // Feature flags
  features: JobFeatures;
  // Detailed workflow tracking
  workflow_steps: WorkflowStep[];
  products_extracted: ExtractedProduct[];
  total_products: number;
  products_processed: number;
  presentation_pdf_url: string | null;
  output_json_url: string | null;
  errors: string[];
}

// Helper to generate workflow steps based on status (ESP pipeline)
const generateESPWorkflowSteps = (
  status: WorkflowStatus,
  startTime: string
): WorkflowStep[] => {
  const steps: WorkflowStep[] = [
    {
      step: 1,
      name: "Detect Source",
      status: "completed",
      started_at: startTime,
      completed_at: startTime,
      details: "Identify presentation source (ESP or SAGE)",
    },
    {
      step: 2,
      name: "Download Presentation",
      status: "pending",
      details: "CUA Agent navigates to presentation portal and downloads PDF",
    },
    {
      step: 3,
      name: "Parse Presentation",
      status: "pending",
      details: "Claude Opus 4.5 extracts product list from presentation PDF",
    },
    {
      step: 4,
      name: "Look Up Products",
      status: "pending",
      details: "Sequential CUA agents lookup each product in ESP+",
    },
    {
      step: 5,
      name: "Parse Products",
      status: "pending",
      details: "Claude Opus 4.5 extracts pricing and vendor data from each report",
    },
    {
      step: 6,
      name: "Merge & Normalize",
      status: "pending",
      details: "Merge presentation and distributor data, normalize to unified schema",
    },
    {
      step: 7,
      name: "Zoho Upload",
      status: "pending",
      details: "Upload items to Zoho Item Master and create quote",
    },
  ];

  const statusToStep: Record<string, number> = {
    queued: 0,
    detecting_source: 1,
    esp_downloading_presentation: 2,
    esp_uploading_to_s3: 2,
    esp_parsing_presentation: 3,
    esp_looking_up_products: 4,
    esp_downloading_products: 4,
    esp_parsing_products: 5,
    esp_merging_data: 6,
    normalizing: 6,
    saving_output: 6,
    zoho_searching_customer: 7,
    zoho_discovering_fields: 7,
    zoho_uploading_items: 7,
    zoho_uploading_images: 7,
    zoho_creating_quote: 7,
    calc_generating: 7,
    calc_uploading: 7,
    awaiting_qa: 8,
    completed: 9,
    partial_success: 9,
    error: 0,
  };

  const currentStep = statusToStep[status] || 0;

  steps.forEach((step, idx) => {
    if (idx + 1 < currentStep) {
      step.status = "completed";
      step.completed_at = new Date(
        new Date(startTime).getTime() + idx * 5 * 60000
      ).toISOString();
    } else if (idx + 1 === currentStep) {
      step.status = "in_progress";
      step.started_at = new Date(
        new Date(startTime).getTime() + idx * 5 * 60000
      ).toISOString();
    }
  });

  if (status === "completed" || status === "partial_success") {
    steps.forEach((step) => {
      step.status = "completed";
    });
  }

  return steps;
};

// Helper to generate workflow steps based on status (SAGE pipeline)
const generateSAGEWorkflowSteps = (
  status: WorkflowStatus,
  startTime: string
): WorkflowStep[] => {
  const steps: WorkflowStep[] = [
    {
      step: 1,
      name: "Detect Source",
      status: "completed",
      started_at: startTime,
      completed_at: startTime,
      details: "Identify presentation source (ESP or SAGE)",
    },
    {
      step: 2,
      name: "Call SAGE API",
      status: "pending",
      details: "Fetch presentation data from SAGE Connect API",
    },
    {
      step: 3,
      name: "Enrich Products",
      status: "pending",
      details: "Enrich with full product details from SAGE API",
    },
    {
      step: 4,
      name: "Normalize Data",
      status: "pending",
      details: "Convert to unified schema for downstream processing",
    },
    {
      step: 5,
      name: "Zoho Upload",
      status: "pending",
      details: "Upload items to Zoho Item Master and create quote",
    },
  ];

  const statusToStep: Record<string, number> = {
    queued: 0,
    detecting_source: 1,
    sage_calling_api: 2,
    sage_parsing_response: 2,
    sage_enriching_products: 3,
    normalizing: 4,
    saving_output: 4,
    zoho_searching_customer: 5,
    zoho_discovering_fields: 5,
    zoho_uploading_items: 5,
    zoho_uploading_images: 5,
    zoho_creating_quote: 5,
    calc_generating: 5,
    calc_uploading: 5,
    awaiting_qa: 6,
    completed: 7,
    partial_success: 7,
    error: 0,
  };

  const currentStep = statusToStep[status] || 0;

  steps.forEach((step, idx) => {
    if (idx + 1 < currentStep) {
      step.status = "completed";
      step.completed_at = new Date(
        new Date(startTime).getTime() + idx * 5 * 60000
      ).toISOString();
    } else if (idx + 1 === currentStep) {
      step.status = "in_progress";
      step.started_at = new Date(
        new Date(startTime).getTime() + idx * 5 * 60000
      ).toISOString();
    }
  });

  if (status === "completed" || status === "partial_success") {
    steps.forEach((step) => {
      step.status = "completed";
    });
  }

  return steps;
};

// Helper to generate workflow steps based on platform and status
export const generateWorkflowSteps = (
  status: WorkflowStatus,
  startTime: string,
  platform: "ESP" | "SAGE" = "ESP"
): WorkflowStep[] => {
  return platform === "SAGE"
    ? generateSAGEWorkflowSteps(status, startTime)
    : generateESPWorkflowSteps(status, startTime);
};

// Production: Empty array - jobs will be populated from backend polling
export const mockJobs: Job[] = [];
