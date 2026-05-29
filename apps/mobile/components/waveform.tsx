import { useEffect, useMemo, useRef } from "react";
import { Animated, Easing, View } from "react-native";
import { T } from "../lib/theme";

// Deterministic pseudo-random bar heights so the visual rhythm is stable
// across renders. Same LCG as the prototype.
function seededHeights(bars: number, seed: number, min = 0.25): number[] {
  const out: number[] = [];
  let s = seed;
  for (let i = 0; i < bars; i++) {
    s = (s * 9301 + 49297) % 233280;
    out.push(min + (s / 233280) * (1 - min));
  }
  return out;
}

// ─── Waveform (live, animated) ───────────────────────────────────────
// Each bar pulses scaleY 0.25 → 1.0 on a 1.1s ease-in-out cycle, staggered
// by (i * 0.06) % 1.1 s. UI-thread driven via Animated.loop + native driver.

interface WaveformProps {
  active?: boolean;
  color?: string;
  height?: number;
  bars?: number;
}

export function Waveform({
  active = true,
  color = T.ink,
  height = 64,
  bars = 28,
}: WaveformProps) {
  const heights = useMemo(() => seededHeights(bars, 7), [bars]);
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "center",
        gap: 4,
        height,
        width: "100%",
      }}
    >
      {heights.map((h, i) => (
        <Bar key={i} index={i} h={h} height={height} color={color} active={active} />
      ))}
    </View>
  );
}

function Bar({
  index,
  h,
  height,
  color,
  active,
}: {
  index: number;
  h: number;
  height: number;
  color: string;
  active: boolean;
}) {
  const scaleY = useRef(new Animated.Value(active ? 0.25 : 1)).current;
  const loopRef = useRef<Animated.CompositeAnimation | null>(null);

  useEffect(() => {
    if (!active) {
      loopRef.current?.stop();
      Animated.timing(scaleY, {
        toValue: 1,
        duration: 200,
        useNativeDriver: true,
      }).start();
      return;
    }

    const staggerMs = ((index * 0.06) % 1.1) * 1000;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scaleY, {
          toValue: 1.0,
          duration: 1100,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(scaleY, {
          toValue: 0.25,
          duration: 1100,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    loopRef.current = loop;
    const start = setTimeout(() => loop.start(), staggerMs);
    return () => {
      clearTimeout(start);
      loop.stop();
    };
  }, [active, index, scaleY]);

  return (
    <Animated.View
      style={{
        width: 3,
        borderRadius: 2,
        backgroundColor: color,
        height: Math.round(h * height),
        opacity: active ? 1 : 0.45,
        transform: [{ scaleY }],
      }}
    />
  );
}

// ─── StaticWaveform (transcript preview / playback) ──────────────────

interface StaticWaveformProps {
  color?: string;
  height?: number;
  bars?: number;
  progress?: number;
}

export function StaticWaveform({
  color = T.ink,
  height = 36,
  bars = 48,
  progress = 1,
}: StaticWaveformProps) {
  const heights = useMemo(() => seededHeights(bars, 13, 0.2), [bars]);
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 2,
        height,
        width: "100%",
      }}
    >
      {heights.map((h, i) => (
        <View
          key={i}
          style={{
            flex: 1,
            borderRadius: 1,
            backgroundColor: i / bars < progress ? color : T.rule,
            height: Math.round(h * height),
          }}
        />
      ))}
    </View>
  );
}
