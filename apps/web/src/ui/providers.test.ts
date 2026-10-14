import { describe, expect, it } from "vitest";

import { credentialFor, providerLabel, settingsWrite } from "./provider-utils";

describe("provider settings helpers", () => {
  it("labels known providers and falls back for unknown values", () => {
    expect(providerLabel("OPENROUTER")).toBe("OpenRouter");
    expect(providerLabel("XAI")).toBe("xAI");
    expect(providerLabel("GEMINI")).toBe("Google Gemini");
    expect(providerLabel("OTHER")).toBe("OTHER");
  });

  it("finds only enabled credentials for a provider", () => {
    const credentials = [
      {
        id: "a",
        provider: "OPENROUTER",
        last4: "1234",
        enabled: false,
        status: "REVOKED",
        revision: 2,
        allow_interactive: true,
        allow_background: false,
      },
      {
        id: "b",
        provider: "OPENROUTER",
        last4: "5678",
        enabled: true,
        status: "READY",
        revision: 3,
        allow_interactive: true,
        allow_background: false,
      },
      {
        id: "c",
        provider: "XAI",
        last4: "9999",
        enabled: true,
        status: "READY",
        revision: 1,
        allow_interactive: true,
        allow_background: true,
      },
    ];
    expect(credentialFor(credentials, "OPENROUTER")?.id).toBe("b");
    expect(credentialFor(credentials, "GEMINI")).toBeUndefined();
  });

  it("sends the current revision as both expected_revision and If-Match", () => {
    const { body, headers } = settingsWrite({
      revision: 7,
      interactive_consent: true,
      fallback_consent: false,
      background_consent: true,
      routes: [
        {
          credential_id: "cred-1",
          model_id: "deepseek/deepseek-chat",
          enabled: true,
          interactive_enabled: true,
          background_enabled: true,
        },
      ],
    });
    expect(body.expected_revision).toBe(7);
    expect(headers["If-Match"]).toBe('"7"');
    expect(body.routes).toHaveLength(1);
  });
});
