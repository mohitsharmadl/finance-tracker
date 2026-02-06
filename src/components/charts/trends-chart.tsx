"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parse } from "date-fns";

interface TrendsChartProps {
  data: Array<{
    month: string;
    income: number;
    expense: number;
    savings: number;
  }>;
}

export function TrendsChart({ data }: TrendsChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted-foreground">
        No trend data
      </div>
    );
  }

  const formatted = data.map((d) => ({
    ...d,
    label: format(parse(d.month, "yyyy-MM", new Date()), "MMM yy"),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={formatted}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
        <XAxis dataKey="label" className="text-xs" tick={{ fontSize: 12 }} />
        <YAxis className="text-xs" tick={{ fontSize: 12 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
          }}
          formatter={(value: number | undefined) =>
            (value ?? 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })
          }
        />
        <Legend />
        <Area
          type="monotone"
          dataKey="income"
          name="Income"
          stroke="#22c55e"
          fill="#22c55e"
          fillOpacity={0.1}
        />
        <Area
          type="monotone"
          dataKey="expense"
          name="Expense"
          stroke="#ef4444"
          fill="#ef4444"
          fillOpacity={0.1}
        />
        <Area
          type="monotone"
          dataKey="savings"
          name="Savings"
          stroke="#3b82f6"
          fill="#3b82f6"
          fillOpacity={0.1}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
