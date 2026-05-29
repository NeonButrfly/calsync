import {
  createExecutionContext,
  env,
  waitOnExecutionContext,
} from "cloudflare:test";
import { afterEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";
import type { WorkerEnv } from "../src/env";

const { alexaVerifierMock } = vi.hoisted(() => ({
  alexaVerifierMock: vi.fn(async () => undefined),
}));

vi.mock("alexa-verifier", () => ({
  default: alexaVerifierMock,
}));

declare module "cloudflare:test" {
  interface ProvidedEnv extends WorkerEnv {}
}

function alexaEnv(): WorkerEnv {
  return {
    ...env,
    ENABLE_ALEXA: "true",
    ALEXA_ALLOWED_SKILL_IDS: "amzn1.ask.skill.test",
    ALEXA_DEFAULT_TIMEZONE: "America/Anchorage",
  };
}

function buildAlexaRequest(
  body: Record<string, unknown>,
  options?: {
    includeSignatureHeaders?: boolean;
  },
): Request {
  const includeSignatureHeaders = options?.includeSignatureHeaders ?? true;
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (includeSignatureHeaders) {
    headers.SignatureCertChainUrl =
      "https://s3.amazonaws.com/echo.api/echo-api-cert.pem";
    headers["Signature-256"] = "ZmFrZS1zaWduYXR1cmU=";
  }
  return new Request("https://edge-calsync.neonbutterfly.net/alexa", {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
}

describe("alexa worker adapter", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    alexaVerifierMock.mockClear();
  });

  it("returns a welcome response for launch requests", async () => {
    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "LaunchRequest",
        timestamp: new Date().toISOString(),
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      version: "1.0",
      response: {
        outputSpeech: {
          text: expect.stringContaining("Welcome to CalSync"),
        },
        shouldEndSession: false,
      },
    });
  });

  it("returns 400 when Alexa signature headers are missing", async () => {
    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "LaunchRequest",
        timestamp: new Date().toISOString(),
      },
    }, { includeSignatureHeaders: false });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      message: "Alexa signature headers are required.",
    });
  });

  it("creates an appointment through the shared origin path", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/appointments",
        );
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");
        const bodyText = String(init?.body);
        const body = JSON.parse(bodyText) as Record<string, string>;
        expect(body.title).toBe("Dentist");
        expect(body.end_time).toBe("11:00");

        return new Response(
          JSON.stringify({
            appointment_id: "appt-123",
            status: "active",
            provider_event_id: "provider-123",
            message: "Appointment created.",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        );
      });
    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "IntentRequest",
        timestamp: new Date().toISOString(),
        intent: {
          name: "CreateAppointmentIntent",
          slots: {
            title: { value: "Dentist" },
            date: { value: "2026-06-01" },
            start_time: { value: "10:00" },
            end_time: { value: "11:00" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("I added Dentist"),
        },
      },
    });
  });

  it("lists appointments for a requested date", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/appointments?date_from=2026-06-02&date_to=2026-06-02",
        );
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");

        return new Response(
          JSON.stringify({
            items: [
              {
                appointment_id: "appt-123",
                title: "Dentist",
                status: "active",
                date: "2026-06-02",
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
    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "IntentRequest",
        timestamp: new Date().toISOString(),
        intent: {
          name: "ListAppointmentsIntent",
          slots: {
            date: { value: "2026-06-02" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("Dentist at 10:00 AM"),
        },
      },
    });
  });

  it("cancels a matching appointment through the shared origin path", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (
          url ===
          "https://calsync.neonbutterfly.net/api/appointments?date_from=2026-06-02&date_to=2026-06-02"
        ) {
          return new Response(
            JSON.stringify({
              items: [
                {
                  appointment_id: "appt-123",
                  title: "Dentist",
                  status: "active",
                  date: "2026-06-02",
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
        }

        if (
          url ===
          "https://calsync.neonbutterfly.net/api/appointments/appt-123/cancel"
        ) {
          const headers = init?.headers as Headers;
          expect(headers.get("X-CalSync-Channel")).toBe("alexa");
          return new Response(
            JSON.stringify({
              appointment_id: "appt-123",
              status: "cancelled",
              provider_event_id: "provider-123",
              message: "Appointment cancelled.",
            }),
            {
              status: 200,
              headers: {
                "content-type": "application/json; charset=utf-8",
              },
            },
          );
        }

        throw new Error(`Unexpected fetch ${url}`);
      });

    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "IntentRequest",
        timestamp: new Date().toISOString(),
        intent: {
          name: "CancelAppointmentIntent",
          slots: {
            title: { value: "Dentist" },
            date: { value: "2026-06-02" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("I cancelled Dentist"),
        },
      },
    });
  });

  it("reschedules a matching appointment through list, detail, and patch flows", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        const url = String(input);
        if (
          url ===
          "https://calsync.neonbutterfly.net/api/appointments?date_from=2026-06-02&date_to=2026-06-02"
        ) {
          return new Response(
            JSON.stringify({
              items: [
                {
                  appointment_id: "appt-123",
                  title: "Dentist",
                  status: "active",
                  date: "2026-06-02",
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
        }

        if (url === "https://calsync.neonbutterfly.net/api/appointments/appt-123") {
          if (init?.method === "GET") {
            return new Response(
              JSON.stringify({
                appointment_id: "appt-123",
                title: "Dentist",
                status: "active",
                date: "2026-06-02",
                start_time: "10:00",
                end_time: "11:00",
                timezone: "America/Anchorage",
              }),
              {
                status: 200,
                headers: {
                  "content-type": "application/json; charset=utf-8",
                },
              },
            );
          }

          const headers = init?.headers as Headers;
          expect(headers.get("X-CalSync-Channel")).toBe("alexa");
          const body = JSON.parse(String(init?.body)) as Record<string, string>;
          expect(body.date).toBe("2026-06-03");
          expect(body.start_time).toBe("13:00");
          expect(body.end_time).toBe("14:00");
          return new Response(
            JSON.stringify({
              appointment_id: "appt-123",
              status: "active",
              provider_event_id: "provider-123",
              message: "Appointment updated.",
            }),
            {
              status: 200,
              headers: {
                "content-type": "application/json; charset=utf-8",
              },
            },
          );
        }

        throw new Error(`Unexpected fetch ${url}`);
      });

    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "IntentRequest",
        timestamp: new Date().toISOString(),
        intent: {
          name: "RescheduleAppointmentIntent",
          slots: {
            title: { value: "Dentist" },
            date: { value: "2026-06-02" },
            new_date: { value: "2026-06-03" },
            new_start_time: { value: "13:00" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("I moved Dentist to Wednesday, June 3, 2026 at 1:00 PM"),
        },
      },
    });
  });

  it("returns 400 when Alexa request verification fails", async () => {
    alexaVerifierMock.mockRejectedValueOnce(new Error("invalid signature"));
    const request = buildAlexaRequest({
      session: {
        application: {
          applicationId: "amzn1.ask.skill.test",
        },
      },
      request: {
        type: "LaunchRequest",
        timestamp: new Date().toISOString(),
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      ok: false,
      message: "Alexa request verification failed: invalid signature",
    });
  });
});
