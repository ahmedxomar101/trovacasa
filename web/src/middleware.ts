import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE = "milan_auth";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow login page, login API, and Telegram webhook
  if (pathname === "/login" || pathname === "/api/login" || pathname === "/api/telegram/webhook") {
    return NextResponse.next();
  }

  // Check auth cookie
  const token = request.cookies.get(AUTH_COOKIE)?.value;
  if (token !== process.env.SITE_PASSWORD) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    // Match all routes except static files and Next.js internals
    "/((?!_next/static|_next/image|icon.svg|favicon.ico).*)",
  ],
};
