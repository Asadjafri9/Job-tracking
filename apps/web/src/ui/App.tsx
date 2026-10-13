import { useEffect, useState, type ReactNode } from "react";
import { LandingPage } from "./Landing";
import { navigation, resolvePage, type Page } from "./navigation";
import { ProvidersPage } from "./providers";

function pageFromHash(): Page {
  return resolvePage(window.location.hash);
}

function Icon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    home: (
      <>
        <path d="m3 10 9-7 9 7" />
        <path d="M5 9v11h14V9M9 20v-6h6v6" />
      </>
    ),
    applications: (
      <>
        <rect x="3" y="7" width="18" height="14" rx="2" />
        <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
      </>
    ),
    email: (
      <>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3 7 9 6 9-6" />
      </>
    ),
    alerts: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="5" />
        <path d="m12 12 6-6" />
      </>
    ),
    profile: (
      <>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21a8 8 0 0 1 16 0" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
      </>
    ),
    arrow: (
      <>
        <path d="M5 12h14M13 6l6 6-6 6" />
      </>
    ),
    key: (
      <>
        <circle cx="8" cy="15" r="4" />
        <path d="m10.8 12.2 8.7-8.7M17 6l2 2M14.5 8.5l2 2" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name] ?? paths.home}
    </svg>
  );
}

export function App() {
  const [page, setPage] = useState<Page>(pageFromHash);
  const [account, setAccount] = useState<{
    email: string;
    csrf: string;
  } | null>(null);
  const [authStatus, setAuthStatus] = useState("Checking account…");
  const [authChecked, setAuthChecked] = useState(false);

  async function refreshAccount() {
    try {
      const response = await fetch("/auth/session", { credentials: "include" });
      if (!response.ok) throw new Error("signed out");
      const session = await response.json();
      setAccount({ email: session.login_email, csrf: session.csrf_token });
      setAuthStatus("Signed in");
    } catch {
      setAccount(null);
      setAuthStatus("Sign in to your workspace");
    } finally {
      setAuthChecked(true);
    }
  }

  async function signOut() {
    if (!account) return;
    const response = await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-Token": account.csrf },
    });
    if (response.ok) await refreshAccount();
  }

  useEffect(() => {
    const syncPage = () => setPage(pageFromHash());
    window.addEventListener("hashchange", syncPage);
    return () => window.removeEventListener("hashchange", syncPage);
  }, []);

  useEffect(() => {
    void refreshAccount();
  }, []);

  const pageTitle =
    navigation.find((item) => item.key === page)?.label ?? "Home";

  if (!authChecked) {
    return (
      <div className="app-loading" role="status">
        Checking your account…
      </div>
    );
  }

  if (!account) {
    return <LandingPage />;
  }

  return (
    <div className="app-frame">
      <aside className="sidebar" aria-label="Main navigation">
        <a className="brand" href="#home" aria-label="Career workspace home">
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

        <p className="nav-heading">Workspace</p>
        <nav className="navigation">
          {navigation.map((item) => (
            <a
              className={`nav-link${item.key === page ? " is-current" : ""}`}
              href={`#${item.key}`}
              aria-current={item.key === page ? "page" : undefined}
              key={item.key}
            >
              <span className="nav-icon">
                <Icon name={item.icon} />
              </span>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="privacy-note">
            <span className="privacy-symbol" aria-hidden="true">
              <Icon name="home" />
            </span>
            <div>
              <strong>Your choices come first</strong>
              <p>This preview has no account data or connected actions.</p>
            </div>
          </div>
          <div className="account">
            <span className="avatar" aria-hidden="true">
              <Icon name="profile" />
            </span>
            <span>
              <strong>{account.email}</strong>
              <small>{authStatus}</small>
            </span>
            <button
              className="preview-pill"
              type="button"
              onClick={() => void signOut()}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <p className="breadcrumb">
            <span>Workspace</span>
            <span aria-hidden="true">/</span>
            <strong>{pageTitle}</strong>
          </p>
          <button
            className="preview-pill account-action"
            type="button"
            onClick={() => void signOut()}
          >
            Sign out
          </button>
          <button
            className="icon-button"
            type="button"
            aria-label="Notifications are not connected"
            disabled
          >
            <Icon name="bell" />
          </button>
        </header>

        <div className="content">
          {page === "home" ? (
            <Home />
          ) : page === "providers" ? (
            <ProvidersPage csrf={account.csrf} signedIn />
          ) : (
            <section
              className="placeholder"
              aria-labelledby="placeholder-title"
            >
              <p className="eyebrow">FOUNDATION PREVIEW</p>
              <h1 id="placeholder-title">{pageTitle}</h1>
              <p>
                This area is planned but not implemented yet. No account data or
                actions are connected.
              </p>
              <a className="text-link" href="#home">
                Back to Home <Icon name="arrow" />
              </a>
            </section>
          )}
          <footer className="page-footer">
            A calm place to bring your next steps together.
          </footer>
        </div>
      </main>
    </div>
  );
}

function Home() {
  return (
    <>
      <section className="welcome" aria-labelledby="welcome-title">
        <p className="eyebrow">YOUR CAREER WORKSPACE</p>
        <h1 id="welcome-title">Your next step, made clearer.</h1>
        <p className="intro">
          Bring your job search details together and stay in control of every
          application.
        </p>
        <a className="primary-action" href="#profile">
          Set up your profile <Icon name="arrow" />
        </a>
      </section>

      <section className="empty-applications" aria-labelledby="empty-title">
        <div>
          <p className="eyebrow">APPLICATIONS</p>
          <h2 id="empty-title">No applications yet</h2>
          <p>
            Your application history will appear here after you start tracking
            roles.
          </p>
        </div>
        <a className="text-link" href="#applications">
          View applications <Icon name="arrow" />
        </a>
      </section>

      <p className="control-note">
        <strong>You stay in control.</strong> This preview does not fill forms,
        send email, or save data.
      </p>
    </>
  );
}
