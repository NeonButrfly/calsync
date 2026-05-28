export interface WorkerEnv {
  TOKEN_HASHES: KVNamespace;
  ORIGIN_BASE_URL: string;
  ENABLE_CHATGPT: string;
  ENABLE_SHORTCUTS: string;
  ENABLE_ALEXA: string;
  ENABLE_WEBHOOKS: string;
  ENABLE_ADMIN_ROUTES: string;
}

export function isEnabled(value: string | undefined): boolean {
  return value === "true";
}
