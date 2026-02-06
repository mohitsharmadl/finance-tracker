import Anthropic from "@anthropic-ai/sdk";
import { prisma } from "@/lib/prisma";
import { DocumentType } from "@/generated/prisma/client";
import { parse } from "csv-parse/sync";
import * as XLSX from "xlsx";
import * as fs from "fs";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY!,
});

interface ParsedTransaction {
  date: string;
  description: string;
  amount: number;
  type: "INCOME" | "EXPENSE" | "TRANSFER";
  category: string;
}

interface ParseResult {
  statement_month?: string;
  account_name?: string;
  transactions: ParsedTransaction[];
}

const SYSTEM_PROMPT = `You are a financial document parser. Extract transactions from the provided document and return structured JSON.

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{
  "statement_month": "YYYY-MM",
  "account_name": "Bank/Card name",
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "Transaction description",
      "amount": 1234.56,
      "type": "INCOME" or "EXPENSE" or "TRANSFER",
      "category": "Category name"
    }
  ]
}

Rules:
- amount should always be positive
- type determines if money came in (INCOME), went out (EXPENSE), or was transferred (TRANSFER)
- Use these categories: Salary, Freelance, Investment, Food & Dining, Groceries, Rent, Utilities, Transportation, Shopping, Entertainment, Healthcare, Insurance, Education, Travel, Subscriptions, ATM Withdrawal, Bank Fee, Transfer, Trading Profit, Trading Loss, Dividend, Interest, Other Income, Other Expense
- Parse dates into YYYY-MM-DD format
- For receipts, extract the single transaction with itemized description`;

export async function processDocument(documentId: string) {
  const document = await prisma.document.findUnique({
    where: { id: documentId },
  });

  if (!document) throw new Error("Document not found");

  await prisma.document.update({
    where: { id: documentId },
    data: { status: "PROCESSING" },
  });

  try {
    let result: ParseResult;

    if (document.documentType === "TRADING_PNL") {
      result = await parseSpreadsheet(document.filePath, document.fileType);
    } else if (
      document.fileType === "text/csv" ||
      document.fileName.endsWith(".csv")
    ) {
      result = await parseCsv(document.filePath);
    } else if (
      document.fileType.includes("spreadsheet") ||
      document.fileType.includes("excel") ||
      document.fileName.endsWith(".xlsx") ||
      document.fileName.endsWith(".xls")
    ) {
      result = await parseSpreadsheet(document.filePath, document.fileType);
    } else {
      result = await parseWithClaude(
        document.filePath,
        document.fileType,
        document.documentType
      );
    }

    // Match categories from DB
    const categories = await prisma.category.findMany({
      where: { OR: [{ isDefault: true }, { userId: document.userId }] },
    });

    const categoryMap = new Map(
      categories.map((c) => [c.name.toLowerCase(), c.id])
    );

    // Create transactions
    const txData = result.transactions.map((tx) => {
      const catId =
        categoryMap.get(tx.category.toLowerCase()) ||
        categoryMap.get("other expense") ||
        null;
      return {
        userId: document.userId,
        documentId: document.id,
        date: new Date(tx.date),
        description: tx.description,
        amount: tx.amount,
        type: tx.type as "INCOME" | "EXPENSE" | "TRANSFER",
        categoryId: catId,
        account: result.account_name || null,
      };
    });

    if (txData.length > 0) {
      await prisma.transaction.createMany({ data: txData });
    }

    await prisma.document.update({
      where: { id: documentId },
      data: {
        status: "COMPLETED",
        statementMonth: result.statement_month || null,
        rawResponse: JSON.stringify(result),
      },
    });

    // Update monthly summary
    await updateMonthlySummaries(document.userId);
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : "Unknown error";
    await prisma.document.update({
      where: { id: documentId },
      data: { status: "FAILED", errorMessage },
    });
    throw error;
  }
}

async function parseWithClaude(
  filePath: string,
  fileType: string,
  documentType: DocumentType
): Promise<ParseResult> {
  const fileBuffer = fs.readFileSync(filePath);
  const base64 = fileBuffer.toString("base64");

  const isPdf = fileType === "application/pdf";
  const isImage = fileType.startsWith("image/");

  const content: Anthropic.Messages.ContentBlockParam[] = [];

  if (isPdf) {
    content.push({
      type: "document",
      source: {
        type: "base64",
        media_type: "application/pdf",
        data: base64,
      },
    });
  } else if (isImage) {
    content.push({
      type: "image",
      source: {
        type: "base64",
        media_type: fileType as
          | "image/jpeg"
          | "image/png"
          | "image/gif"
          | "image/webp",
        data: base64,
      },
    });
  }

  content.push({
    type: "text",
    text: `This is a ${documentType.replace("_", " ").toLowerCase()}. Extract all transactions and return the JSON as specified.`,
  });

  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 4096,
    system: SYSTEM_PROMPT,
    messages: [{ role: "user", content }],
  });

  const textBlock = response.content.find((b) => b.type === "text");
  if (!textBlock || textBlock.type !== "text") {
    throw new Error("No text response from Claude");
  }

  // Clean any markdown wrapping
  let jsonText = textBlock.text.trim();
  if (jsonText.startsWith("```")) {
    jsonText = jsonText.replace(/^```(?:json)?\n?/, "").replace(/\n?```$/, "");
  }

  return JSON.parse(jsonText);
}

