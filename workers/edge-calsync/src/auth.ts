import { CHANNEL_FLAGS, type ChannelName, type WorkerEnv } from "./env";

const encoder = new TextEncoder();
const channels = Object.keys(CHANNEL_FLAGS) as ChannelName[];

export function extractBearerToken(request: Request): string | null {
  const authorization = request.headers.get("Authorization");
  if (!authorization?.startsWith("Bearer ")) {
    return null;
  }

  const token = authorization.slice("Bearer ".length).trim();
  return token || null;
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export async function validateChannelToken(
  request: Request,
  env: WorkerEnv,
): Promise<ChannelName | null> {
  const token = extractBearerToken(request);
  if (!token) {
    return null;
  }

  const presentedHash = await sha256Hex(token);

  for (const channel of channels) {
    const expectedHash = await env.TOKEN_HASHES.get(channel);
    if (expectedHash && timingSafeEqualHex(expectedHash, presentedHash)) {
      return channel;
    }
  }

  return null;
}

function timingSafeEqualHex(left: string, right: string): boolean {
  if (left.length !== right.length) {
    return false;
  }

  const leftBytes = encoder.encode(left);
  const rightBytes = encoder.encode(right);
  let diff = 0;

  for (let index = 0; index < leftBytes.length; index += 1) {
    diff |= leftBytes[index] ^ rightBytes[index];
  }

  return diff === 0;
}
