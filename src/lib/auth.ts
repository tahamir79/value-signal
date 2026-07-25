import { betterAuth } from "better-auth";
import { Kysely, PostgresDialect } from "kysely";
import { isAuthConfigured } from "@/lib/auth-config";
import { getPostgresPool, hasDatabaseUrl } from "@/lib/postgres";

const database = hasDatabaseUrl()
  ? new Kysely({
      dialect: new PostgresDialect({
        pool: getPostgresPool(),
      }),
    })
  : undefined;

function getAuthBaseURL() {
  const configured = process.env.BETTER_AUTH_URL?.trim();
  if (configured && !(process.env.VERCEL && configured.includes("localhost"))) {
    return configured;
  }

  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  }

  if (process.env.VERCEL_URL) {
    return `https://${process.env.VERCEL_URL}`;
  }

  if (process.env.VERCEL) {
    return "https://value-signal.vercel.app";
  }

  return "http://localhost:3000";
}

export const auth = betterAuth({
  appName: "ValueSignal",
  baseURL: getAuthBaseURL(),
  secret: process.env.BETTER_AUTH_SECRET ?? "development-only-missing-better-auth-secret",
  database: database ? { db: database, type: "postgres" } : undefined,
  trustedOrigins: [
    "https://value-signal.vercel.app",
    "https://*.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
    ...(process.env.BETTER_AUTH_TRUSTED_ORIGINS?.split(",").map((origin) => origin.trim()).filter(Boolean) ?? []),
  ],
  socialProviders: isAuthConfigured()
    ? {
        google: {
          clientId: process.env.GOOGLE_CLIENT_ID as string,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
        },
      }
    : {},
});
