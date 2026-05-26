"use client";

import dynamic from "next/dynamic";
import type { ClusterRead } from "../lib/types";

// Leaflet requires `window` — load client-only to avoid SSR/prerender crash.
const ClusterMapInner = dynamic(
  () => import("./cluster-map-inner").then((mod) => mod.ClusterMapInner),
  { ssr: false }
);

export function ClusterMap({ clusters }: { clusters: ClusterRead[] }) {
  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );
  if (withCoords.length === 0) return null;
  return <ClusterMapInner clusters={withCoords} />;
}
