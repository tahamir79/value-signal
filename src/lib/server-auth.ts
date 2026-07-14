import "server-only";
import { headers } from "next/headers";
import { auth } from "@/lib/auth";
import { isAuthConfigured } from "@/lib/auth-config";

export async function getCurrentSession() {
  if (!isAuthConfigured()) return null;

  try {
    return await auth.api.getSession({
      headers: await headers(),
    });
  } catch {
    return null;
  }
}
