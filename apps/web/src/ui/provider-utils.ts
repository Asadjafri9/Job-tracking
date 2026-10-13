import type { components } from "../api/generated";

export type Credential = components["schemas"]["CredentialSummary"];
export type Route = components["schemas"]["RouteWrite"];
export type ProviderSettings =
  components["schemas"]["ProviderSettingsResponse"];

export const PROVIDERS = [
  {
    id: "OPENROUTER",
    label: "OpenRouter",
    modelHint: "e.g. deepseek/deepseek-chat",
  },
  { id: "XAI", label: "xAI", modelHint: "e.g. grok-4" },
  { id: "GEMINI", label: "Google Gemini", modelHint: "e.g. gemini-2.5-flash" },
] as const;

export type ProviderId = (typeof PROVIDERS)[number]["id"];

export function providerLabel(provider: string): string {
  return PROVIDERS.find((entry) => entry.id === provider)?.label ?? provider;
}

export function credentialFor(
  credentials: Credential[],
  provider: string,
): Credential | undefined {
  return credentials.find(
    (credential) => credential.provider === provider && credential.enabled,
  );
}

export function settingsWrite(settings: ProviderSettings) {
  return {
    body: {
      expected_revision: settings.revision,
      interactive_consent: settings.interactive_consent,
      fallback_consent: settings.fallback_consent,
      background_consent: settings.background_consent,
      routes: settings.routes,
    },
    headers: { "If-Match": `"${settings.revision}"` },
  };
}
