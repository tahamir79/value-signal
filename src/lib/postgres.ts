import "server-only";

import { Pool, type QueryResult, type QueryResultRow } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var valueSignalPostgresPool: Pool | undefined;
}

export function hasDatabaseUrl() {
  return Boolean(process.env.DATABASE_URL);
}

export function getPostgresPool() {
  if (!process.env.DATABASE_URL) {
    throw new Error("DATABASE_URL is required for ValueSignal user records.");
  }

  globalThis.valueSignalPostgresPool ??= new Pool({
    connectionString: process.env.DATABASE_URL,
    max: Number(process.env.DATABASE_POOL_MAX || 1),
    idleTimeoutMillis: Number(process.env.DATABASE_IDLE_TIMEOUT_MS || 30_000),
    connectionTimeoutMillis: Number(process.env.DATABASE_CONNECTION_TIMEOUT_MS || 8_000),
    allowExitOnIdle: true,
  });

  return globalThis.valueSignalPostgresPool;
}

function isTransientPostgresError(error: unknown) {
  const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  return (
    message.includes("connection terminated") ||
    message.includes("connection timeout") ||
    message.includes("timeout exceeded") ||
    message.includes("econnreset") ||
    message.includes("terminating connection")
  );
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function postgresQuery<T extends QueryResultRow = QueryResultRow>(
  text: string,
  values?: readonly unknown[],
  attempts = 2,
): Promise<QueryResult<T>> {
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await getPostgresPool().query<T>(text, values ? [...values] : undefined);
    } catch (error) {
      lastError = error;
      if (attempt >= attempts || !isTransientPostgresError(error)) break;
      await wait(150 * attempt);
    }
  }

  throw lastError;
}
