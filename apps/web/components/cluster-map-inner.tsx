"use client";

import { useEffect } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import type { ClusterRead } from "../lib/types";

import "leaflet/dist/leaflet.css";

// Fix Leaflet default icon paths (broken in bundlers)
// @ts-expect-error — leaflet default icon handling
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function urgencyColor(score: number): string {
  if (score >= 0.8) return "#e53e3e";
  if (score >= 0.6) return "#dd6b20";
  if (score >= 0.4) return "#d69e2e";
  return "#38a169";
}

function markerRadius(count: number): number {
  return Math.max(8, Math.min(24, 8 + Math.sqrt(count) * 4));
}

function ClusterMarkers({ clusters }: { clusters: ClusterRead[] }) {
  const map = useMap();

  useEffect(() => {
    if (clusters.length > 0) {
      // Refit bounds whenever the cluster set changes
      const bounds = L.latLngBounds(
        clusters.map(
          (c) => [c.centroid_latitude!, c.centroid_longitude!] as [number, number]
        )
      );
      // Single marker: zoom in; multiple: fit bounds
      if (clusters.length === 1) {
        map.setView(bounds.getCenter(), 15);
      } else {
        map.fitBounds(bounds.pad(0.3));
      }
    }
  }, [clusters, map]);

  return (
    <>
      {clusters.map((cluster) => {
        const r = markerRadius(cluster.grievance_count);
        const icon = L.divIcon({
          className: "cluster-marker",
          html: `<div style="
            width:${r * 2}px;height:${r * 2}px;
            background:${urgencyColor(cluster.urgency_score)};
            border-radius:50%;border:2px solid white;
            box-shadow:0 1px 4px rgba(0,0,0,0.3);
            display:flex;align-items:center;justify-content:center;
            color:white;font-size:${Math.max(10, r * 0.6)}px;font-weight:bold;
          ">${cluster.grievance_count}</div>`,
          iconSize: [r * 2, r * 2],
          iconAnchor: [r, r],
        });

        return (
          <Marker
            key={cluster.id}
            position={[cluster.centroid_latitude!, cluster.centroid_longitude!]}
            icon={icon}
          >
            <Popup>
              <strong>{cluster.title}</strong>
              <br />
              {cluster.ward ? `Ward ${cluster.ward} · ` : ""}
              {cluster.issue_category.replace(/_/g, " ")}
              <br />
              {cluster.grievance_count} reports · {cluster.support_count} supporters
              <br />
              Urgency: {(cluster.urgency_score * 100).toFixed(0)}%
              <br />
              <a href={`/clusters/${cluster.id}`}>View details →</a>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}

export function ClusterMapInner({ clusters }: { clusters: ClusterRead[] }) {
  return (
    <section style={{ marginBottom: 24 }}>
      <MapContainer
        center={[19.076, 72.877]}
        zoom={13}
        style={{ height: "400px", borderRadius: "8px" }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClusterMarkers clusters={clusters} />
      </MapContainer>
    </section>
  );
}
