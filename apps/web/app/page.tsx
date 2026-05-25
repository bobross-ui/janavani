"use client";

import { useEffect, useMemo, useState } from "react";
import { ClusterCard } from "../components/cluster-card";
import { StatsStrip } from "../components/stats-strip";
import { API_BASE_URL, listClusters } from "../lib/api";
import type { ClusterRead } from "../lib/types";

export default function PublicDashboardPage() {
  const [clusters, setClusters] = useState<ClusterRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ward, setWard] = useState("");
  const [category, setCategory] = useState("");

  useEffect(() => {
    listClusters()
      .then(setClusters)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const wards = useMemo(
    () => Array.from(new Set(clusters.map((c) => c.ward).filter(Boolean))).sort(),
    [clusters],
  );
  const categories = useMemo(
    () => Array.from(new Set(clusters.map((c) => c.issue_category).filter(Boolean))).sort(),
    [clusters],
  );

  const filtered = clusters.filter((cluster) => {
    if (ward && cluster.ward !== ward) return false;
    if (category && cluster.issue_category !== category) return false;
    return true;
  });

  return (
    <>
      <section className="panel">
        <h2>Public issue map, minus the map dependency</h2>
        <p className="muted">
          Phase 6 starts with a resilient, data-first dashboard. MapLibre can be layered in once locations are geocoded;
          today this view shows clustered civic demand by ward, issue, urgency, and support.
        </p>
        <p className="muted">API: {API_BASE_URL}</p>
      </section>

      {loading ? <p className="muted">Loading public issues…</p> : null}
      {error ? <div className="error">Could not load clusters: {error}</div> : null}

      {!loading && !error ? (
        <>
          {clusters.length === 0 ? (
            <section className="panel">
              <p className="muted">
                No issue clusters yet. Run <code>make demo</code> from the
                project root to seed sample data with four clusters across
                Wards 2, 4, 8, and 11.
              </p>
            </section>
          ) : (
            <>
          <StatsStrip clusters={clusters} />

          <section className="filters" aria-label="Cluster filters">
            <select value={ward} onChange={(event) => setWard(event.target.value)} aria-label="Filter by ward">
              <option value="">All wards</option>
              {wards.map((w) => <option key={w} value={w}>Ward {w}</option>)}
            </select>
            <select value={category} onChange={(event) => setCategory(event.target.value)} aria-label="Filter by category">
              <option value="">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c.replaceAll("_", " ")}</option>)}
            </select>
            {(ward || category) ? (
              <button className="button" onClick={() => { setWard(""); setCategory(""); }}>Clear filters</button>
            ) : null}
          </section>

          <section className="grid cluster-grid" aria-label="Public issue clusters">
            {filtered.map((cluster) => <ClusterCard key={cluster.id} cluster={cluster} />)}
          </section>

          {filtered.length === 0 ? <p className="muted">No clusters match those filters.</p> : null}
          </>
        )}
        </>
      ) : null}
    </>
  );
}
