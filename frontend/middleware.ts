import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "dashboard_auth";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip middleware for:
  // 1. API routes (don't protect)
  // 2. Login page (allow access)
  // 3. Static files and Next.js internals
  if (
    pathname.startsWith("/api") ||
    pathname === "/login" ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.endsWith(".ico") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".jpg") ||
    pathname.endsWith(".svg")
  ) {
    return NextResponse.next();
  }

  // Check for auth cookie
  const authCookie = request.cookies.get(AUTH_COOKIE_NAME);

  if (!authCookie?.value) {
    // No auth cookie, redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Validate the token format and expiration
  try {
    const [timestampStr, hash] = authCookie.value.split(":");
    const timestamp = parseInt(timestampStr, 10);

    // Check if token is expired (24 hours = 86400000 ms)
    const now = Date.now();
    const twentyFourHours = 24 * 60 * 60 * 1000;

    if (now - timestamp > twentyFourHours) {
      // Token expired, redirect to login
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      const response = NextResponse.redirect(loginUrl);
      response.cookies.delete(AUTH_COOKIE_NAME);
      return response;
    }

    // Verify hash exists and has minimum length
    if (!hash || hash.length < 16) {
      throw new Error("Invalid token format");
    }

    return NextResponse.next();
  } catch {
    // Invalid token, redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    const response = NextResponse.redirect(loginUrl);
    response.cookies.delete(AUTH_COOKIE_NAME);
    return response;
  }
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
