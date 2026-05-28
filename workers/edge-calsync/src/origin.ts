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
