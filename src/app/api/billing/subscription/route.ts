import { NextResponse } from "next/server";
import { entitlementForUser } from "@/lib/billing-store";
import { getCurrentSession } from "@/lib/server-auth";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const session = await getCurrentSession();
  const entitlement = await entitlementForUser(session?.user?.id);
  return NextResponse.json({ entitlement });
}
