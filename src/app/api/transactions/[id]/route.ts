import { NextRequest, NextResponse } from "next/server";
import { requireAuth, unauthorized } from "@/lib/auth-helpers";
import { prisma } from "@/lib/prisma";
import { updateMonthlySummaries } from "@/lib/document-processor";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const { id } = await params;
  const body = await req.json();

  const transaction = await prisma.transaction.findUnique({
    where: { id, userId: session.user.id },
  });

  if (!transaction) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const updateData: Record<string, unknown> = {};
  if (body.categoryId !== undefined) updateData.categoryId = body.categoryId;
  if (body.notes !== undefined) updateData.notes = body.notes;
  if (body.description !== undefined) updateData.description = body.description;
  if (body.type !== undefined) updateData.type = body.type;

  const updated = await prisma.transaction.update({
    where: { id },
    data: updateData,
    include: { category: true },
  });

  await updateMonthlySummaries(session.user.id);

  return NextResponse.json(updated);
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await requireAuth();
  if (!session) return unauthorized();

  const { id } = await params;

  const transaction = await prisma.transaction.findUnique({
    where: { id, userId: session.user.id },
  });

  if (!transaction) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  await prisma.transaction.delete({ where: { id } });
  await updateMonthlySummaries(session.user.id);

  return NextResponse.json({ success: true });
}
