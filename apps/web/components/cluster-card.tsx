import Link from "next/link";
import type { ClusterRead } from "../lib/types";

export function ClusterCard({ cluster }: { cluster: ClusterRead }) {
  const urgent = cluster.urgency_score >= 0.7;

  return (
    <Link className="card" href={`/clusters/${cluster.id}`}>
      <h2 className="card-title">{cluster.title}</h2>
      <div className="meta">
        <span className="chip">{cluster.issue_category.replaceAll("_", " ")}</span>
        <span className="chip">Ward {cluster.ward || "unknown"}</span>
        <span className="chip">{cluster.status}</span>
        {urgent ? <span className="chip urgent">urgent</span> : null}
      </div>
      <p className="muted">{cluster.summary}</p>
      <div className="meta" aria-label="Cluster statistics">
        <span>{cluster.grievance_count} reports</span>
        <span>{cluster.support_count} supporters</span>
        <span>{Math.round(cluster.urgency_score * 100)} urgency</span>
      </div>
    </Link>
  );
}
