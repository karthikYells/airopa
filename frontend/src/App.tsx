import { PublicPage } from "./components/PublicPage";
import { InternalView } from "./components/Internal";

export default function App() {
  const isInternal =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).has("internal");

  return <div className="min-h-screen py-0 sm:py-6">{isInternal ? <InternalView /> : <PublicPage />}</div>;
}
