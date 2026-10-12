import createClient from "openapi-fetch";

import type { paths } from "./generated";

/** Create the web API client against an explicitly configured API origin. */
export function createApiClient(
  baseUrl: string,
  fetchImplementation: typeof fetch = fetch,
) {
  return createClient<paths>({ baseUrl, fetch: fetchImplementation });
}
