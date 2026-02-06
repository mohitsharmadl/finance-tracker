import { NextRequest, NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";
import { processDocument } from "@/lib/document-processor";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const { id } = await params;

  const document = await prisma.document.findUnique({
    where: { id, userId: session.user.id },
  });

  if (!document) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  // Delete existing transactions from this document
  await prisma.transaction.deleteMany({ where: { documentId: id } });

  // Reset status
  await prisma.document.update({
    where: { id },
    data: { status: "PENDING", errorMessage: null },
  });

  // Fire-and-forget reprocessing
  processDocument(id).catch((err) => {
    console.error(`Failed to reprocess document ${id}:`, err);
  });

  return NextResponse.json({ success: true });
}
