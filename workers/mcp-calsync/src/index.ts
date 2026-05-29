import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { z } from "zod";

export interface WorkerEnv {
  MCP_AUTH_TOKEN: string;
  EDGE_INTERNAL_TOKEN: string;
  EDGE_BASE_URL: string;
}

function isAuthorized(request: Request, env: WorkerEnv): boolean {
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer ")) {
    return false;
  }
  return authorization.slice("Bearer ".length) === env.MCP_AUTH_TOKEN;
}

async function callEdge(
  env: WorkerEnv,
  path: string,
  options: {
    method: string;
    body?: unknown;
  },
): Promise<Response> {
  const headers = new Headers({
    accept: "application/json",
    authorization: `Bearer ${env.EDGE_INTERNAL_TOKEN}`,
  });

  let body: string | undefined;
  if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers.set("content-type", "application/json; charset=utf-8");
  }

  return fetch(new URL(path, env.EDGE_BASE_URL).toString(), {
    method: options.method,
    headers,
    body,
  });
}

async function parseEdgeJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as T;
  if (!response.ok) {
    throw new Error("Upstream edge request failed.");
  }
  return payload;
}

function appointmentSummary(item: {
  title: string;
  date: string;
  start_time: string;
  timezone: string;
}): string {
  return `${item.title} on ${item.date} at ${item.start_time} ${item.timezone}`;
}

type AppointmentDetail = {
  appointment_id: string;
  provider_event_id: string;
  status: string;
  title: string;
  date: string;
  start_time: string;
  end_time: string;
  timezone: string;
  all_day: boolean;
  location: string | null;
  notes: string | null;
  attendees_text: string | null;
};

function hasAppointmentSummaryFields(
  item: Partial<AppointmentDetail>,
): item is AppointmentDetail {
  return Boolean(item.title && item.date && item.start_time && item.timezone);
}

async function fetchAppointmentDetail(
  env: WorkerEnv,
  appointmentId: string,
): Promise<AppointmentDetail> {
  const edgeResponse = await callEdge(
    env,
    `/v1/appointments/${encodeURIComponent(appointmentId)}`,
    { method: "GET" },
  );
  const payload = await parseEdgeJson<{
    data: AppointmentDetail;
  }>(edgeResponse);
  return payload.data;
}

function createServer(env: WorkerEnv): McpServer {
  const server = new McpServer({
    name: "calsync-mcp",
    version: "1.0.0",
  });

  server.registerTool(
    "list_appointments",
    {
      title: "List appointments",
      description:
        "List appointments in a required date window before editing or cancelling anything.",
      inputSchema: {
        date_from: z.string(),
        date_to: z.string(),
      },
    },
    async ({ date_from, date_to }) => {
      const edgeResponse = await callEdge(
        env,
        `/v1/appointments?date_from=${encodeURIComponent(date_from)}&date_to=${encodeURIComponent(date_to)}`,
        { method: "GET" },
      );
      const payload = await parseEdgeJson<{
        data: {
          items: Array<{
            appointment_id: string;
            title: string;
            date: string;
            start_time: string;
            end_time: string;
            timezone: string;
            status: string;
            all_day: boolean;
            location: string | null;
            notes: string | null;
            attendees_text: string | null;
          }>;
          count: number;
        };
      }>(edgeResponse);
      const items = payload.data.items;
      const summary = items.length
        ? items.map((item) => appointmentSummary(item)).join("\n")
        : "No appointments found in that window.";
      return {
        content: [{ type: "text", text: summary }],
        structuredContent: payload.data,
      };
    },
  );

  server.registerTool(
    "create_appointment",
    {
      title: "Create appointment",
      description: "Create a new calendar appointment in the shared schedule.",
      inputSchema: {
        title: z.string(),
        date: z.string(),
        start_time: z.string(),
        end_time: z.string(),
        timezone: z.string(),
        all_day: z.boolean().optional(),
        location: z.string().optional(),
        notes: z.string().optional(),
        attendees_text: z.string().optional(),
      },
    },
    async (args) => {
      const edgeResponse = await callEdge(env, "/v1/appointments", {
        method: "POST",
        body: args,
      });
      const payload = await parseEdgeJson<{
        data: Partial<AppointmentDetail> & {
          appointment_id: string;
          provider_event_id: string;
          status: string;
          message?: string;
        };
      }>(edgeResponse);
      const detail = hasAppointmentSummaryFields(payload.data)
        ? payload.data
        : await fetchAppointmentDetail(env, payload.data.appointment_id);
      return {
        content: [{ type: "text", text: `Created ${appointmentSummary(detail)}.` }],
        structuredContent: {
          ...payload.data,
          appointment: detail,
        },
      };
    },
  );

  server.registerTool(
    "update_appointment",
    {
      title: "Update appointment",
      description: "Update a known appointment by id.",
      inputSchema: {
        appointment_id: z.string(),
        title: z.string().optional(),
        date: z.string().optional(),
        start_time: z.string().optional(),
        end_time: z.string().optional(),
        timezone: z.string().optional(),
        all_day: z.boolean().optional(),
        location: z.string().optional(),
        notes: z.string().optional(),
        attendees_text: z.string().optional(),
      },
    },
    async ({ appointment_id, ...updates }) => {
      const edgeResponse = await callEdge(
        env,
        `/v1/appointments/${encodeURIComponent(appointment_id)}`,
        {
          method: "PATCH",
          body: updates,
        },
      );
      const payload = await parseEdgeJson<{
        data: Partial<AppointmentDetail> & {
          appointment_id: string;
          provider_event_id: string;
          status: string;
          message?: string;
        };
      }>(edgeResponse);
      const detail = hasAppointmentSummaryFields(payload.data)
        ? payload.data
        : await fetchAppointmentDetail(env, payload.data.appointment_id);
      return {
        content: [{ type: "text", text: `Updated ${appointmentSummary(detail)}.` }],
        structuredContent: {
          ...payload.data,
          appointment: detail,
        },
      };
    },
  );

  server.registerTool(
    "cancel_appointment",
    {
      title: "Cancel appointment",
      description: "Cancel a known appointment by id.",
      inputSchema: {
        appointment_id: z.string(),
      },
    },
    async ({ appointment_id }) => {
      const edgeResponse = await callEdge(
        env,
        `/v1/appointments/${encodeURIComponent(appointment_id)}/cancel`,
        {
          method: "POST",
        },
      );
      const payload = await parseEdgeJson<{
        data: {
          appointment_id: string;
          provider_event_id: string;
          status: string;
        };
      }>(edgeResponse);
      return {
        content: [
          {
            type: "text",
            text: `Cancelled appointment ${payload.data.appointment_id}.`,
          },
        ],
        structuredContent: payload.data,
      };
    },
  );

  return server;
}

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname !== "/mcp") {
      return new Response("Not found", { status: 404 });
    }

    if (!isAuthorized(request, env)) {
      return new Response(
        JSON.stringify({
          jsonrpc: "2.0",
          error: {
            code: -32001,
            message: "Authentication required.",
          },
          id: null,
        }),
        {
          status: 401,
          headers: {
            "content-type": "application/json; charset=utf-8",
          },
        },
      );
    }

    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    const server = createServer(env);

    await server.connect(transport);
    return transport.handleRequest(request);
  },
} satisfies ExportedHandler<WorkerEnv>;
