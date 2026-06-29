import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";

const ESP_PATTERN = /^https:\/\/portal\.mypromooffice\.com\/presentations\/\d+\?accessCode=[a-f0-9]+$/;
const SAGE_PATTERN = /^https:\/\/www\.viewpresentation\.com\/\d+$/;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { url } = body;

    if (!url || typeof url !== "string") {
      return NextResponse.json(
        { error: "URL is required" },
        { status: 400 }
      );
    }

    const trimmedUrl = url.trim();

    // Detect platform from URL
    let platform: string;
    if (ESP_PATTERN.test(trimmedUrl)) {
      platform = "ESP";
    } else if (SAGE_PATTERN.test(trimmedUrl)) {
      platform = "SAGE";
    } else {
      return NextResponse.json(
        { error: "Invalid URL. Must be an ESP or SAGE presentation URL." },
        { status: 400 }
      );
    }

    // Determine project root (frontend is inside the project)
    const projectRoot = path.join(process.cwd(), "..");
    const promoParserCmd = path.join(projectRoot, "venv", "bin", "promo-parser");

    if (!fs.existsSync(promoParserCmd)) {
      return NextResponse.json(
        { error: "promo-parser command not found on server" },
        { status: 500 }
      );
    }

    // Spawn workflow WITHOUT --email-context (no email sent)
    const args = [
      trimmedUrl,
      "--zoho-upload",
      "--zoho-quote",
      "--calculator",
      "--verbose",
    ];

    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const logPath = path.join(projectRoot, "email_trigger", `workflow_manual_${timestamp}.log`);
    const logFd = fs.openSync(logPath, "w");

    // Spawn detached process with stdio going to log file
    const child = spawn(promoParserCmd, args, {
      cwd: projectRoot,
      env: process.env,
      detached: true,
      stdio: ["ignore", logFd, logFd],
    });

    child.unref();
    fs.closeSync(logFd);

    return NextResponse.json({
      success: true,
      platform,
      message: `${platform} workflow started`,
    });
  } catch (error) {
    console.error("Error triggering workflow:", error);
    return NextResponse.json(
      { error: "Failed to trigger workflow" },
      { status: 500 }
    );
  }
}
