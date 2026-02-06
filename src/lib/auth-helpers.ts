import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { NextResponse } from "next/server";

const DEV_SESSION = {
  user: {
    id: "dev-user-id",
    name: "Mohit Sharma",
    email: "mohit@mohitsharma.com",
  },
  expires: "2099-01-01T00:00:00.000Z",
};

export async function getSession() {
  if (process.env.SKIP_AUTH === "true") {
    return DEV_SESSION;
  }
  return getServerSession(authOptions);
}

export async function requireAuth() {
  const session = await getSession();
  if (!session?.user?.id) {
    return null;
  }
  return session;
}

export function unauthorized() {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}
