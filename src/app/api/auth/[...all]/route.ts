import { NextRequest, NextResponse } from "next/server";
import { toNextJsHandler } from "better-auth/next-js";
import { auth } from "@/lib/auth";
import { missingAuthEnv } from "@/lib/auth-config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const handlers = toNextJsHandler(auth);

function unavailable() {
  const missing = missingAuthEnv();
  if (!missing.length) return null;
  return NextResponse.json(
    {
      error: "ValueSignal authentication is not configured.",
      missing,
      nextStep: "Set Better Auth, Google OAuth, and PostgreSQL environment variables before using sign-in.",
    },
    { status: 503 },
  );
}

export async function GET(request: NextRequest) {
  return unavailable() ?? handlers.GET(request);
}

export async function POST(request: NextRequest) {
  return unavailable() ?? handlers.POST(request);
}

