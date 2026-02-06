import { NextRequest, NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";

export async function GET(req: NextRequest) {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const { searchParams } = new URL(req.url);
  const month = searchParams.get("month") || new Date().toISOString().slice(0, 7);

  const summary = await prisma.monthlySummary.findUnique({
    where: { userId_month: { userId: session.user.id, month } },
  });

  // Get daily spending for the month
  const startDate = new Date(`${month}-01`);
  const endDate = new Date(startDate);
  endDate.setMonth(endDate.getMonth() + 1);

  const transactions = await prisma.transaction.findMany({
    where: {
      userId: session.user.id,
      date: { gte: startDate, lt: endDate },
    },
    include: { category: true },
    orderBy: { date: "asc" },
  });

  // Daily spending aggregation
  const dailySpending: Record<string, number> = {};
  const categoryTotals: Record<string, { amount: number; color: string }> = {};

  for (const tx of transactions) {
    const day = tx.date.toISOString().slice(0, 10);
    const amount = Number(tx.amount);

    if (tx.type === "EXPENSE") {
      dailySpending[day] = (dailySpending[day] || 0) + amount;
    }

    const catName = tx.category?.name || "Uncategorized";
    const catColor = tx.category?.color || "#6b7280";
    if (!categoryTotals[catName]) {
      categoryTotals[catName] = { amount: 0, color: catColor };
    }
    if (tx.type === "EXPENSE") {
      categoryTotals[catName].amount += amount;
    }
  }

  const transactionCount = transactions.length;

  return NextResponse.json({
    summary: summary || {
      totalIncome: 0,
      totalExpense: 0,
      netSavings: 0,
      categoryBreakdown: {},
    },
    dailySpending: Object.entries(dailySpending).map(([date, amount]) => ({
      date,
      amount,
    })),
    categoryTotals: Object.entries(categoryTotals)
      .map(([name, data]) => ({
        name,
        amount: data.amount,
        color: data.color,
      }))
      .filter((c) => c.amount > 0)
      .sort((a, b) => b.amount - a.amount),
    transactionCount,
    recentTransactions: transactions.slice(-10).reverse(),
  });
}
