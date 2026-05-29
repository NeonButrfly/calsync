import type { ChannelName, WorkerEnv } from "./env";

export async function forwardToOrigin(
  env: WorkerEnv,
  request: Request,
  path: string,
  channel: ChannelName,
  requestId: string,
): Promise<Response> {
  const url = new URL(path, env.ORIGIN_BASE_URL);
  const headers = new Headers();
  const contentType = request.headers.get("content-type");

  if (contentType) {
    headers.set("content-type", contentType);
  }
  headers.set("accept", "application/json");
  headers.set("X-CalSync-Channel", channel);
  headers.set("X-CalSync-Request-Id", requestId);

  return fetch(url.toString(), {
    method: request.method,
    headers,
    body: request.body,
  });
}

export async function callOriginJson(
  env: WorkerEnv,
  options: {
    method: string;
    path: string;
    channel: ChannelName;
    requestId: string;
    body?: unknown;
  },
): Promise<Response> {
  const { method, path, channel, requestId, body } = options;
  const url = new URL(path, env.ORIGIN_BASE_URL);
  const headers = new Headers({
    accept: "application/json",
    "X-CalSync-Channel": channel,
    "X-CalSync-Request-Id": requestId,
  });

  let serializedBody: string | undefined;
  if (body !== undefined) {
    serializedBody = JSON.stringify(body);
    headers.set("content-type", "application/json; charset=utf-8");
  }

  return fetch(url.toString(), {
    method,
    headers,
    body: serializedBody,
  });
}
