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

export interface Job {
  id: string;
  source_link: string;
  platform: "ESP" | "Sage";
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
  // NEW: Detailed workflow tracking
  workflow_steps: WorkflowStep[];
  products_extracted: ExtractedProduct[];
  total_products: number;
  products_processed: number;
  presentation_pdf_url: string | null;
  output_json_url: string | null;
  errors: string[];
}

// Helper to generate workflow steps based on status
const generateWorkflowSteps = (
  status: WorkflowStatus,
  startTime: string
): WorkflowStep[] => {
  const steps: WorkflowStep[] = [
    {
      step: 1,
      name: "Email Received",
      status: "completed",
      started_at: startTime,
      completed_at: startTime,
      details: "Presentation link captured from client email",
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
      name: "Download Product PDFs",
      status: "pending",
      details:
        "Sequential CUA agents lookup each product in ESP+ and download distributor reports",
    },
    {
      step: 5,
      name: "Parse Product PDFs",
      status: "pending",
      details:
        "Claude Opus 4.5 extracts pricing and vendor data from each report",
    },
    {
      step: 6,
      name: "Generate Output",
      status: "pending",
      details: "Aggregate all extracted data into Zoho-ready JSON format",
    },
    {
      step: 7,
      name: "QA Review",
      status: "pending",
      details: "Human review of extracted data before Zoho import",
    },
  ];

  const statusToStep: Record<WorkflowStatus, number> = {
    email_received: 1,
    downloading_presentation: 2,
    parsing_presentation: 3,
    downloading_product_pdfs: 4,
    parsing_product_pdfs: 5,
    generating_output: 6,
    awaiting_qa: 7,
    completed: 8,
    error: 0,
  };

  const currentStep = statusToStep[status];

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

  if (status === "completed") {
    steps.forEach((step) => {
      step.status = "completed";
    });
  }

  return steps;
};

