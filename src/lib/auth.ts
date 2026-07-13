import { betterAuth } from "better-auth";
import { Pool } from "pg";
import { isAuthConfigured } from "@/lib/auth-config";

const database = process.env.DATABASE_URL ? new Pool({ connectionString: process.env.DATABASE_URL }) : undefined;

export const auth = betterAuth({
  appName: "ValueSignal",
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  secret: process.env.BETTER_AUTH_SECRET ?? "development-only-missing-better-auth-secret",
  database,
  socialProviders: isAuthConfigured()
    ? {
        google: {
          clientId: process.env.GOOGLE_CLIENT_ID as string,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
        },
      }
    : {},
});
