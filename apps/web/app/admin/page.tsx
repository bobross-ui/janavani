"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { createComplaintDraft, listAdminClusters, updateClusterStatus } from "../../lib/api";
import type { ClusterRead, ComplaintDraftRead } from "../../lib/types";

const STATUSES = ["open", "drafted", "filed", "resolved"];

export default function AdminPage() {
  return (
    <Suspense fallback={<p className="muted">Loading admin dashboard…</p>}>
      <AdminDashboard />
    </Suspense>
  );
}

function AdminDashboard() {
  const searchParams = useSearchParams();
  const requestedCluster = searchParams.get("cluster") || "";
  const [clusters, setClusters] = useState<ClusterRead[]>([]);
  const [selectedId, setSelectedId] = useState(requestedCluster);
  const [draft, setDraft] = useState<ComplaintDraftRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    listAdminClusters()
      .then((data) => {
        setClusters(data);
        if (requestedCluster) {
          setSelectedId(requestedCluster);
        } else if (data.length > 0) {
          setSelectedId(data[0].id);
        }
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [requestedCluster]);

  const selected = useMemo(
    () => clusters.find((cluster) => cluster.id === selectedId) || null,
    [clusters, selectedId],
  );

  const handleDraft = async () => {
    if (!selectedId) return;
    setActionLoading(true);
    setError("");
    setMessage("");
    try {
      const newDraft = await createComplaintDraft(selectedId);
      setDraft(newDraft);
      setMessage("Draft generated.");
      setClusters((current) => current.map((cluster) => (
        cluster.id === selectedId ? { ...cluster, status: "drafted" } : cluster
      )));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate draft");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStatus = async (status: string) => {
    if (!selectedId) return;
    setActionLoading(true);
    setError("");
    setMessage("");
    try {
      await updateClusterStatus(selectedId, status);
      setClusters((current) => current.map((cluster) => (
        cluster.id === selectedId ? { ...cluster, status } : cluster
      )));
      setMessage(`Status updated to ${status}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update status");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) return <p className="muted">Loading admin dashboard…</p>;

  return (
    <div className="two-col">
      <section className="panel">
        <h2>Admin queue</h2>
        <p className="muted">Prioritize high-signal public clusters, generate formal complaint drafts, and move clusters through status.</p>
        {error ? <div className="error">{error}</div> : null}
        {message ? <p className="chip">{message}</p> : null}

        <div className="grid" style={{ marginTop: 16 }}>
          {clusters.map((cluster) => (
            <button
              className="card"
              key={cluster.id}
              onClick={() => { setSelectedId(cluster.id); setDraft(null); setMessage(""); }}
              style={{ textAlign: "left", cursor: "pointer", borderColor: cluster.id === selectedId ? "#2b6cb0" : undefined }}
            >
              <h2 className="card-title">{cluster.title}</h2>
              <div className="meta">
                <span className="chip">{cluster.grievance_count} reports</span>
                <span className="chip">{cluster.support_count} supporters</span>
                <span className="chip">Ward {cluster.ward || "unknown"}</span>
                <span className="chip">{cluster.status}</span>
              </div>
              <p className="muted">{cluster.summary}</p>
            </button>
          ))}
        </div>
      </section>

      <aside className="panel">
        <h2>Cluster action</h2>
        {selected ? (
          <>
            <p><strong>{selected.title}</strong></p>
            <p className="muted">{selected.department.replaceAll("_", " ")} · Ward {selected.ward || "unknown"}</p>
            <div className="meta">
              <Link className="button" href={`/clusters/${selected.id}`}>View public detail</Link>
              <button className="button primary" disabled={actionLoading} onClick={handleDraft}>
                {actionLoading ? "Working…" : "Generate draft"}
              </button>
            </div>
            <div className="filters">
              {STATUSES.map((status) => (
                <button
                  className={status === selected.status ? "button primary" : "button"}
                  disabled={actionLoading}
                  key={status}
                  onClick={() => handleStatus(status)}
                >
                  {status}
                </button>
              ))}
            </div>
            {draft ? (
              <section>
                <h2>{draft.title}</h2>
                <p className="muted">Department: {draft.department.replaceAll("_", " ")} · Language: {draft.language}</p>
                <pre className="draft">{draft.body}</pre>
              </section>
            ) : (
              <p className="muted">Generate a draft to preview the formal complaint text here.</p>
            )}
          </>
        ) : (
          <p className="muted">No clusters available.</p>
        )}
      </aside>
    </div>
  );
}
