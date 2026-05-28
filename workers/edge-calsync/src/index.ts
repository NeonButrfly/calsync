import type { WorkerEnv } from "./env";

export default {
  async fetch(
    _request: Request,
    _env: WorkerEnv,
    _ctx: ExecutionContext,
  ): Promise<Response> {
    return new Response("not implemented", { status: 501 });
  },
};
