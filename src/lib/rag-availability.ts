export function isLocalRagEnabled() {
  return process.env.NODE_ENV !== "production" && process.env.ENABLE_LOCAL_RAG !== "false";
}

