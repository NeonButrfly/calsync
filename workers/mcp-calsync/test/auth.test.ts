import { afterEach, describe, expect, it, vi } from "vitest";

async function postMcp(
  worker: { default: ExportedHandler },
  body: unknown,
  headers: Record<string, string> = {},
) {
  const request = new Request("https://mcp-calsync.neonbutterfly.net/mcp", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      accept: "application/json, text/event-stream",
      ...headers,
    },
    body: JSON.stringify(body),
  });

  return worker.default.fetch(
    request,
    {
      MCP_AUTH_TOKEN: "top-secret",
      EDGE_INTERNAL_TOKEN: "edge-secret",
      EDGE_BASE_URL: "https://edge-calsync.neonbutterfly.net",
    } as never,
    {} as ExecutionContext,
  );
}

async function initializeSession(worker: { default: ExportedHandler }) {
  const initializeResponse = await postMcp(
    worker,
    {
      jsonrpc: "2.0",
      id: "1",
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: {
          name: "vitest",
          version: "0.1.0",
        },
      },
    },
    {
      authorization: "Bearer top-secret",
    },
  );

  expect(initializeResponse.status).toBe(200);

  const initializedResponse = await postMcp(
    worker,
    {
      jsonrpc: "2.0",
      method: "notifications/initialized",
    },
    {
      authorization: "Bearer top-secret",
    },
  );

  expect(initializedResponse.status).toBe(202);
}

