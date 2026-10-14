// Bounded durable outbox for passive tracking events. Entries carry only
// metadata — never profile facts, answers, DOM, keys, or document text —
// and are bound to the extension session token they were queued under, so a
// sign-out or account switch can never replay another account's events.
(() => {
  const STORAGE_KEY = "rolevoOutbox";
  const MAX_ENTRIES = 32;
  const MAX_PAYLOAD_BYTES = 4096;
  const MAX_ATTEMPTS = 8;
  const TTL_MS = 24 * 60 * 60 * 1000;

  const ALLOWED_FIELDS = new Set([
    "event_idempotency_key",
    "application_session_id",
    "evidence_type",
    "evidence_source",
    "observed_at",
    "signal_code",
    "gesture_ref_hash",
    "evidence",
  ]);
  const ALLOWED_EVIDENCE_FIELDS = new Set([
    "final_url_hash",
    "outcome_code",
    "page_changed",
    "navigation_occurred",
  ]);

  function sanitize(raw) {
    if (!raw || typeof raw !== "object") return null;
    const event = {};
    for (const [key, value] of Object.entries(raw)) {
      if (!ALLOWED_FIELDS.has(key)) continue;
      if (key === "evidence") {
        const evidence = {};
        for (const [name, item] of Object.entries(value ?? {})) {
          if (ALLOWED_EVIDENCE_FIELDS.has(name)) evidence[name] = item;
        }
        event.evidence = evidence;
      } else {
        event[key] = value;
      }
    }
    if (
      typeof event.event_idempotency_key !== "string" ||
      typeof event.evidence_type !== "string" ||
      typeof event.evidence_source !== "string" ||
      typeof event.observed_at !== "string" ||
      Number.isNaN(Date.parse(event.observed_at))
    ) {
      return null;
    }
    const bytes = new TextEncoder().encode(JSON.stringify(event)).length;
    if (bytes > MAX_PAYLOAD_BYTES) return null;
    event.evidence ??= {};
    return event;
  }

  function createOutbox({ storage, send, now = () => Date.now() }) {
    async function read() {
      const saved = await storage.get(STORAGE_KEY);
      return Array.isArray(saved[STORAGE_KEY]) ? saved[STORAGE_KEY] : [];
    }

    async function write(entries) {
      await storage.set({ [STORAGE_KEY]: entries });
      return entries.length;
    }

    async function enqueue(rawEvent, accountKey) {
      const event = sanitize(rawEvent);
      if (!event || typeof accountKey !== "string" || !accountKey) {
        return { queued: false, reason: "invalid_event" };
      }
      const entries = await read();
      if (entries.some((entry) => entry.event.event_idempotency_key === event.event_idempotency_key)) {
        return { queued: false, reason: "duplicate" };
      }
      const fresh = entries.filter((entry) => now() - entry.enqueued_at <= TTL_MS);
      fresh.push({ account_key: accountKey, enqueued_at: now(), attempts: 0, event });
      const bounded = fresh.slice(-MAX_ENTRIES);
      await write(bounded);
      return { queued: true, dropped_oldest: fresh.length - bounded.length };
    }

    async function flush(accountKey) {
      const entries = await read();
      const remaining = [];
      let sent = 0;
      for (const entry of entries) {
        const expired = now() - entry.enqueued_at > TTL_MS;
        const foreign = !accountKey || entry.account_key !== accountKey;
        if (expired || foreign) continue; // never send another account's events
        try {
          await send(entry.event);
          sent += 1; // server dedupes on event_idempotency_key
        } catch (error) {
          if (error?.terminal) continue; // 4xx or signed out: replay cannot help
          entry.attempts += 1;
          if (entry.attempts < MAX_ATTEMPTS) remaining.push(entry);
        }
      }
      await write(remaining);
      return { sent, pending: remaining.length };
    }

    async function purge() {
      await write([]);
    }

    async function pendingCount() {
      return (await read()).length;
    }

    return { enqueue, flush, purge, pendingCount };
  }

  globalThis.ExtensionOutbox = Object.freeze({
    createOutbox,
    sanitize,
    STORAGE_KEY,
    MAX_ENTRIES,
    MAX_PAYLOAD_BYTES,
    TTL_MS,
  });
})();
