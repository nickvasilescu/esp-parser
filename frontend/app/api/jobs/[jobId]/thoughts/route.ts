import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params;
  const searchParams = request.nextUrl.searchParams;
  const afterLine = parseInt(searchParams.get("after") || "0", 10);
  const limit = parseInt(searchParams.get("limit") || "50", 10);

  // Path to thoughts file - try both possible locations
  const cwd = process.cwd();
  const possiblePaths = [
    path.join(cwd, "output", `job_${jobId}_thoughts.jsonl`),
    path.join(cwd, "..", "output", `job_${jobId}_thoughts.jsonl`),
    path.resolve(cwd, "output", `job_${jobId}_thoughts.jsonl`),
    path.resolve(cwd, "..", "output", `job_${jobId}_thoughts.jsonl`),
  ];

  // Find the first path that exists
  let filePath: string | null = null;
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      filePath = p;
      break;
    }
  }

  // Debug: log what we're looking for
  console.log(`[thoughts] CWD: ${cwd}`);
  console.log(`[thoughts] Looking for job: ${jobId}`);
  console.log(`[thoughts] Found at: ${filePath || 'NOT FOUND'}`);

  if (!filePath) {
    return NextResponse.json({
      thoughts: [],
      total_lines: 0,
      next_offset: 0,
      debug: { cwd, possiblePaths, jobId }
    });
  }

  try {
    const content = fs.readFileSync(filePath, "utf-8");
    const lines = content.trim().split("\n").filter(Boolean);

    // Return only lines after the requested position
    const newLines = lines.slice(afterLine, afterLine + limit);
    const thoughts = newLines.map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    }).filter(Boolean);

    return NextResponse.json({
      thoughts,
      total_lines: lines.length,
      next_offset: afterLine + newLines.length,
    });
  } catch (error) {
    console.error("Error reading thoughts file:", error);
    return NextResponse.json(
      { error: "Failed to read thoughts", thoughts: [], total_lines: 0 },
      { status: 500 }
    );
  }
}
