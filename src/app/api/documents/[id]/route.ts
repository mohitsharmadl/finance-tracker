import { NextRequest, NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";
import { updateMonthlySummaries } from "@/lib/document-processor";
import * as fs from "fs";

export async function DELETE(
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

  // Delete transactions first
  await prisma.transaction.deleteMany({ where: { documentId: id } });

  // Delete document
  await prisma.document.delete({ where: { id } });

  // Delete file
  try {
    if (fs.existsSync(document.filePath)) {
      fs.unlinkSync(document.filePath);
    }
  } catch {
    // Ignore file deletion errors
  }

  await updateMonthlySummaries(session.user.id);

  return NextResponse.json({ success: true });
}
