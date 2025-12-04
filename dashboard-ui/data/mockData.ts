import { WorkflowStatus } from "../components/StatusBadge";

export interface Job {
  id: string;
  source_link: string;
  platform: "ESP" | "Sage";
  product_id: string;
  status: WorkflowStatus;
  progress: number;
  created_at: string;
  updated_at: string;
  mpn: string | null;
  vendor: string | null;
  vendor_website: string | null;
  zoho_item_link: string | null;
  zoho_quote_link: string | null;
  calculator_link: string | null;
  action_items: string[];
  value: number; // Estimated quote value
}

// Use static dates to avoid hydration mismatches between server and client
export const mockJobs: Job[] = [
  {
    id: "job_1",
    source_link:
      "https://portal.mypromooffice.com/projects/500187876/presentations/500183020/products",
    platform: "ESP",
    product_id: "CPN-564949909",
    status: "scraping_metadata",
    progress: 45,
    created_at: "2024-12-03T15:25:00.000Z",
    updated_at: "2024-12-03T15:30:00.000Z",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [],
    value: 1250.0,
  },
  {
    id: "job_2",
    source_link: "https://www.viewpresentation.com/66907679185",
    platform: "Sage",
    product_id: "AC-1234-ITEM-567",
    status: "awaiting_qa",
    progress: 90,
    created_at: "2024-12-03T13:30:00.000Z",
    updated_at: "2024-12-03T15:15:00.000Z",
    mpn: "PRIME-12345",
    vendor: "Prime Line",
    vendor_website: "https://primeline.com",
    zoho_item_link: "https://books.zoho.com/app#/items/123456789",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/987654321",
    calculator_link: "https://docs.zoho.com/sheet/123456",
    action_items: ["Verify PMS match fee"],
    value: 5400.5,
  },
  {
    id: "job_3",
    source_link:
      "https://portal.mypromooffice.com/projects/999/presentations/888",
    platform: "ESP",
    product_id: "CPN-99887766",
    status: "completed",
    progress: 100,
    created_at: "2024-12-02T10:00:00.000Z",
    updated_at: "2024-12-02T11:00:00.000Z",
    mpn: "HIT-5500",
    vendor: "Hit Promo",
    vendor_website: "https://hitpromo.net",
    zoho_item_link: "https://books.zoho.com/app#/items/555555",
    zoho_quote_link: "https://books.zoho.com/app#/quotes/444444",
    calculator_link: "https://docs.zoho.com/sheet/333333",
    action_items: [],
    value: 890.0,
  },
  {
    id: "job_4",
    source_link: "https://portal.mypromooffice.com/projects/new/123",
    platform: "ESP",
    product_id: "CPN-11223344",
    status: "email_received",
    progress: 10,
    created_at: "2024-12-03T15:29:30.000Z",
    updated_at: "2024-12-03T15:29:30.000Z",
    mpn: null,
    vendor: null,
    vendor_website: null,
    zoho_item_link: null,
    zoho_quote_link: null,
    calculator_link: null,
    action_items: [],
    value: 2100.0,
  },
];
