"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getCluster } from "../../../lib/api";
import type { ClusterDetail } from "../../../lib/types";

export default function ClusterDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [cluster, setCluster] = useState<ClusterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getCluster(id)
      .then(setCluster)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="muted">Loading cluster…</p>;
  if (error) return <div className="error">Could not load cluster: {error}</div>;
  if (!cluster) return <div className="error">Cluster not found.</div>;

  return (
    <div className="two-col">
      <section className="panel">
        <Link className="button" href="/">← Back to public dashboard</Link>
        <h2 style={{ marginTop: 18 }}>{cluster.title}</h2>
        <div className="meta">
          <span className="chip">{cluster.issue_category.replaceAll("_", " ")}</span>
          <span className="chip">{cluster.department.replaceAll("_", " ")}</span>
          <span className="chip">Ward {cluster.ward || "unknown"}</span>
          <span className={cluster.urgency_score >= 0.7 ? "chip urgent" : "chip"}>
            {Math.round(cluster.urgency_score * 100)} urgency
          </span>
          <span className="chip">{cluster.status}</span>
        </div>
        <p>{cluster.summary}</p>
        <div className="grid stats">
          <div className="stat"><span className="value">{cluster.grievance_count}</span><span className="label">reports</span></div>
          <div className="stat"><span className="value">{cluster.support_count}</span><span className="label">supporters</span></div>
        </div>

        <h2>Redacted grievance samples</h2>
        <div className="samples">
          {cluster.sample_grievances.map((grievance) => (
            <article className="sample" key={grievance.id}>
              <p>{grievance.pii_redacted_text || "[redacted sample unavailable]"}</p>
              <p className="muted">Language: {grievance.language} · Status: {grievance.status}</p>
            </article>
          ))}
          {cluster.sample_grievances.length === 0 ? <p className="muted">No public samples yet.</p> : null}
        </div>
      </section>

      <aside className="panel">
        <h2>Official workflow</h2>
        <p className="muted">Use admin workflow to generate a formal complaint draft for this cluster.</p>
        <Link className="button primary" href={`/admin?cluster=${id}`}>Open in admin</Link>
      </aside>
    </div>
  );
}
