import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession } from "@/lib/server-auth";
import { removeWatchlistItem, updateWatchlistAlerts } from "@/lib/user-data-store";

function error(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

async function requireUserId() {
  const session = await getCurrentSession();
  return session?.user?.id ?? null;
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ ticker: string }> }) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to update Watchlist alerts.", 401);

  try {
    const { ticker } = await params;
    const record = await updateWatchlistAlerts(userId, ticker, await request.json());
    if (!record) return error("Watchlist stock was not found.", 404);
    return NextResponse.json({ record });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not update Watchlist alerts.");
  }
}

export async function DELETE(_request: NextRequest, { params }: { params: Promise<{ ticker: string }> }) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to remove a Watchlist stock.", 401);

  try {
    const { ticker } = await params;
    const removed = await removeWatchlistItem(userId, ticker);
    return NextResponse.json({ removed });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not remove Watchlist stock.");
  }
}
