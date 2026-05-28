export const CHANNEL_FLAGS = {
  chatgpt: "ENABLE_CHATGPT",
  shortcuts: "ENABLE_SHORTCUTS",
  alexa: "ENABLE_ALEXA",
  webhooks: "ENABLE_WEBHOOKS",
} as const;

export type ChannelName = keyof typeof CHANNEL_FLAGS;

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

export function isChannelEnabled(env: WorkerEnv, channel: ChannelName): boolean {
  return isEnabled(env[CHANNEL_FLAGS[channel]]);
}
