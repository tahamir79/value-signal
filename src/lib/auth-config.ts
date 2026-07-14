const REQUIRED_AUTH_ENV = [
  "BETTER_AUTH_SECRET",
  "BETTER_AUTH_URL",
  "GOOGLE_CLIENT_ID",
  "GOOGLE_CLIENT_SECRET",
  "DATABASE_URL",
] as const;

export type AuthEnvName = (typeof REQUIRED_AUTH_ENV)[number];

export function missingAuthEnv(): AuthEnvName[] {
  return REQUIRED_AUTH_ENV.filter((name) => !process.env[name]);
}

export function isAuthConfigured() {
  return missingAuthEnv().length === 0;
}

export function publicAuthDiagnostics() {
  const configuredBaseURL = process.env.BETTER_AUTH_URL || null;
  const resolvedBaseURL =
    process.env.VERCEL && configuredBaseURL?.includes("localhost")
      ? process.env.VERCEL_PROJECT_PRODUCTION_URL
        ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
        : process.env.VERCEL_URL
          ? `https://${process.env.VERCEL_URL}`
          : "https://value-signal.vercel.app"
      : configuredBaseURL || "http://localhost:3000";

  return {
    missing: missingAuthEnv(),
    configuredBaseURL,
    resolvedBaseURL,
    vercel: Boolean(process.env.VERCEL),
    hasTrustedOrigins: Boolean(process.env.BETTER_AUTH_TRUSTED_ORIGINS),
  };
}
