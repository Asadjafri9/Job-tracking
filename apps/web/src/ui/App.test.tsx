import { describe, expect, it } from "vitest";

import { resolvePage } from "./navigation";

describe("workspace navigation", () => {
  it.each([
    "home",
    "applications",
    "email",
    "job-alerts",
    "profile",
    "providers",
  ])("opens the %s page from its hash", (page) => {
    expect(resolvePage(`#${page}`)).toBe(page);
  });

  it("returns home for an empty or unknown hash", () => {
    expect(resolvePage("")).toBe("home");
    expect(resolvePage("#unplanned-page")).toBe("home");
  });
});
