import { env } from "cloudflare:test";
import { beforeEach, describe, expect, it } from "vitest";

import { sha256Hex, validateChannelToken } from "../src/auth";
import type { WorkerEnv } from "../src/env";

declare module "cloudflare:test" {
  interface ProvidedEnv extends WorkerEnv {}
}

describe("channel token auth", () => {
  beforeEach(async () => {
    await Promise.all([
      env.TOKEN_HASHES.delete("chatgpt"),
      env.TOKEN_HASHES.delete("shortcuts"),
      env.TOKEN_HASHES.delete("alexa"),
      env.TOKEN_HASHES.delete("webhooks"),
    ]);
  });

  it("returns null when auth is missing", async () => {
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments",
    );

    await expect(validateChannelToken(request, env)).resolves.toBeNull();
  });

  it("matches a hashed token to the chatgpt channel", async () => {
    await env.TOKEN_HASHES.put("chatgpt", await sha256Hex("real-token"));
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments",
      {
        headers: {
          Authorization: "Bearer real-token",
        },
      },
    );

    await expect(validateChannelToken(request, env)).resolves.toBe("chatgpt");
  });
});