// Use static dates to avoid hydration mismatches between server and client
export const mockJobs: Job[] = [
  // ACTIVE/IN-PROGRESS JOBS
  {
    id: "job_1",
    source_link:
      "https://portal.mypromooffice.com/presentations/500183020?accessCode=b07e67d01cbd4ca2ba71934d128e1a44",
    platform: "ESP",
    product_id: "CPN-564949909",
    status: "downloading_product_pdfs",
    progress: 65,
    created_at: "2024-12-04T10:15:00.000Z",
    updated_at: "2024-12-04T10:45:00.000Z",
    client_name: "Sarah Johnson",
    client_email: "sarah.j@techcorp.com",
    client_company: "Tech Corp",
    mpn: "101142",
    vendor: "A Plus Wine Designs",
    vendor_website: "https://apluswd.com",
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "CUA Agent processing product 12/25",
      "Downloading distributor report",
    ],
    value: 3750.0,
    workflow_steps: generateWorkflowSteps(
      "downloading_product_pdfs",
      "2024-12-04T10:15:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-564949909",
        name: "Wine Opener Deluxe",
        vendor: "A Plus Wine Designs",
        mpn: "101142",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564949899",
        name: "Wine Stopper Set",
        vendor: "A Plus Wine Designs",
        mpn: "100288",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564949753",
        name: "Corkscrew Pro",
        vendor: "A Plus Wine Designs",
        mpn: "100198",
        pdf_downloaded: true,
        pdf_parsed: false,
      },
      {
        cpn: "CPN-564949800",
        name: "Wine Pourer",
        vendor: "A Plus Wine Designs",
        mpn: "100500",
        pdf_downloaded: false,
        pdf_parsed: false,
      },
    ],
    total_products: 25,
    products_processed: 12,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_101500/presentation.pdf",
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_2",
    source_link: "https://portal.mypromooffice.com/presentations/500183020",
    platform: "ESP",
    product_id: "CPN-564949899",
    status: "parsing_product_pdfs",
    progress: 55,
    created_at: "2024-12-04T10:18:00.000Z",
    updated_at: "2024-12-04T10:40:00.000Z",
    client_name: "Michael Chen",
    client_email: "mchen@globalbrands.com",
    client_company: "Global Brands LLC",
    mpn: "100288",
    vendor: "A Plus Wine Designs",
    vendor_website: "https://apluswd.com",
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "Claude parsing product 8/15 PDF",
      "Extracting pricing tiers",
    ],
    value: 2950.0,
    workflow_steps: generateWorkflowSteps(
      "parsing_product_pdfs",
      "2024-12-04T10:18:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-564949899",
        name: "Wine Stopper Set",
        vendor: "A Plus Wine Designs",
        mpn: "100288",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564949753",
        name: "Corkscrew Pro",
        vendor: "A Plus Wine Designs",
        mpn: "100198",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 15,
    products_processed: 8,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_101800/presentation.pdf",
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_3",
    source_link:
      "https://portal.mypromooffice.com/presentations/500180055?accessCode=abc123def456",
    platform: "ESP",
    product_id: "CPN-564949753",
    status: "downloading_presentation",
    progress: 40,
    created_at: "2024-12-04T10:25:00.000Z",
    updated_at: "2024-12-04T10:38:00.000Z",
    client_name: "Jennifer Smith",
    client_email: "jsmith@acmemarketing.com",
    client_company: "ACME Marketing",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "CUA Agent navigating to presentation portal",
      "Waiting for PDF download",
    ],
    value: 3200.0,
    workflow_steps: generateWorkflowSteps(
      "downloading_presentation",
      "2024-12-04T10:25:00.000Z"
    ),
    products_extracted: [],
    total_products: 0,
    products_processed: 0,
    presentation_pdf_url: null,
    output_json_url: null,
    errors: [],
  },

  // PARSING & QA
  {
    id: "job_4",
    source_link: "https://www.viewpresentation.com/66907679185",
    platform: "Sage",
    product_id: "AC-1234-ITEM-567",
    status: "awaiting_qa",
    progress: 90,
    created_at: "2024-12-03T13:30:00.000Z",
    updated_at: "2024-12-04T10:15:00.000Z",
    client_name: "Robert Martinez",
    client_email: "rmartinez@innovativegroup.com",
    client_company: "Innovative Group",
    mpn: "PRIME-12345",
    vendor: "Prime Line",
    vendor_website: "https://primeline.com",
    zoho_item_link: "https://books.zoho.com/app#/items/123456789",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/987654321",
    calculator_link: "https://docs.zoho.com/sheet/123456",
    action_items: [
      "Verify PMS match fee calculation",
      "Confirm vendor pricing accuracy",
      "Approve for Zoho import",
    ],
    value: 5400.5,
    workflow_steps: generateWorkflowSteps(
      "awaiting_qa",
      "2024-12-03T13:30:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "AC-1234-ITEM-567",
        name: "Custom Pen Set",
        vendor: "Prime Line",
        mpn: "PRIME-12345",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-1234-ITEM-568",
        name: "Notebook Bundle",
        vendor: "Prime Line",
        mpn: "PRIME-12346",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-1234-ITEM-569",
        name: "Desk Organizer",
        vendor: "Prime Line",
        mpn: "PRIME-12347",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 8,
    products_processed: 8,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/sage_20241203_133000/presentation.pdf",
    output_json_url: "s3://esp-quotes-bucket/sage_20241203_133000/output.json",
    errors: [],
  },
  {
    id: "job_5",
    source_link:
      "https://portal.mypromooffice.com/presentations/500180001?accessCode=xyz789",
    platform: "ESP",
    product_id: "CPN-564951234",
    status: "generating_output",
    progress: 75,
    created_at: "2024-12-04T08:00:00.000Z",
    updated_at: "2024-12-04T10:30:00.000Z",
    client_name: "Lisa Wong",
    client_email: "lwong@blueprintevents.com",
    client_company: "Blueprint Events",
    mpn: "VEST-8823",
    vendor: "Vest Promotions",
    vendor_website: "https://vestpromo.com",
    zoho_item_link: "https://books.zoho.com/app#/items/987654",
    zoho_quote_link: null,
    calculator_link: "https://docs.zoho.com/sheet/999999",
    action_items: [
      "Aggregating parsed data into JSON",
      "Formatting for Zoho import",
    ],
    value: 4125.75,
    workflow_steps: generateWorkflowSteps(
      "generating_output",
      "2024-12-04T08:00:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-564951234",
        name: "Branded Vest",
        vendor: "Vest Promotions",
        mpn: "VEST-8823",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564951235",
        name: "Polo Shirt",
        vendor: "Vest Promotions",
        mpn: "VEST-8824",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564951236",
        name: "Cap Collection",
        vendor: "Vest Promotions",
        mpn: "VEST-8825",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564951237",
        name: "Jacket Premium",
        vendor: "Vest Promotions",
        mpn: "VEST-8826",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 18,
    products_processed: 18,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_080000/presentation.pdf",
    output_json_url: null,
    errors: [],
  },

  // COMPLETED JOBS
  {
    id: "job_6",
    source_link:
      "https://portal.mypromooffice.com/presentations/888?accessCode=completed123",
    platform: "ESP",
    product_id: "CPN-99887766",
    status: "completed",
    progress: 100,
    created_at: "2024-12-02T10:00:00.000Z",
    updated_at: "2024-12-02T11:00:00.000Z",
    client_name: "David Lee",
    client_email: "dlee@summitenterprises.com",
    client_company: "Summit Enterprises",
    mpn: "HIT-5500",
    vendor: "Hit Promo",
    vendor_website: "https://hitpromo.net",
    zoho_item_link: "https://books.zoho.com/app#/items/555555",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/444444",
    calculator_link: "https://docs.zoho.com/sheet/333333",
    action_items: [],
    value: 890.0,
    workflow_steps: generateWorkflowSteps(
      "completed",
      "2024-12-02T10:00:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-99887766",
        name: "Promotional Mug",
        vendor: "Hit Promo",
        mpn: "HIT-5500",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-99887767",
        name: "Water Bottle",
        vendor: "Hit Promo",
        mpn: "HIT-5501",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 5,
    products_processed: 5,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241202_100000/presentation.pdf",
    output_json_url: "s3://esp-quotes-bucket/esp_20241202_100000/output.json",
    errors: [],
  },
  {
    id: "job_7",
    source_link: "https://www.viewpresentation.com/12345678",
    platform: "Sage",
    product_id: "AC-9876-ITEM-543",
    status: "completed",
    progress: 100,
    created_at: "2024-12-01T14:20:00.000Z",
    updated_at: "2024-12-01T16:45:00.000Z",
    client_name: "Amanda Rodriguez",
    client_email: "arodriguez@creativehub.co",
    client_company: "Creative Hub",
    mpn: "SAGE-99999",
    vendor: "Sage Solutions",
    vendor_website: "https://sagesolutions.com",
    zoho_item_link: "https://books.zoho.com/app#/items/111111",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/222222",
    calculator_link: "https://docs.zoho.com/sheet/111111",
    action_items: [],
    value: 7250.0,
    workflow_steps: generateWorkflowSteps(
      "completed",
      "2024-12-01T14:20:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "AC-9876-ITEM-543",
        name: "Executive Portfolio",
        vendor: "Sage Solutions",
        mpn: "SAGE-99999",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-9876-ITEM-544",
        name: "Leather Padfolio",
        vendor: "Sage Solutions",
        mpn: "SAGE-99998",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-9876-ITEM-545",
        name: "Business Card Holder",
        vendor: "Sage Solutions",
        mpn: "SAGE-99997",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 12,
    products_processed: 12,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/sage_20241201_142000/presentation.pdf",
    output_json_url: "s3://esp-quotes-bucket/sage_20241201_142000/output.json",
    errors: [],
  },
  {
    id: "job_8",
    source_link:
      "https://portal.mypromooffice.com/presentations/500170000?accessCode=tote789",
    platform: "ESP",
    product_id: "CPN-564987654",
    status: "completed",
    progress: 100,
    created_at: "2024-12-03T09:00:00.000Z",
    updated_at: "2024-12-03T12:30:00.000Z",
    client_name: "Tom Baker",
    client_email: "tbaker@venturecorp.net",
    client_company: "Venture Corp",
    mpn: "TOTE-4456",
    vendor: "Tote Bags Plus",
    vendor_website: "https://totebags.com",
    zoho_item_link: "https://books.zoho.com/app#/items/333333",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/555555",
    calculator_link: "https://docs.zoho.com/sheet/777777",
    action_items: [],
    value: 1650.0,
    workflow_steps: generateWorkflowSteps(
      "completed",
      "2024-12-03T09:00:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-564987654",
        name: "Canvas Tote",
        vendor: "Tote Bags Plus",
        mpn: "TOTE-4456",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "CPN-564987655",
        name: "Eco Bag",
        vendor: "Tote Bags Plus",
        mpn: "TOTE-4457",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
    ],
    total_products: 7,
    products_processed: 7,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241203_090000/presentation.pdf",
    output_json_url: "s3://esp-quotes-bucket/esp_20241203_090000/output.json",
    errors: [],
  },

  // NEW/EMAIL RECEIVED
  {
    id: "job_9",
    source_link:
      "https://portal.mypromooffice.com/presentations/500190001?accessCode=newjob123",
    platform: "ESP",
    product_id: "Pending",
    status: "email_received",
    progress: 10,
    created_at: "2024-12-04T10:50:00.000Z",
    updated_at: "2024-12-04T10:50:00.000Z",
    client_name: "Karen Thompson",
    client_email: "kthompson@nextgenbrands.com",
    client_company: "NextGen Brands",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "Queued for presentation download",
      "CUA Agent initializing",
    ],
    value: 2100.0,
    workflow_steps: generateWorkflowSteps(
      "email_received",
      "2024-12-04T10:50:00.000Z"
    ),
    products_extracted: [],
    total_products: 0,
    products_processed: 0,
    presentation_pdf_url: null,
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_10",
    source_link: "https://www.viewpresentation.com/99999999",
    platform: "Sage",
    product_id: "Pending",
    status: "email_received",
    progress: 5,
    created_at: "2024-12-04T10:55:00.000Z",
    updated_at: "2024-12-04T10:55:00.000Z",
    client_name: "James Wilson",
    client_email: "jwilson@fusiongroup.io",
    client_company: "Fusion Group",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: ["Awaiting CUA Agent availability"],
    value: 0.0,
    workflow_steps: generateWorkflowSteps(
      "email_received",
      "2024-12-04T10:55:00.000Z"
    ),
    products_extracted: [],
    total_products: 0,
    products_processed: 0,
    presentation_pdf_url: null,
    output_json_url: null,
    errors: [],
  },

  // ADDITIONAL ACTIVE JOBS
  {
    id: "job_11",
    source_link:
      "https://portal.mypromooffice.com/presentations/500183020?accessCode=pen456",
    platform: "ESP",
    product_id: "CPN-564951456",
    status: "parsing_presentation",
    progress: 32,
    created_at: "2024-12-04T10:28:00.000Z",
    updated_at: "2024-12-04T10:35:00.000Z",
    client_name: "Emily Davis",
    client_email: "edavis@horizonmarketing.com",
    client_company: "Horizon Marketing",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "Claude Opus 4.5 extracting product list from presentation PDF",
    ],
    value: 1825.0,
    workflow_steps: generateWorkflowSteps(
      "parsing_presentation",
      "2024-12-04T10:28:00.000Z"
    ),
    products_extracted: [],
    total_products: 0,
    products_processed: 0,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_102800/presentation.pdf",
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_12",
    source_link:
      "https://portal.mypromooffice.com/presentations/500185555?accessCode=apex999",
    platform: "ESP",
    product_id: "CPN-564951789",
    status: "downloading_product_pdfs",
    progress: 28,
    created_at: "2024-12-04T10:32:00.000Z",
    updated_at: "2024-12-04T10:33:00.000Z",
    client_name: "Chris Anderson",
    client_email: "canderson@apexsolutions.com",
    client_company: "Apex Solutions",
    mpn: "HAT-2211",
    vendor: "Hat Concepts",
    vendor_website: "https://hatconcepts.com",
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "CUA Agent processing product 3/10",
      "ESP+ product search in progress",
    ],
    value: 2450.0,
    workflow_steps: generateWorkflowSteps(
      "downloading_product_pdfs",
      "2024-12-04T10:32:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "CPN-564951789",
        name: "Custom Cap",
        vendor: "Hat Concepts",
        mpn: "HAT-2211",
        pdf_downloaded: true,
        pdf_parsed: false,
      },
      {
        cpn: "CPN-564951790",
        name: "Beanie Pro",
        vendor: "Hat Concepts",
        mpn: "HAT-2212",
        pdf_downloaded: true,
        pdf_parsed: false,
      },
      {
        cpn: "CPN-564951791",
        name: "Sun Hat",
        vendor: "Hat Concepts",
        mpn: "HAT-2213",
        pdf_downloaded: false,
        pdf_parsed: false,
      },
    ],
    total_products: 10,
    products_processed: 2,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_103200/presentation.pdf",
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_13",
    source_link: "https://www.viewpresentation.com/77777777",
    platform: "Sage",
    product_id: "AC-2222-ITEM-999",
    status: "parsing_product_pdfs",
    progress: 82,
    created_at: "2024-12-04T07:15:00.000Z",
    updated_at: "2024-12-04T10:28:00.000Z",
    client_name: "Patricia Moore",
    client_email: "pmoore@prestigecompany.com",
    client_company: "Prestige Company",
    mpn: "SAGE-55555",
    vendor: "Sage Premium",
    vendor_website: "https://sagepremium.com",
    zoho_item_link: "https://books.zoho.com/app#/items/444444",
    zoho_quote_link: null,
    calculator_link: "https://docs.zoho.com/sheet/555555",
    action_items: [
      "Claude parsing product 9/11 PDF",
      "Extracting distributor pricing tiers",
    ],
    value: 6200.0,
    workflow_steps: generateWorkflowSteps(
      "parsing_product_pdfs",
      "2024-12-04T07:15:00.000Z"
    ),
    products_extracted: [
      {
        cpn: "AC-2222-ITEM-999",
        name: "Premium Folder",
        vendor: "Sage Premium",
        mpn: "SAGE-55555",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-2222-ITEM-1000",
        name: "Desk Set",
        vendor: "Sage Premium",
        mpn: "SAGE-55556",
        pdf_downloaded: true,
        pdf_parsed: true,
      },
      {
        cpn: "AC-2222-ITEM-1001",
        name: "Pen Collection",
        vendor: "Sage Premium",
        mpn: "SAGE-55557",
        pdf_downloaded: true,
        pdf_parsed: false,
      },
    ],
    total_products: 11,
    products_processed: 9,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/sage_20241204_071500/presentation.pdf",
    output_json_url: null,
    errors: [],
  },
  {
    id: "job_14",
    source_link:
      "https://portal.mypromooffice.com/presentations/500186000?accessCode=impact123",
    platform: "ESP",
    product_id: "Pending",
    status: "downloading_presentation",
    progress: 22,
    created_at: "2024-12-04T10:40:00.000Z",
    updated_at: "2024-12-04T10:42:00.000Z",
    client_name: "Daniel Kim",
    client_email: "dkim@impactgroup.com",
    client_company: "Impact Group",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [
      "CUA Agent navigating presentation portal",
      "Locating download button",
    ],
    value: 1575.0,
    workflow_steps: generateWorkflowSteps(
      "downloading_presentation",
      "2024-12-04T10:40:00.000Z"
    ),
    products_extracted: [],
    total_products: 0,
    products_processed: 0,
    presentation_pdf_url: null,
    output_json_url: null,
    errors: [],
  },
  // ERROR STATE JOB
  {
    id: "job_15",
    source_link:
      "https://portal.mypromooffice.com/presentations/500181234?accessCode=error999",
    platform: "ESP",
    product_id: "CPN-564900000",
    status: "error",
    progress: 45,
    created_at: "2024-12-04T09:00:00.000Z",
    updated_at: "2024-12-04T09:25:00.000Z",
    client_name: "Mark Stevens",
    client_email: "mstevens@failedcorp.com",
    client_company: "Failed Corp",
    mpn: "ERR-1234",
    vendor: "Unknown Vendor",
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: ["Retry product lookup", "Contact support if issue persists"],
    value: 0,
    workflow_steps: [
      {
        step: 1,
        name: "Email Received",
        status: "completed",
        started_at: "2024-12-04T09:00:00.000Z",
        completed_at: "2024-12-04T09:00:00.000Z",
      },
      {
        step: 2,
        name: "Download Presentation",
        status: "completed",
        started_at: "2024-12-04T09:01:00.000Z",
        completed_at: "2024-12-04T09:05:00.000Z",
      },
      {
        step: 3,
        name: "Parse Presentation",
        status: "completed",
        started_at: "2024-12-04T09:05:00.000Z",
        completed_at: "2024-12-04T09:10:00.000Z",
      },
      {
        step: 4,
        name: "Download Product PDFs",
        status: "error",
        started_at: "2024-12-04T09:10:00.000Z",
        details: "CUA Agent failed to locate product in ESP+",
      },
      { step: 5, name: "Parse Product PDFs", status: "pending" },
      { step: 6, name: "Generate Output", status: "pending" },
      { step: 7, name: "QA Review", status: "pending" },
    ],
    products_extracted: [
      {
        cpn: "CPN-564900000",
        name: "Mystery Product",
        vendor: "Unknown Vendor",
        mpn: "ERR-1234",
        pdf_downloaded: false,
        pdf_parsed: false,
        error: "Product not found in ESP+",
      },
    ],
    total_products: 3,
    products_processed: 0,
    presentation_pdf_url:
      "s3://esp-quotes-bucket/esp_20241204_090000/presentation.pdf",
    output_json_url: null,
    errors: [
      "CUA Agent failed: Product CPN-564900000 not found in ESP+ search",
      "Timeout after 5 retries",
    ],
  },
];
