import { useEffect, useState } from "react";
import { getMethodology } from "../services/api";

export default function MethodologyPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    getMethodology().then(setData).catch(() => setData(null));
  }, []);

  return (
    <div className="page-block">
      <h1 className="page-title">Methodology</h1>
      <p className="page-subtitle">How ImpactScore is computed and what gets filtered out.</p>
      <pre className="methodology-block">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
