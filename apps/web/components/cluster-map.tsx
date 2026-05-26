"use client";

import { useEffect, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import type { ClusterRead } from "../lib/types";

// Fix Leaflet default icon paths (broken in bundlers)
import "leaflet/dist/leaflet.css";

// @ts-expect-error — leaflet default icon handling
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function urgencyColor(score: number): string {
  if (score >= 0.8) return "#e53e3e"; // red
  if (score >= 0.6) return "#dd6b20"; // orange
  if (score >= 0.4) return "#d69e2e"; // yellow
  return "#38a169"; // green
}

function markerRadius(count: number): number {
  return Math.max(8, Math.min(24, 8 + Math.sqrt(count) * 4));
}

function ClusterMarkers({ clusters }: { clusters: ClusterRead[] }) {
  const map = useMap();
  const [boundsSet, setBoundsSet] = useState(false);

  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );

  useEffect(() => {
    if (withCoords.length > 0 && !boundsSet) {
      const bounds = L.latLngBounds(
        withCoords.map((c) => [c.centroid_latitude!, c.centroid_longitude!] as [number, number])
      );
      map.fitBounds(bounds.pad(0.3));
      setBoundsSet(true);
    }
  }, [withCoords, map, boundsSet]);

  return (
    <>
      {withCoords.map((cluster) => {
        const icon = L.divIcon({
          className: "cluster-marker",
          html: `<div style="
            width:${markerRadius(cluster.grievance_count) * 2}px;
            height:${markerRadius(cluster.grievance_count) * 2}px;
            background:${urgencyColor(cluster.urgency_score)};
            border-radius:50%;
            border:2px solid white;
            box-shadow:0 1px 4px rgba(0,0,0,0.3);
            display:flex;
            align-items:center;
            justify-content:center;
            color:white;
            font-size:${Math.max(10, markerRadius(cluster.grievance_count) * 0.6)}px;
            font-weight:bold;
          ">${cluster.grievance_count}</div>`,
          iconSize: [markerRadius(cluster.grievance_count) * 2, markerRadius(cluster.grievance_count) * 2],
          iconAnchor: [markerRadius(cluster.grievance_count), markerRadius(cluster.grievance_count)],
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

export function ClusterMap({ clusters }: { clusters: ClusterRead[] }) {
  const withCoords = clusters.filter(
    (c) => c.centroid_latitude != null && c.centroid_longitude != null
  );

  if (withCoords.length === 0) return null;

  return (
    <section style={{ marginBottom: 24 }}>
      <MapContainer
        center={[19.076, 72.877]} // Mumbai default
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
