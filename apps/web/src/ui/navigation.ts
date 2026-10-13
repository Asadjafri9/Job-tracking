export const navigation = [
  { label: "Home", key: "home", icon: "home" },
  { label: "Applications", key: "applications", icon: "applications" },
  { label: "Email", key: "email", icon: "email" },
  { label: "Job alerts", key: "job-alerts", icon: "alerts" },
  { label: "Profile", key: "profile", icon: "profile" },
  { label: "Documents", key: "documents", icon: "documents" },
  { label: "AI providers", key: "providers", icon: "key" },
] as const;

export type Page = (typeof navigation)[number]["key"];

export function resolvePage(hash: string): Page {
  const page = hash.replace(/^#/, "") as Page;
  return navigation.some((item) => item.key === page) ? page : "home";
}
