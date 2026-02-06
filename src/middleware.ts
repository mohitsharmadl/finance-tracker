import { NextRequest } from "next/server";
import { getToken } from "next-auth/jwt";
import { NextResponse } from "next/server";

export async function middleware(req: NextRequest) {
  const token = await getToken({ req });

  if (!token) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("callbackUrl", req.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/upload/:path*",
    "/transactions/:path*",
    "/documents/:path*",
    "/api/upload/:path*",
    "/api/documents/:path*",
    "/api/transactions/:path*",
    "/api/categories/:path*",
    "/api/analytics/:path*",
  ],
};
