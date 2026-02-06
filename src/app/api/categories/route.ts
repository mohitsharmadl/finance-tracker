import { NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";

export async function GET() {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const categories = await prisma.category.findMany({
    where: {
      OR: [{ isDefault: true }, { userId: session.user.id }],
    },
    orderBy: { name: "asc" },
  });

  return NextResponse.json(categories);
}
