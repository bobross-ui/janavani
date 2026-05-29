// Civic Almanac — Janavani mobile design tokens.
// Hex values are sRGB conversions of the oklch palette in the design handoff.
// Font family names match the cuts loaded by useFonts() in app/_layout.tsx;
// each weight is a separate registered family per @expo-google-fonts convention.

export const T = {
  // Paper / ink ramp
  paper: "#FAF8F3",
  paperAlt: "#F2EFE7",
  paperDim: "#E9E5DB",
  rule: "#D6D1C4",
  inkSoft: "#8A847A",
  inkMid: "#5C574F",
  ink: "#322F2A",
  inkDeep: "#23211E",

  // Accent / status
  accent: "#86322B",
  accentDeep: "#671E1B",
  accentSoft: "#F4E4DF",
  warn: "#9C503A",
  warnSoft: "#F2E2D6",
  good: "#456856",
  goodSoft: "#E1EAE3",

  // Soft halo tints — for marker glows, focus rings, etc.
  inkHalo: "rgba(50,47,42,0.14)",
  warnHalo: "rgba(156,80,58,0.18)",

  // Font families — each weight is its own registered family name.
  serif: "Newsreader_400Regular",
  sans: "DMSans_400Regular",
  sansMed: "DMSans_500Medium",
  sansSemi: "DMSans_600SemiBold",
  sansBold: "DMSans_700Bold",
  monoLight: "JetBrainsMono_300Light",
  mono: "JetBrainsMono_400Regular",
  monoMed: "JetBrainsMono_500Medium",

  // Spacing
  pad: 22,

  radius: {
    card: 14,
    well: 24,
    pill: 999,
  },

  // Google Maps style — warm-paper basemap. Used on Android via
  // customMapStyle. iOS uses mapType="mutedStandard" instead because Apple
  // Maps does not honor this JSON.
  mapStyle: [
    { elementType: "geometry", stylers: [{ color: "#F2EFE7" }] },
    { elementType: "labels.text.fill", stylers: [{ color: "#8A847A" }] },
    { elementType: "labels.text.stroke", stylers: [{ color: "#FAF8F3" }] },
    { featureType: "poi", stylers: [{ visibility: "off" }] },
    { featureType: "transit", stylers: [{ visibility: "off" }] },
    { featureType: "road", elementType: "geometry", stylers: [{ color: "#E9E5DB" }] },
    { featureType: "road.highway", elementType: "geometry", stylers: [{ color: "#D6D1C4" }] },
    { featureType: "road.arterial", elementType: "geometry", stylers: [{ color: "#D6D1C4" }] },
    { featureType: "road", elementType: "labels.text.fill", stylers: [{ color: "#5C574F" }] },
    { featureType: "water", elementType: "geometry", stylers: [{ color: "#E1EAE3" }] },
    { featureType: "water", elementType: "labels.text.fill", stylers: [{ color: "#456856" }] },
    { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#D6D1C4" }] },
    { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#F2EFE7" }] },
  ],
};
