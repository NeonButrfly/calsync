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

function buildAccountLinkingValidationResponse(
  options?: {
    configured?: boolean;
    linked?: boolean;
  },
): Response {
  return new Response(
    JSON.stringify({
      data: {
        account_linking_configured: options?.configured ?? false,
        linked: options?.linked ?? false,
      },
    }),
    {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}

function buildReadinessResponse(
  options?: {
    anyCalendarReady?: boolean;
    recoveryMode?: boolean;
  },
): Response {
  return new Response(
    JSON.stringify({
      origin: {
        any_calendar_ready: options?.anyCalendarReady ?? true,
        recovery_mode: options?.recoveryMode ?? false,
      },
    }),
    {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}

describe("alexa worker adapter", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    alexaVerifierMock.mockClear();
  });

  it("returns a welcome response for launch requests", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate") {
        return buildAccountLinkingValidationResponse();
      }
      if (url === "https://calsync.neonbutterfly.net/api/readiness") {
        return buildReadinessResponse();
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
        type: "LaunchRequest",
        timestamp: new Date().toISOString(),
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(2);
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

  it("returns Apple reconnect guidance for launch requests in recovery mode", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url === "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate") {
          return buildAccountLinkingValidationResponse();
        }
        if (url === "https://calsync.neonbutterfly.net/api/readiness") {
          return buildReadinessResponse({
            anyCalendarReady: false,
            recoveryMode: true,
          });
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
        type: "LaunchRequest",
        timestamp: new Date().toISOString(),
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining(
            "Open Apple setup, confirm the loaded recovered Apple calendar, and save a fresh app-specific password",
          ),
        },
      },
    });
  });

  it("returns a link account card when the origin says account linking is required", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      expect(String(input)).toBe(
        "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate",
      );
      return buildAccountLinkingValidationResponse({
        configured: true,
        linked: false,
      });
    });
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
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("link your CalSync account"),
        },
        card: {
          type: "LinkAccount",
        },
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

  it("returns Apple reconnect guidance for help intent in recovery mode", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url === "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate") {
          return buildAccountLinkingValidationResponse();
        }
        if (url === "https://calsync.neonbutterfly.net/api/readiness") {
          return buildReadinessResponse({
            anyCalendarReady: false,
            recoveryMode: true,
          });
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
          name: "AMAZON.HelpIntent",
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining(
            "Open Apple setup, confirm the loaded recovered Apple calendar, and save a fresh app-specific password",
          ),
        },
      },
    });
  });

  it("returns Apple reconnect guidance for fallback intent in recovery mode", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url === "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate") {
          return buildAccountLinkingValidationResponse();
        }
        if (url === "https://calsync.neonbutterfly.net/api/readiness") {
          return buildReadinessResponse({
            anyCalendarReady: false,
            recoveryMode: true,
          });
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
          name: "AMAZON.FallbackIntent",
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining(
            "Open Apple setup, confirm the loaded recovered Apple calendar, and save a fresh app-specific password",
          ),
        },
      },
    });
  });

  it("creates an appointment through the shared origin path", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

        expect(String(input)).toBe("https://calsync.neonbutterfly.net/api/appointments");
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");
        const bodyText = String(init?.body);
        const body = JSON.parse(bodyText) as Record<string, string>;
        expect(body.title).toBe("Dentist");
        expect(body.end_time).toBe("11:00");
        expect(body.target_calendar_name).toBe("School");

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
            calendar_name: { value: "School" },
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
          text: expect.stringContaining("I added Dentist to the School calendar"),
        },
      },
    });
  });

  it("normalizes Apple recovery errors for create intent", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

        return new Response(
          JSON.stringify({
            message: "Primary Apple/iCloud calendar is not configured.",
          }),
          {
            status: 400,
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

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining(
            "Apple reconnect still needs one more step.",
          ),
        },
      },
    });
  });

  it("lists appointments for a requested date", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

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
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("Dentist at 10:00 AM"),
        },
      },
    });
  });

  it("announces the next active appointment", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/appointments?date_from=2026-06-02&date_to=2026-07-02",
        );
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");

        return new Response(
          JSON.stringify({
            items: [
              {
                appointment_id: "appt-cancelled",
                title: "Old Dentist",
                status: "cancelled",
                date: "2026-06-02",
                start_time: "09:00",
                end_time: "10:00",
                timezone: "America/Anchorage",
              },
              {
                appointment_id: "appt-next",
                title: "Health Coach",
                status: "active",
                date: "2026-06-03",
                start_time: "13:00",
                end_time: "14:00",
                timezone: "America/Anchorage",
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
        timestamp: "2026-06-02T16:00:00Z",
        intent: {
          name: "NextAppointmentIntent",
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
          text: expect.stringContaining(
            "Your next appointment is Health Coach on Wednesday, June 3, 2026 at 1:00 PM",
          ),
        },
      },
    });
  });

  it("reports availability openings through the shared origin path", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/availability?date_from=2026-06-02&date_to=2026-06-02&duration_minutes=60&max_results=3",
        );
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");

        return new Response(
          JSON.stringify({
            items: [
              {
                date: "2026-06-02",
                start_time: "10:00",
                end_time: "11:00",
                timezone: "America/Anchorage",
              },
              {
                date: "2026-06-02",
                start_time: "11:00",
                end_time: "12:00",
                timezone: "America/Anchorage",
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
          name: "FindAvailabilityIntent",
          slots: {
            date: { value: "2026-06-02" },
            duration_minutes: { value: "60" },
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
          text: expect.stringContaining(
            "I found openings on Tuesday, June 2, 2026 at 10:00 AM and 11:00 AM",
          ),
        },
      },
    });
  });

  it("normalizes Apple recovery errors for availability intent", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (
          String(input) ===
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }

        return new Response(
          JSON.stringify({
            message: "Primary Apple/iCloud calendar is not configured.",
          }),
          {
            status: 400,
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
          name: "FindAvailabilityIntent",
          slots: {
            date: { value: "2026-06-02" },
            duration_minutes: { value: "60" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining(
            "Apple reconnect still needs one more step.",
          ),
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
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }
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
    expect(fetchSpy).toHaveBeenCalledTimes(3);
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
          "https://calsync.neonbutterfly.net/api/alexa/account-linking/validate"
        ) {
          return buildAccountLinkingValidationResponse();
        }
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
          expect(body.target_calendar_name).toBe("School");
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
            new_calendar_name: { value: "School" },
          },
        },
      },
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, alexaEnv(), ctx);

    await waitOnExecutionContext(ctx);

    expect(alexaVerifierMock).toHaveBeenCalledOnce();
    expect(fetchSpy).toHaveBeenCalledTimes(4);
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      response: {
        outputSpeech: {
          text: expect.stringContaining("I moved Dentist to the School calendar on Wednesday, June 3, 2026 at 1:00 PM"),
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

  it("simulates an Alexa intent through the real handler when an authenticated channel calls the simulator route", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, init) => {
        expect(String(input)).toBe(
          "https://calsync.neonbutterfly.net/api/appointments",
        );
        const headers = init?.headers as Headers;
        expect(headers.get("X-CalSync-Channel")).toBe("alexa");
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

    const request = new Request(
      "https://edge-calsync.neonbutterfly.net/alexa/simulate",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: "Bearer chatgpt-token",
        },
        body: JSON.stringify({
          request_type: "IntentRequest",
          intent_name: "CreateAppointmentIntent",
          slots: {
            title: "Dentist",
            date: "2026-06-01",
            start_time: "10:00",
            end_time: "11:00",
          },
        }),
      },
    );
    const ctx = createExecutionContext();
    const response = await worker.fetch(
      request,
      {
        ...alexaEnv(),
        ENABLE_CHATGPT: "true",
        TOKEN_HASHES: {
          get: vi.fn(async (key: string) =>
            key === "chatgpt"
              ? "8aa22830d27792eaec99566fe269943c50cb59c094f40a4c2bb5c8b05522802e"
              : null,
          ),
        } as unknown as KVNamespace,
      },
      ctx,
    );

    await waitOnExecutionContext(ctx);

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      ok: true,
      data: {
        speech: expect.stringContaining("I added Dentist"),
        raw_response: {
          response: {
            outputSpeech: {
              text: expect.stringContaining("I added Dentist"),
            },
          },
        },
      },
    });
  });
});
