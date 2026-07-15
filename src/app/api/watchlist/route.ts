import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession } from "@/lib/server-auth";
import { addWatchlistItem, listWatchlist } from "@/lib/user-data-store";

function error(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

async function requireUserId() {
  const session = await getCurrentSession();
  return session?.user?.id ?? null;
}

export async function GET() {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to view a Watchlist.", 401);

  try {
    return NextResponse.json({ records: await listWatchlist(userId) });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not load Watchlist.", 503);
  }
}

export async function POST(request: NextRequest) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to save a Watchlist stock.", 401);

  try {
    const body = await request.json();
    const record = await addWatchlistItem(userId, body?.ticker);
    return NextResponse.json({ record }, { status: 201 });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not save Watchlist stock.");
  }
}
