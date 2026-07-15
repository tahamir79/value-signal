import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession } from "@/lib/server-auth";
import { removePortfolioPosition, updatePortfolioPosition, validatePortfolioInput } from "@/lib/user-data-store";

function error(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

async function requireUserId() {
  const session = await getCurrentSession();
  return session?.user?.id ?? null;
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ positionId: string }> }) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to update a Portfolio position.", 401);

  try {
    const { positionId } = await params;
    const record = await updatePortfolioPosition(userId, positionId, validatePortfolioInput(await request.json()));
    if (!record) return error("Portfolio position was not found.", 404);
    return NextResponse.json({ record });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not update Portfolio position.");
  }
}

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ positionId: string }> }) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to remove a Portfolio position.", 401);

  try {
    const { positionId } = await params;
    const removed = await removePortfolioPosition(userId, positionId);
    return NextResponse.json({ removed });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not remove Portfolio position.");
  }
}