async function parseCsv(filePath: string): Promise<ParseResult> {
  const content = fs.readFileSync(filePath, "utf-8");
  const records = parse(content, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
  });

  return mapSpreadsheetRecords(records as Record<string, unknown>[]);
}

async function parseSpreadsheet(
  filePath: string,
  _fileType: string
): Promise<ParseResult> {
  const workbook = XLSX.readFile(filePath);
  const sheetName = workbook.SheetNames[0];
  const records = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName]);

  return mapSpreadsheetRecords(records as Record<string, unknown>[]);
}

function mapSpreadsheetRecords(
  records: Record<string, unknown>[]
): ParseResult {
  const transactions: ParsedTransaction[] = [];

  for (const row of records) {
    // Try to find date, description, amount columns (flexible column matching)
    const dateKey = findKey(row, ["date", "trade_date", "transaction_date", "txn_date", "value_date"]);
    const descKey = findKey(row, ["description", "narration", "particulars", "details", "instrument", "symbol"]);
    const amountKey = findKey(row, ["amount", "total", "net_amount", "pnl", "profit_loss", "net"]);
    const debitKey = findKey(row, ["debit", "withdrawal", "dr"]);
    const creditKey = findKey(row, ["credit", "deposit", "cr"]);
    const typeKey = findKey(row, ["type", "transaction_type", "txn_type"]);

    const dateVal = dateKey ? String(row[dateKey]) : null;
    const descVal = descKey ? String(row[descKey]) : "Unknown";

    if (!dateVal) continue;

    let amount = 0;
    let type: "INCOME" | "EXPENSE" | "TRANSFER" = "EXPENSE";

    if (amountKey) {
      amount = parseFloat(String(row[amountKey]).replace(/[^0-9.-]/g, "")) || 0;
      if (typeKey) {
        const t = String(row[typeKey]).toUpperCase();
        if (t.includes("INCOME") || t.includes("CREDIT") || t.includes("CR")) {
          type = "INCOME";
        } else if (t.includes("TRANSFER")) {
          type = "TRANSFER";
        }
      }
      if (amount < 0) {
        amount = Math.abs(amount);
        type = "EXPENSE";
      } else if (amount > 0 && !typeKey) {
        // For trading PnL: positive = profit (income), negative = loss (expense)
        type = "INCOME";
      }
    } else {
      const debit = debitKey
        ? parseFloat(String(row[debitKey]).replace(/[^0-9.-]/g, "")) || 0
        : 0;
      const credit = creditKey
        ? parseFloat(String(row[creditKey]).replace(/[^0-9.-]/g, "")) || 0
        : 0;
      if (credit > 0) {
        amount = credit;
        type = "INCOME";
      } else {
        amount = debit;
        type = "EXPENSE";
      }
    }

    // Parse date
    let parsedDate: string;
    try {
      const d = new Date(dateVal);
      if (isNaN(d.getTime())) {
        // Try DD/MM/YYYY or DD-MM-YYYY
        const parts = dateVal.split(/[/-]/);
        if (parts.length === 3) {
          const [dd, mm, yyyy] = parts;
          parsedDate = `${yyyy}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
        } else {
          continue;
        }
      } else {
        parsedDate = d.toISOString().split("T")[0];
      }
    } catch {
      continue;
    }

    transactions.push({
      date: parsedDate,
      description: descVal,
      amount: Math.abs(amount),
      type,
      category:
        type === "INCOME" ? "Trading Profit" : type === "EXPENSE" ? "Trading Loss" : "Transfer",
    });
  }

  return { transactions };
}

function findKey(
  obj: Record<string, unknown>,
  candidates: string[]
): string | null {
  const keys = Object.keys(obj).map((k) => k.toLowerCase().replace(/\s+/g, "_"));
  const originalKeys = Object.keys(obj);

  for (const candidate of candidates) {
    const idx = keys.indexOf(candidate);
    if (idx !== -1) return originalKeys[idx];
  }

  // Fuzzy match
  for (const candidate of candidates) {
    const idx = keys.findIndex((k) => k.includes(candidate));
    if (idx !== -1) return originalKeys[idx];
  }

  return null;
}

export async function updateMonthlySummaries(userId: string) {
  // Get all transactions grouped by month
  const transactions = await prisma.transaction.findMany({
    where: { userId },
    include: { category: true },
  });

  const monthMap = new Map<
    string,
    {
      income: number;
      expense: number;
      categories: Record<string, number>;
    }
  >();

  for (const tx of transactions) {
    const month = tx.date.toISOString().slice(0, 7); // YYYY-MM
    if (!monthMap.has(month)) {
      monthMap.set(month, { income: 0, expense: 0, categories: {} });
    }
    const entry = monthMap.get(month)!;
    const amount = Number(tx.amount);

    if (tx.type === "INCOME") {
      entry.income += amount;
    } else if (tx.type === "EXPENSE") {
      entry.expense += amount;
    }

    const catName = tx.category?.name || "Uncategorized";
    entry.categories[catName] = (entry.categories[catName] || 0) + amount;
  }

  for (const [month, data] of monthMap) {
    await prisma.monthlySummary.upsert({
      where: { userId_month: { userId, month } },
      update: {
        totalIncome: data.income,
        totalExpense: data.expense,
        netSavings: data.income - data.expense,
        categoryBreakdown: data.categories,
      },
      create: {
        userId,
        month,
        totalIncome: data.income,
        totalExpense: data.expense,
        netSavings: data.income - data.expense,
        categoryBreakdown: data.categories,
      },
    });
  }
}
