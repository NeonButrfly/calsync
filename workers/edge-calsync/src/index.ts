import { validateChannelToken } from "./auth";
import { handleAlexaRequest } from "./alexa";
import {
  isEnabled,
  isChannelEnabled,
  type ChannelName,
  type WorkerEnv,
} from "./env";
import { forwardToOrigin } from "./origin";
import { errorResponse, normalizeOriginResponse } from "./responses";

export default {
  async fetch(
    request: Request,
    env: WorkerEnv,
    _ctx: ExecutionContext,
  ): Promise<Response> {
    const requestId = crypto.randomUUID();
    const url = new URL(request.url);

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
