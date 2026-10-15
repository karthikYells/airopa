import { useState } from "react";
import { scoreCompany } from "./api";
import { Landing } from "./components/Landing";
import { SnapshotView } from "./components/Snapshot";
import { InternalView } from "./components/Internal";
import type { Snapshot } from "./types";

export default function App() {
  const isInternal =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).has("internal");

  const [data, setData] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (url: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await scoreCompany(url);
      setData(res);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen paper-grain">
      <div className="rule-top" />
      {isInternal ? (
        <InternalView />
      ) : data ? (
        <SnapshotView data={data} onReset={() => setData(null)} />
      ) : (
        <Landing onSubmit={run} loading={loading} error={error} />
      )}
    </div>
  );
}
