import { PrismaClient } from "../src/generated/prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import "dotenv/config";

const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL! });
const prisma = new PrismaClient({ adapter });

const defaultCategories = [
  // Income
  { name: "Salary", type: "INCOME" as const, color: "#22c55e", icon: "briefcase" },
  { name: "Freelance", type: "INCOME" as const, color: "#10b981", icon: "laptop" },
  { name: "Investment", type: "INCOME" as const, color: "#14b8a6", icon: "trending-up" },
  { name: "Dividend", type: "INCOME" as const, color: "#06b6d4", icon: "dollar-sign" },
  { name: "Interest", type: "INCOME" as const, color: "#0ea5e9", icon: "percent" },
  { name: "Trading Profit", type: "INCOME" as const, color: "#16a34a", icon: "chart-line" },
  { name: "Other Income", type: "INCOME" as const, color: "#84cc16", icon: "plus-circle" },

  // Expense
  { name: "Food & Dining", type: "EXPENSE" as const, color: "#ef4444", icon: "utensils" },
  { name: "Groceries", type: "EXPENSE" as const, color: "#f97316", icon: "shopping-cart" },
  { name: "Rent", type: "EXPENSE" as const, color: "#f59e0b", icon: "home" },
  { name: "Utilities", type: "EXPENSE" as const, color: "#eab308", icon: "zap" },
  { name: "Transportation", type: "EXPENSE" as const, color: "#84cc16", icon: "car" },
  { name: "Shopping", type: "EXPENSE" as const, color: "#a855f7", icon: "shopping-bag" },
  { name: "Entertainment", type: "EXPENSE" as const, color: "#ec4899", icon: "film" },
  { name: "Healthcare", type: "EXPENSE" as const, color: "#f43f5e", icon: "heart" },
  { name: "Insurance", type: "EXPENSE" as const, color: "#64748b", icon: "shield" },
  { name: "Education", type: "EXPENSE" as const, color: "#6366f1", icon: "book" },
  { name: "Travel", type: "EXPENSE" as const, color: "#8b5cf6", icon: "plane" },
  { name: "Subscriptions", type: "EXPENSE" as const, color: "#d946ef", icon: "repeat" },
  { name: "ATM Withdrawal", type: "EXPENSE" as const, color: "#78716c", icon: "banknote" },
  { name: "Bank Fee", type: "EXPENSE" as const, color: "#9ca3af", icon: "building" },
  { name: "Trading Loss", type: "EXPENSE" as const, color: "#dc2626", icon: "chart-line" },
  { name: "Other Expense", type: "EXPENSE" as const, color: "#6b7280", icon: "minus-circle" },

  // Transfer
  { name: "Transfer", type: "TRANSFER" as const, color: "#3b82f6", icon: "arrow-right-left" },
];

async function main() {
  console.log("Seeding default categories...");

  // Delete existing default categories and re-create
  await prisma.category.deleteMany({ where: { isDefault: true } });

  await prisma.category.createMany({
    data: defaultCategories.map((cat) => ({
      name: cat.name,
      type: cat.type,
      color: cat.color,
      icon: cat.icon,
      isDefault: true,
      userId: null,
    })),
  });

  const count = await prisma.category.count({ where: { isDefault: true } });
  console.log(`Seeded ${count} default categories`);
}

main()
  .then(() => prisma.$disconnect())
  .catch((e) => {
    console.error(e);
    prisma.$disconnect();
    process.exit(1);
  });
