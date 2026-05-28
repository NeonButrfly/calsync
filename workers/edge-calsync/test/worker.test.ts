import {
  createExecutionContext,
  env,
  waitOnExecutionContext,
} from "cloudflare:test";
import { describe, expect, it } from "vitest";

import worker from "../src/index";

describe("edge worker smoke", () => {
  it("returns 401 when auth is missing", async () => {
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments",
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(401);
  });
});
