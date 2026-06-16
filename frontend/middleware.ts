import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_NAME = "dashboard_auth";

// Recompute the same token hash the login route produces:
// SHA-256(`${timestamp}:${AUTH_TOKEN_SECRET}`)
async function expectedHash(timestamp: number): Promise<string> {
  const secret = process.env.AUTH_TOKEN_SECRET || "default-secret-change-me";
  const data = `${timestamp}:${secret}`;
  const hashBuffer = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(data),
  );
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

function redirectToLogin(
  request: NextRequest,
  pathname: string,
  clear = false,
) {
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("redirect", pathname);
  const response = NextResponse.redirect(loginUrl);
  if (clear) response.cookies.delete(AUTH_COOKIE_NAME);
  return response;
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

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

  const authCookie = request.cookies.get(AUTH_COOKIE_NAME);
  if (!authCookie?.value) {
    return redirectToLogin(request, pathname);
  }

  try {
    const [timestampStr, hash] = authCookie.value.split(":");
    const timestamp = parseInt(timestampStr, 10);

    if (!Number.isFinite(timestamp) || !hash) {
      return redirectToLogin(request, pathname, true);
    }

    const now = Date.now();
    const twentyFourHours = 24 * 60 * 60 * 1000;
    // Reject expired tokens and tokens dated absurdly in the future.
    if (now - timestamp > twentyFourHours || timestamp - now > 60_000) {
      return redirectToLogin(request, pathname, true);
    }

    // Verify the signature — this is the check the old code was missing.
    const expected = await expectedHash(timestamp);
    if (!timingSafeEqual(hash, expected)) {
      return redirectToLogin(request, pathname, true);
    }

    return NextResponse.next();
  } catch {
    return redirectToLogin(request, pathname, true);
  }
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
