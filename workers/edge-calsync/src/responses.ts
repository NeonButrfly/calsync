export interface EdgeResponseEnvelope<T = unknown> {
  ok: boolean;
  message: string;
  data: T | null;
  request_id: string;
}

export function jsonResponse<T>(
  status: number,
  payload: EdgeResponseEnvelope<T>,
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
    },
  });
}

export function errorResponse(
  status: number,
  message: string,
  requestId: string,
): Response {
  return jsonResponse(status, {
    ok: false,
    message,
    data: null,
    request_id: requestId,
  });
}

export async function normalizeOriginResponse(
  response: Response,
  options: {
    requestId: string;
    successMessage: string;
  },
): Promise<Response> {
  const { requestId, successMessage } = options;
  const contentType = response.headers.get("content-type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (response.ok) {
    return jsonResponse(response.status, {
      ok: true,
      message: extractMessage(parsedBody) ?? successMessage,
      data: parsedBody,
      request_id: requestId,
    });
  }

  return errorResponse(
    response.status,
    extractMessage(parsedBody) ?? "Origin request failed.",
    requestId,
  );
}

function extractMessage(body: unknown): string | null {
  if (body && typeof body === "object") {
    const candidate =
      "message" in body
        ? body.message
        : "detail" in body
          ? body.detail
          : null;
    return typeof candidate === "string" ? candidate : null;
  }

  return typeof body === "string" && body ? body : null;
}
