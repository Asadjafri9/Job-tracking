import { describe, expect, it } from "vitest";

import { gmailComposeUrl, mailtoUrl } from "./email";

const draft = {
  recipient_email: "hiring+dev@example.test",
  subject: "Applying: Backend & Platform — Q3",
  body: "Dear team,\n\nI applied for role #42 & would love to talk.\n\nBest,\nA?",
};

describe("compose URL builders", () => {
  it("encodes unicode, newlines, and reserved characters for Gmail", () => {
    const url = gmailComposeUrl(draft);
    expect(url.startsWith("https://mail.google.com/mail/?view=cm&fs=1&")).toBe(
      true,
    );
    const params = new URL(url).searchParams;
    // URLSearchParams round-trips the exact reviewed text.
    expect(params.get("to")).toBe(draft.recipient_email);
    expect(params.get("su")).toBe(draft.subject);
    expect(params.get("body")).toBe(draft.body);
    // Nothing unencoded could break parameter parsing.
    expect(url).not.toContain("\n");
    expect(decodeURIComponent(url)).toContain("&");
  });

  it("mailto carries the same reviewed content", () => {
    const url = mailtoUrl(draft);
    expect(
      url.startsWith(`mailto:${encodeURIComponent(draft.recipient_email)}`),
    ).toBe(true);
    const params = new URLSearchParams(url.slice(url.indexOf("?") + 1));
    expect(params.get("subject")).toBe(draft.subject);
    expect(params.get("body")).toBe(draft.body);
  });

  it("never accepts a job-provided target origin", () => {
    const url = gmailComposeUrl(draft);
    expect(url.startsWith("https://mail.google.com/")).toBe(true);
  });
});
