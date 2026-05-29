import { validateChannelToken } from "./auth";
import { handleAlexaRequest, simulateAlexaRequest } from "./alexa";
import {
  allowedAlexaSkillIds,
  CHANNEL_FLAGS,
  isEnabled,
  isChannelEnabled,
  type ChannelName,
  type WorkerEnv,
} from "./env";
import { forwardToOrigin } from "./origin";
import { errorResponse, jsonResponse, normalizeOriginResponse } from "./responses";

export default {
  async fetch(
    request: Request,
    env: WorkerEnv,
    _ctx: ExecutionContext,
  ): Promise<Response> {
    const requestId = crypto.randomUUID();
    const url = new URL(request.url);

    if (url.pathname === "/status" && request.method === "GET") {
      return jsonResponse(200, {
        ok: true,
        message: "Worker readiness retrieved.",
        data: await buildPublicStatus(env),
        request_id: requestId,
      });
    }

    if (url.pathname === "/alexa" && request.method === "POST") {
      if (!isEnabled(env.ENABLE_ALEXA)) {
        return errorResponse(403, "This channel is disabled.", requestId);
      }
      return handleAlexaRequest(request, env, requestId);
    }

    const channel = await validateChannelToken(request, env);

    if (!channel) {
      return errorResponse(401, "Authentication required.", requestId);
    }
    if (!isChannelEnabled(env, channel)) {
      return errorResponse(403, "This channel is disabled.", requestId);
    }

    if (url.pathname === "/alexa/simulate" && request.method === "POST") {
      if (channel !== "chatgpt") {
        return errorResponse(
          403,
          "Only the ChatGPT channel may run Alexa simulations.",
          requestId,
        );
      }

      const simulation = (await request.json()) as Record<string, unknown>;
      const alexaResponse = await simulateAlexaRequest(
        {
          request_type:
            typeof simulation.request_type === "string"
              ? simulation.request_type
              : undefined,
          intent_name:
            typeof simulation.intent_name === "string"
              ? simulation.intent_name
              : undefined,
          timestamp:
            typeof simulation.timestamp === "string"
              ? simulation.timestamp
              : undefined,
          slots:
            simulation.slots && typeof simulation.slots === "object"
              ? Object.fromEntries(
                  Object.entries(simulation.slots as Record<string, unknown>)
                    .filter(([, value]) => typeof value === "string")
                    .map(([key, value]) => [key, value as string]),
                )
              : undefined,
        },
        env,
        requestId,
      );
      const body = (await alexaResponse.json()) as {
        response?: {
          outputSpeech?: { text?: string };
          card?: { type?: string };
          shouldEndSession?: boolean;
        };
      };

      return jsonResponse(alexaResponse.status, {
        ok: alexaResponse.ok,
        message: "Alexa simulation completed.",
        data: {
          speech: body.response?.outputSpeech?.text ?? null,
          card_type: body.response?.card?.type ?? null,
          should_end_session: body.response?.shouldEndSession ?? null,
          raw_response: body,
        },
        request_id: requestId,
      });
    }

    return routeRequest(request, env, channel, requestId);
  },
};

async function routeRequest(
  request: Request,
  env: WorkerEnv,
  channel: ChannelName,
  requestId: string,
): Promise<Response> {
  const url = new URL(request.url);
  const pathname = url.pathname;

  if (pathname === "/v1/appointments" && request.method === "GET") {
    if (!url.searchParams.get("date_from") || !url.searchParams.get("date_to")) {
      return errorResponse(400, "date_from and date_to are required.", requestId);
    }
    return proxyRequest(
      request,
      env,
      channel,
      requestId,
      `/api/appointments?${url.searchParams.toString()}`,
      "Appointments retrieved.",
    );
  }

  if (pathname === "/v1/appointments" && request.method === "POST") {
    return proxyRequest(
      request,
      env,
      channel,
      requestId,
      "/api/appointments",
      "Appointment created.",
    );
  }

  const updateMatch = pathname.match(/^\/v1\/appointments\/([^/]+)$/);
  if (updateMatch && request.method === "GET") {
    return proxyRequest(
      request,
      env,
      channel,
      requestId,
      `/api/appointments/${updateMatch[1]}`,
      "Appointment retrieved.",
    );
  }

  if (updateMatch && request.method === "PATCH") {
    return proxyRequest(
      request,
      env,
      channel,
      requestId,
      `/api/appointments/${updateMatch[1]}`,
      "Appointment updated.",
    );
  }

  const cancelMatch = pathname.match(/^\/v1\/appointments\/([^/]+)\/cancel$/);
  if (cancelMatch && request.method === "POST") {
    return proxyRequest(
      request,
      env,
      channel,
      requestId,
      `/api/appointments/${cancelMatch[1]}/cancel`,
      "Appointment cancelled.",
    );
  }

  return errorResponse(404, "Route not found.", requestId);
}

async function proxyRequest(
  request: Request,
  env: WorkerEnv,
  channel: ChannelName,
  requestId: string,
  path: string,
  successMessage: string,
): Promise<Response> {
  try {
    const originResponse = await forwardToOrigin(
      env,
      request,
      path,
      channel,
      requestId,
    );
    return normalizeOriginResponse(originResponse, {
      requestId,
      successMessage,
    });
  } catch {
    return errorResponse(502, "Origin unavailable.", requestId);
  }
}

async function buildPublicStatus(env: WorkerEnv): Promise<Record<string, unknown>> {
  const channelStatuses = await Promise.all(
    Object.keys(CHANNEL_FLAGS).map(async (channel) => {
      const channelName = channel as ChannelName;
      const storedHash = await env.TOKEN_HASHES.get(channelName);
      return [
        channelName,
        {
          enabled: isChannelEnabled(env, channelName),
          token_hash_present: Boolean(storedHash),
        },
      ] as const;
    }),
  );

  return {
    origin_base_url_configured: Boolean(env.ORIGIN_BASE_URL),
    admin_routes_enabled: isEnabled(env.ENABLE_ADMIN_ROUTES),
    channels: Object.fromEntries(channelStatuses),
    alexa: {
      enabled: isEnabled(env.ENABLE_ALEXA),
      skill_ids_configured: allowedAlexaSkillIds(env).length > 0,
      allowed_skill_id_count: allowedAlexaSkillIds(env).length,
      default_timezone: env.ALEXA_DEFAULT_TIMEZONE || "America/Anchorage",
    },
  };
}
