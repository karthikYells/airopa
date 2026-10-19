import { PublicPage } from "./components/PublicPage";
import { EuropePage } from "./components/EuropePage";
import { InternalView } from "./components/Internal";

// The internal view (GCC Fit) is left out of the public accessindia.nl build:
// build with VITE_PUBLIC_ONLY=true (see DEPLOY.md).
const PUBLIC_ONLY = (import.meta as any).env?.VITE_PUBLIC_ONLY === "true";
// VITE_ENGINE=europe builds the Europe Market Assessment page instead.
const ENGINE = (import.meta as any).env?.VITE_ENGINE ?? "india";

export default function App() {
  if (ENGINE === "europe") return <EuropePage />;
  const isInternal =
    !PUBLIC_ONLY &&
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).has("internal");

  return isInternal ? (
    <div className="min-h-screen sm:py-6"><InternalView /></div>
  ) : (
    <PublicPage />
  );
}
