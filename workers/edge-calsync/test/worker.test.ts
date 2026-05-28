import {
  createExecutionContext,
  env,
  waitOnExecutionContext,
} from "cloudflare:test";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import { sha256Hex } from "../src/auth";
import type { WorkerEnv } from "../src/env";

declare module "cloudflare:test" {
  interface ProvidedEnv extends WorkerEnv {}
}

describe("edge worker smoke", () => {
  beforeEach(async () => {
    vi.restoreAllMocks();
    await Promise.all([
      env.TOKEN_HASHES.delete("chatgpt"),
      env.TOKEN_HASHES.delete("shortcuts"),
      env.TOKEN_HASHES.delete("alexa"),
      env.TOKEN_HASHES.delete("webhooks"),
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 401 when auth is missing", async () => {
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments",
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      message: "Authentication required.",
    });
  });

  it("rejects invalid bearer tokens", async () => {
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments",
      {
        headers: {
          Authorization: "Bearer wrong-token",
        },
      },
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(401);
  });

  it("forwards list requests for valid chatgpt tokens", async () => {
    await env.TOKEN_HASHES.put("chatgpt", await sha256Hex("real-token"));
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/appointments?date_from=2026-06-01&date_to=2026-06-02",
        );
        expect(init?.headers).toBeInstanceOf(Headers);
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("chatgpt");
        expect(headers.get("X-CalSync-Request-Id")).toBeTruthy();

        return new Response(
          JSON.stringify({
            items: [
              {
                appointment_id: "appt-123",
                title: "Dentist",
                status: "active",
                date: "2026-06-01",
                start_time: "10:00",
                end_time: "11:00",
                timezone: "America/Anchorage",
                all_day: false,
              },
            ],
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        );
      });
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01&date_to=2026-06-02",
      {
        headers: {
          Authorization: "Bearer real-token",
        },
      },
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      message: "Appointments retrieved.",
      data: {
        items: [
          {
            title: "Dentist",
          },
        ],
      },
    });
  });

  it("returns 403 for disabled channels", async () => {
    await env.TOKEN_HASHES.put("shortcuts", await sha256Hex("shortcuts-token"));
    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01&date_to=2026-06-02",
      {
        headers: {
          Authorization: "Bearer shortcuts-token",
        },
      },
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      message: "This channel is disabled.",
    });
  });
});
