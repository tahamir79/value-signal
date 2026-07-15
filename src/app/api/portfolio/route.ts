import { NextResponse, type NextRequest } from "next/server";
import { getCurrentSession } from "@/lib/server-auth";
import { addPortfolioPosition, listPortfolio, validatePortfolioInput } from "@/lib/user-data-store";

function error(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

async function requireUserId() {
  const session = await getCurrentSession();
  return session?.user?.id ?? null;
}

export async function GET() {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to view Portfolio positions.", 401);

  try {
    return NextResponse.json({ records: await listPortfolio(userId) });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not load Portfolio positions.", 503);
  }
}

export async function POST(request: NextRequest) {
  const userId = await requireUserId();
  if (!userId) return error("Google sign-in is required to save a Portfolio position.", 401);

  try {
    const record = await addPortfolioPosition(userId, validatePortfolioInput(await request.json()));
    return NextResponse.json({ record }, { status: 201 });
  } catch (err) {
    return error(err instanceof Error ? err.message : "Could not save Portfolio position.");
  }
}
