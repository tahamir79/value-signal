import { NextResponse } from "next/server";
import { publicAuthDiagnostics } from "@/lib/auth-config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(publicAuthDiagnostics());
}
