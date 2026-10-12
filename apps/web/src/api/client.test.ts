import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";

describe("generated API client", () => {
  it("uses the generated meta response and preserves contract headers", async () => {
    const fetchImplementation = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            api_version: "v1",
            contract_version: 1,
            minimum_compatible_client_version: "0.1.0",
          }),
          { headers: { "content-type": "application/json" } },
        ),
    );
    const client = createApiClient(
      "http://127.0.0.1:18000",
      fetchImplementation,
    );

    const result = await client.GET("/api/v1/meta", {
      headers: {
        "X-Copilot-Contract-Version": "1",
        "X-Copilot-Client-Version": "0.1.0",
      },
    });

    expect(result.data?.contract_version).toBe(1);
    const request = fetchImplementation.mock.calls[0]?.[0];
    expect(new Request(request).headers.get("X-Copilot-Contract-Version")).toBe(
      "1",
    );
  });

  it("types the standard error payload returned for incompatible clients", async () => {
    const fetchImplementation = vi.fn<typeof fetch>(
      async () =>
        new Response(
          JSON.stringify({
            error: {
              code: "incompatible_contract_version",
              message: "This client contract version is not supported.",
              request_id: "89e1ac73-32c1-4446-b68b-6516da6ef926",
              field_errors: [],
            },
          }),
          { status: 426, headers: { "content-type": "application/json" } },
        ),
    );
    const client = createApiClient(
      "http://127.0.0.1:18000",
      fetchImplementation,
    );

    const result = await client.GET("/api/v1/meta");

    expect(result.error?.error.code).toBe("incompatible_contract_version");
    expect(result.response.status).toBe(426);
  });
});
