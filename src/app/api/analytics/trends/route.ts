import { NextRequest, NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const { searchParams } = new URL(req.url);
  const months = parseInt(searchParams.get("months") || "6");

  // Get last N months
  const now = new Date();
  const monthKeys: string[] = [];
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    monthKeys.push(d.toISOString().slice(0, 7));
  }

  const summaries = await prisma.monthlySummary.findMany({
    where: {
      userId: session.user.id,
      month: { in: monthKeys },
    },
    orderBy: { month: "asc" },
  });

  const summaryMap = new Map(summaries.map((s) => [s.month, s]));

  const trends = monthKeys.map((month) => {
    const s = summaryMap.get(month);
    return {
      month,
      income: s ? Number(s.totalIncome) : 0,
      expense: s ? Number(s.totalExpense) : 0,
      savings: s ? Number(s.netSavings) : 0,
    };
  });

  return NextResponse.json(trends);
}
