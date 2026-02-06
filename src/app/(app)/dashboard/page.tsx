"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowDownRight,
  ArrowUpRight,
  DollarSign,
  Loader2,
  PiggyBank,
  Receipt,
  TrendingUp,
} from "lucide-react";
import { format, subMonths } from "date-fns";
import { DailyChart } from "@/components/charts/daily-chart";
import { CategoryChart } from "@/components/charts/category-chart";
import { TrendsChart } from "@/components/charts/trends-chart";

interface SummaryData {
  summary: {
    totalIncome: number;
    totalExpense: number;
    netSavings: number;
    categoryBreakdown: Record<string, number>;
  };
  dailySpending: Array<{ date: string; amount: number }>;
  categoryTotals: Array<{ name: string; amount: number; color: string }>;
  transactionCount: number;
  recentTransactions: Array<{
    id: string;
    date: string;
    description: string;
    amount: string;
    type: string;
    category: { name: string; color: string } | null;
  }>;
}

interface TrendData {
  month: string;
  income: number;
  expense: number;
  savings: number;
}

function getMonthOptions() {
  const options = [];
  const now = new Date();
  for (let i = 0; i < 12; i++) {
    const d = subMonths(now, i);
    options.push({
      value: format(d, "yyyy-MM"),
      label: format(d, "MMMM yyyy"),
    });
  }
  return options;
}

export default function DashboardPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"));
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [trends, setTrends] = useState<TrendData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [summaryRes, trendsRes] = await Promise.all([
      fetch(`/api/analytics/summary?month=${month}`),
      fetch("/api/analytics/trends?months=6"),
    ]);

    if (summaryRes.ok) {
      setSummaryData(await summaryRes.json());
    }
    if (trendsRes.ok) {
      setTrends(await trendsRes.json());
    }
    setLoading(false);
  }, [month]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const monthOptions = getMonthOptions();

  if (loading || !summaryData) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const { summary, dailySpending, categoryTotals, transactionCount, recentTransactions } =
    summaryData;

  const income = Number(summary.totalIncome);
  const expense = Number(summary.totalExpense);
  const savings = Number(summary.netSavings);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Select value={month} onValueChange={setMonth}>
          <SelectTrigger className="w-[200px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {monthOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Income</CardTitle>
            <ArrowUpRight className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {income.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Expense</CardTitle>
            <ArrowDownRight className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-500">
              {expense.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Net Savings</CardTitle>
            <PiggyBank className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                savings >= 0 ? "text-green-500" : "text-red-500"
              }`}
            >
              {savings.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Transactions</CardTitle>
            <Receipt className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{transactionCount}</div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Daily Spending</CardTitle>
          </CardHeader>
          <CardContent>
            <DailyChart data={dailySpending} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Spending by Category</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryChart data={categoryTotals} />
          </CardContent>
        </Card>
      </div>

      {/* Trends */}
      <Card>
        <CardHeader>
          <CardTitle>Income vs Expense (6 Months)</CardTitle>
        </CardHeader>
        <CardContent>
          <TrendsChart data={trends} />
        </CardContent>
      </Card>

      {/* Recent Transactions */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {recentTransactions.length === 0 ? (
            <p className="py-8 text-center text-muted-foreground">
              No transactions this month.{" "}
              <Button
                variant="link"
                className="px-0"
                onClick={() => (window.location.href = "/upload")}
              >
                Upload a document
              </Button>
            </p>
          ) : (
            <div className="space-y-2">
              {recentTransactions.map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="h-2 w-2 rounded-full"
                      style={{
                        backgroundColor: tx.category?.color || "#6b7280",
                      }}
                    />
                    <div>
                      <p className="text-sm font-medium">{tx.description}</p>
                      <p className="text-xs text-muted-foreground">
                        {format(new Date(tx.date), "MMM d")}
                        {tx.category && ` · ${tx.category.name}`}
                      </p>
                    </div>
                  </div>
                  <span
                    className={`text-sm font-medium ${
                      tx.type === "INCOME" ? "text-green-500" : "text-red-500"
                    }`}
                  >
                    {tx.type === "INCOME" ? "+" : "-"}
                    {parseFloat(tx.amount).toLocaleString("en-IN", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
