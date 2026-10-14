export function LandingPage() {
  return (
    <div className="landing">
      <header className="landing-header">
        <a className="brand" href="#top" aria-label="Rolevo home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M8 25V7h8a6 6 0 0 1 0 12H8m7 0 9 6" />
              <path d="m24.5 4 .8 2.4 2.4.8-2.4.8-.8 2.4-.8-2.4-2.4-.8 2.4-.8.8-2.4Z" />
            </svg>
          </span>
          <span className="brand-copy">
            <span className="brand-name">Rolevo</span>
            <span className="brand-caption">Career workspace</span>
          </span>
        </a>
        <a className="landing-signin" href="/auth/login">
          Sign in
        </a>
      </header>

      <main className="landing-main">
        <section className="landing-hero" aria-labelledby="landing-title">
          <p className="eyebrow">JOB APPLICATION COPILOT</p>
          <h1 id="landing-title">
            Apply with less busywork — and keep every receipt.
          </h1>
          <p className="intro">
            Rolevo helps you fill applications, draft personalized emails, and
            watch the career pages you care about — while you stay in control of
            every submit and send.
          </p>
          <div className="landing-actions">
            <a className="primary-action" href="/auth/login">
              Get started
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </a>
            <a className="text-link" href="#how-it-works">
              See how it works
            </a>
          </div>
          <p className="landing-note">
            Free during beta. Sign-up is handled by the secure identity service.
          </p>
        </section>

        <section
          className="landing-features"
          id="how-it-works"
          aria-labelledby="features-title"
        >
          <h2 id="features-title" className="visually-hidden">
            How it works
          </h2>
          <div className="feature-card">
            <span className="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <rect x="3" y="7" width="18" height="14" rx="2" />
                <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
              </svg>
            </span>
            <h3>Assisted autofill, honest tracking</h3>
            <p>
              The browser extension reads the form you choose and fills answers
              from your confirmed profile. It never submits — it records what
              actually happened.
            </p>
          </div>
          <div className="feature-card">
            <span className="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <rect x="3" y="5" width="18" height="14" rx="2" />
                <path d="m3 7 9 6 9-6" />
              </svg>
            </span>
            <h3>Personalized email drafts</h3>
            <p>
              Drafts built from your profile and the posting open straight into
              Gmail compose. You review and press send — the send is confirmed,
              not assumed.
            </p>
          </div>
          <div className="feature-card">
            <span className="feature-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <circle cx="12" cy="12" r="9" />
                <circle cx="12" cy="12" r="5" />
                <path d="m12 12 6-6" />
              </svg>
            </span>
            <h3>Daily monitoring that respects sites</h3>
            <p>
              Watch up to five public career pages once a day, on your schedule
              and timezone. Get notified only when something actually changed.
            </p>
          </div>
        </section>

        <section className="landing-trust" aria-labelledby="trust-title">
          <h2 id="trust-title">Your data stays yours</h2>
          <ul className="trust-list">
            <li>
              Provider keys are optional and stored encrypted — you set exactly
              what each key may be used for.
            </li>
            <li>
              Nothing submits an application or sends an email without you.
            </li>
            <li>Export or delete your workspace at any time.</li>
          </ul>
          <a className="primary-action" href="/auth/login">
            Create your workspace
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </a>
        </section>
      </main>

      <footer className="landing-footer">
        <p>Rolevo · a calm place to bring your next steps together.</p>
      </footer>
    </div>
  );
}
