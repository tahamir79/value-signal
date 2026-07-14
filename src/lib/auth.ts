import { betterAuth } from "better-auth";
import { Kysely, PostgresDialect } from "kysely";
import { Pool } from "pg";
import { isAuthConfigured } from "@/lib/auth-config";

const database = process.env.DATABASE_URL
  ? new Kysely({
      dialect: new PostgresDialect({
        pool: new Pool({
          connectionString: process.env.DATABASE_URL,
          connectionTimeoutMillis: 10_000,
        }),
      }),
    })
  : undefined;

export const auth = betterAuth({
  appName: "ValueSignal",
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
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
