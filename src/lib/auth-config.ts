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

