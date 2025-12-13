import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

interface JobState {
  job_id: string;
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

export async function GET(request: NextRequest) {
  // Path to output folder (relative to dashboard-ui, go up to root then into output)
  const outputDir = path.join(process.cwd(), "..", "output");

  if (!fs.existsSync(outputDir)) {
    return NextResponse.json({ jobs: [] });
  }

  try {
    const files = fs.readdirSync(outputDir);

    // Find all job state files
    const stateFiles = files.filter(
      (f) => f.startsWith("job_") && f.endsWith("_state.json")
    );

    const jobs = stateFiles
      .map((file) => {
        try {
          const content = fs.readFileSync(path.join(outputDir, file), "utf-8");
          const state: JobState = JSON.parse(content);
          return {
            id: state.job_id,
            status: state.status,
            platform: state.platform,
            progress: state.progress,
            current_item: state.current_item,
            total_items: state.total_items,
            current_item_name: state.current_item_name,
            features: state.features,
            started_at: state.started_at,
            updated_at: state.updated_at,
            presentation_pdf_url: state.presentation_pdf_url,
            output_json_url: state.output_json_url,
            zoho_item_link: state.zoho_item_link,
            zoho_quote_link: state.zoho_quote_link,
            calculator_link: state.calculator_link,
            errors: state.errors,
          };
        } catch {
          return null;
        }
      })
      .filter(Boolean)
      // Sort by started_at descending (most recent first)
      .sort((a, b) => {
        const dateA = new Date(a!.started_at).getTime();
        const dateB = new Date(b!.started_at).getTime();
        return dateB - dateA;
      });

    return NextResponse.json({ jobs });
  } catch (error) {
    console.error("Error reading jobs:", error);
    return NextResponse.json({ jobs: [], error: "Failed to read jobs" }, { status: 500 });
  }
}
