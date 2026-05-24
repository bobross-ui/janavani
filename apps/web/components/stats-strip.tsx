import type { ClusterRead, DashboardStats } from "../lib/types";

function computeStats(clusters: ClusterRead[]): DashboardStats {
  return {
    totalClusters: clusters.length,
    totalReports: clusters.reduce((sum, c) => sum + c.grievance_count, 0),
    totalSupporters: clusters.reduce((sum, c) => sum + c.support_count, 0),
    urgentClusters: clusters.filter((c) => c.urgency_score >= 0.7).length,
    openClusters: clusters.filter((c) => c.status === "open").length,
  };
}

export function StatsStrip({ clusters }: { clusters: ClusterRead[] }) {
  const stats = computeStats(clusters);
  const items = [
    ["Public clusters", stats.totalClusters],
    ["Citizen reports", stats.totalReports],
    ["Supporters", stats.totalSupporters],
    ["Urgent clusters", stats.urgentClusters],
    ["Open clusters", stats.openClusters],
  ] as const;

  return (
    <section className="grid stats" aria-label="Dashboard statistics">
      {items.map(([label, value]) => (
        <div className="stat" key={label}>
          <span className="value">{value}</span>
          <span className="label">{label}</span>
        </div>
      ))}
    </section>
  );
}
