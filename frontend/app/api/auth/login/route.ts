import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const AUTH_COOKIE_NAME = "dashboard_auth";
const TWENTY_FOUR_HOURS = 24 * 60 * 60; // in seconds

async function generateToken(timestamp: number): Promise<string> {
  const secret = process.env.AUTH_TOKEN_SECRET || "default-secret-change-me";
  const data = `${timestamp}:${secret}`;

  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);
  const hashBuffer = await crypto.subtle.digest("SHA-256", dataBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");

  return `${timestamp}:${hashHex}`;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { password } = body;

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { success: false, error: "Password is required" },
        { status: 400 }
      );
    }

    const expectedPassword = process.env.DASHBOARD_PASSWORD;

    if (!expectedPassword) {
      console.error("DASHBOARD_PASSWORD environment variable is not set");
      return NextResponse.json(
        { success: false, error: "Server configuration error" },
        { status: 500 }
      );
    }

    const passwordsMatch = password === expectedPassword;

    if (!passwordsMatch) {
      return NextResponse.json(
        { success: false, error: "Invalid password" },
        { status: 401 }
      );
    }

    const timestamp = Date.now();
    const token = await generateToken(timestamp);

    const cookieStore = await cookies();
    cookieStore.set(AUTH_COOKIE_NAME, token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: TWENTY_FOUR_HOURS,
      path: "/",
    });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Login error:", error);
    return NextResponse.json(
      { success: false, error: "An error occurred" },
      { status: 500 }
    );
  }
}