async function callTool(
  worker: { default: ExportedHandler },
  name: string,
  args: Record<string, unknown>,
) {
  return postMcp(
    worker,
    {
      jsonrpc: "2.0",
      id: crypto.randomUUID(),
      method: "tools/call",
      params: {
        name,
        arguments: args,
      },
    },
    {
      authorization: "Bearer top-secret",
    },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("mcp auth", () => {
  it("rejects unauthenticated mcp requests", async () => {
    const worker = await import("../src/index");
    const request = new Request("https://mcp-calsync.neonbutterfly.net/mcp", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "1",
        method: "initialize",
        params: {
          protocolVersion: "2025-03-26",
          capabilities: {},
          clientInfo: {
            name: "vitest",
            version: "0.1.0",
          },
        },
      }),
    });

    const response = await worker.default.fetch(request, {
      MCP_AUTH_TOKEN: "top-secret",
      EDGE_INTERNAL_TOKEN: "edge-secret",
      EDGE_BASE_URL: "https://edge-calsync.neonbutterfly.net",
    } as never, {} as ExecutionContext);

    expect(response.status).toBe(401);
  });

  it("lets an authenticated client initialize and list appointment tools", async () => {
    const worker = await import("../src/index");

    await initializeSession(worker);

    const toolsResponse = await postMcp(
      worker,
      {
        jsonrpc: "2.0",
        id: "2",
        method: "tools/list",
        params: {},
      },
      {
        authorization: "Bearer top-secret",
      },
    );

    expect(toolsResponse.status).toBe(200);
    const toolsPayload = (await toolsResponse.json()) as {
      result: { tools: Array<{ name: string }> };
    };
    expect(toolsPayload.result.tools.map((tool) => tool.name)).toEqual([
      "list_appointments",
      "create_appointment",
      "update_appointment",
      "cancel_appointment",
    ]);
  });

  it("forwards list_appointments through the edge worker with the internal credential", async () => {
    const worker = await import("../src/index");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          message: "Appointments retrieved.",
          data: {
            items: [
              {
                appointment_id: "appt-123",
                title: "Dentist",
                status: "confirmed",
                date: "2026-06-01",
                start_time: "10:00",
                end_time: "11:00",
                timezone: "America/Anchorage",
                all_day: false,
                location: "Clinic",
                notes: null,
                attendees_text: null,
              },
            ],
            count: 1,
          },
          request_id: "req-123",
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        },
      ),
    );

    await initializeSession(worker);

    const toolResponse = await callTool(worker, "list_appointments", {
      date_from: "2026-06-01",
      date_to: "2026-06-02",
    });

    expect(toolResponse.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "https://edge-calsync.neonbutterfly.net/v1/appointments?date_from=2026-06-01&date_to=2026-06-02",
    );
    expect(init.method).toBe("GET");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer edge-secret");

    const toolPayload = (await toolResponse.json()) as {
      result: { content: Array<{ text: string }> };
    };
    expect(toolPayload.result.content[0].text).toContain("Dentist");
  });

  it("forwards create_appointment through the edge worker with the internal credential", async () => {
    const worker = await import("../src/index");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            message: "Appointment created.",
            data: {
              appointment_id: "appt-created",
              provider_event_id: "provider-123",
              status: "confirmed",
              message: "Appointment created.",
            },
            request_id: "req-created",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            data: {
              appointment_id: "appt-created",
              provider_event_id: "provider-123",
              status: "confirmed",
              title: "Health Coach",
              date: "2026-06-04",
              start_time: "09:00",
              end_time: "09:30",
              timezone: "America/Anchorage",
              all_day: false,
              location: "Clinic",
              notes: "Bring papers",
              attendees_text: null,
            },
            request_id: "req-detail",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      );

    await initializeSession(worker);

    const toolResponse = await callTool(worker, "create_appointment", {
      title: "Health Coach",
      date: "2026-06-04",
      start_time: "09:00",
      end_time: "09:30",
      timezone: "America/Anchorage",
      location: "Clinic",
      notes: "Bring papers",
    });

    expect(toolResponse.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://edge-calsync.neonbutterfly.net/v1/appointments");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer edge-secret");
    expect(init.body).toBe(
      JSON.stringify({
        title: "Health Coach",
        date: "2026-06-04",
        start_time: "09:00",
        end_time: "09:30",
        timezone: "America/Anchorage",
        location: "Clinic",
        notes: "Bring papers",
      }),
    );
    const [detailUrl, detailInit] = fetchSpy.mock.calls[1] as [string, RequestInit];
    expect(detailUrl).toBe(
      "https://edge-calsync.neonbutterfly.net/v1/appointments/appt-created",
    );
    expect(detailInit.method).toBe("GET");

    const toolPayload = (await toolResponse.json()) as {
      result: {
        content: Array<{ text: string }>;
        structuredContent: { appointment: { title: string } };
      };
    };
    expect(toolPayload.result.content[0].text).toContain("Health Coach");
    expect(toolPayload.result.structuredContent.appointment.title).toBe("Health Coach");
  });

  it("forwards update_appointment through the edge worker with the internal credential", async () => {
    const worker = await import("../src/index");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            message: "Appointment updated.",
            data: {
              appointment_id: "appt-123",
              provider_event_id: "provider-123",
              status: "confirmed",
              message: "Appointment updated.",
            },
            request_id: "req-updated",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: true,
            data: {
              appointment_id: "appt-123",
              provider_event_id: "provider-123",
              status: "confirmed",
              title: "Health Coach Updated",
              date: "2026-06-04",
              start_time: "10:00",
              end_time: "10:30",
              timezone: "America/Anchorage",
              all_day: false,
              location: "New clinic",
              notes: null,
              attendees_text: null,
            },
            request_id: "req-detail",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json; charset=utf-8",
            },
          },
        ),
      );

    await initializeSession(worker);

    const toolResponse = await callTool(worker, "update_appointment", {
      appointment_id: "appt-123",
      title: "Health Coach Updated",
      start_time: "10:00",
      end_time: "10:30",
      location: "New clinic",
    });

    expect(toolResponse.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("https://edge-calsync.neonbutterfly.net/v1/appointments/appt-123");
    expect(init.method).toBe("PATCH");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer edge-secret");
    expect(init.body).toBe(
      JSON.stringify({
        title: "Health Coach Updated",
        start_time: "10:00",
        end_time: "10:30",
        location: "New clinic",
      }),
    );
    const [detailUrl, detailInit] = fetchSpy.mock.calls[1] as [string, RequestInit];
    expect(detailUrl).toBe("https://edge-calsync.neonbutterfly.net/v1/appointments/appt-123");
    expect(detailInit.method).toBe("GET");

    const toolPayload = (await toolResponse.json()) as {
      result: {
        content: Array<{ text: string }>;
        structuredContent: { appointment: { title: string } };
      };
    };
    expect(toolPayload.result.content[0].text).toContain("Health Coach Updated");
    expect(toolPayload.result.structuredContent.appointment.title).toBe(
      "Health Coach Updated",
    );
  });

  it("forwards cancel_appointment through the edge worker with the internal credential", async () => {
    const worker = await import("../src/index");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ok: true,
          message: "Appointment cancelled.",
          data: {
            appointment_id: "appt-123",
            provider_event_id: "provider-123",
            status: "cancelled",
          },
          request_id: "req-cancelled",
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        },
      ),
    );

    await initializeSession(worker);

    const toolResponse = await callTool(worker, "cancel_appointment", {
      appointment_id: "appt-123",
    });

    expect(toolResponse.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "https://edge-calsync.neonbutterfly.net/v1/appointments/appt-123/cancel",
    );
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("authorization")).toBe("Bearer edge-secret");
    expect(init.body).toBeUndefined();

    const toolPayload = (await toolResponse.json()) as {
      result: { content: Array<{ text: string }> };
    };
    expect(toolPayload.result.content[0].text).toContain("Cancelled appointment");
  });
});
