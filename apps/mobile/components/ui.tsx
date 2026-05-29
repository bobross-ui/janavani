import { ReactElement, ReactNode } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextStyle,
  View,
  ViewStyle,
} from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { T } from "../lib/theme";

// ─── Icon ────────────────────────────────────────────────────────────
// 11 stroke-based glyphs, 24×24 viewBox. No emoji anywhere in the app.

export type IconName =
  | "mic"
  | "stop"
  | "arrow-left"
  | "arrow-right"
  | "pin"
  | "check"
  | "plus"
  | "spark"
  | "user"
  | "pen"
  | "dot";

interface IconProps {
  name: IconName;
  size?: number;
  stroke?: string;
  weight?: number;
}

export function Icon({ name, size = 18, stroke = T.ink, weight = 1.5 }: IconProps) {
  const common = {
    stroke,
    strokeWidth: weight,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    fill: "none" as const,
  };
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24">
      {(() => {
        switch (name) {
          case "mic":
            return (
              <>
                <Rect x="9" y="3" width="6" height="12" rx="3" {...common} />
                <Path d="M5 11a7 7 0 0 0 14 0" {...common} />
                <Path d="M12 18v3" {...common} />
              </>
            );
          case "stop":
            return <Rect x="7" y="7" width="10" height="10" rx="1.5" fill={stroke} />;
          case "arrow-left":
            return (
              <>
                <Path d="M14 6l-6 6 6 6" {...common} />
                <Path d="M20 12H8" {...common} />
              </>
            );
          case "arrow-right":
            return (
              <>
                <Path d="M5 12h13" {...common} />
                <Path d="M13 6l6 6-6 6" {...common} />
              </>
            );
          case "pin":
            return (
              <>
                <Path d="M12 21s7-6.5 7-12a7 7 0 1 0-14 0c0 5.5 7 12 7 12z" {...common} />
                <Circle cx="12" cy="9" r="2.5" {...common} />
              </>
            );
          case "check":
            return <Path d="M5 12l4 4 10-10" {...common} />;
          case "plus":
            return (
              <>
                <Path d="M12 5v14" {...common} />
                <Path d="M5 12h14" {...common} />
              </>
            );
          case "spark":
            return <Path d="M3 17l5-7 4 4 5-9 4 6" {...common} />;
          case "user":
            return (
              <>
                <Circle cx="12" cy="8" r="4" {...common} />
                <Path d="M4 21c1.5-4 5-6 8-6s6.5 2 8 6" {...common} />
              </>
            );
          case "pen":
            return <Path d="M14 4l6 6L9 21H3v-6L14 4z" {...common} />;
          case "dot":
            return <Circle cx="12" cy="12" r="4" fill={stroke} />;
        }
      })()}
    </Svg>
  );
}

// ─── Rule ────────────────────────────────────────────────────────────
// 1px hairline; vertical or horizontal, soft variant uses paperDim.

export function Rule({
  vertical = false,
  soft = false,
  strong = false,
  style,
}: {
  vertical?: boolean;
  soft?: boolean;
  strong?: boolean;
  style?: ViewStyle;
}) {
  const color = strong ? T.ink : soft ? T.paperDim : T.rule;
  return (
    <View
      style={[
        vertical ? { width: 1, alignSelf: "stretch" } : { height: 1, width: "100%" },
        { backgroundColor: color },
        style,
      ]}
    />
  );
}

// ─── BackBtn ─────────────────────────────────────────────────────────
// 32×32 rule-bordered circle with an arrow-left.

export function BackBtn({
  onPress,
  tone = "ink",
}: {
  onPress?: () => void;
  tone?: "ink" | "paper";
}) {
  const borderColor = tone === "paper" ? "rgba(255,255,255,0.18)" : T.rule;
  const strokeColor = tone === "paper" ? T.paper : T.ink;
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel="Go back"
      style={({ pressed }) => [
        styles.circleBtn,
        { borderColor, opacity: pressed ? 0.55 : 1 },
      ]}
    >
      <Icon name="arrow-left" size={15} stroke={strokeColor} />
    </Pressable>
  );
}

// ─── CircleBtn (generic 32px chrome button) ──────────────────────────

export function CircleBtn({
  onPress,
  children,
  tone = "ink",
  accessibilityLabel,
}: {
  onPress?: () => void;
  children: ReactNode;
  tone?: "ink" | "paper";
  accessibilityLabel?: string;
}) {
  const borderColor = tone === "paper" ? "rgba(255,255,255,0.18)" : T.rule;
  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      style={({ pressed }) => [
        styles.circleBtn,
        { borderColor, opacity: pressed ? 0.55 : 1 },
      ]}
    >
      {children}
    </Pressable>
  );
}

// ─── TopBar ──────────────────────────────────────────────────────────
// 3-col chrome: 32px leading slot · centered mono eyebrow · 32px trailing slot.

export function TopBar({
  leading,
  eyebrow,
  trailing,
  tone = "ink",
}: {
  leading?: ReactNode;
  eyebrow?: ReactNode;
  trailing?: ReactNode;
  tone?: "ink" | "paper";
}) {
  return (
    <View style={styles.topbar}>
      <View style={styles.topbarSlot}>{leading}</View>
      <Eyebrow tone={tone} numberOfLines={1} style={styles.topbarEyebrow}>
        {eyebrow}
      </Eyebrow>
      <View style={[styles.topbarSlot, { alignItems: "flex-end" }]}>
        {trailing}
      </View>
    </View>
  );
}

// ─── Chip ────────────────────────────────────────────────────────────

type ChipTone = "default" | "accent" | "warn" | "good" | "ink" | "outline";
type ChipSize = "xs" | "sm";

export function Chip({
  children,
  tone = "default",
  size = "sm",
  mono = false,
  onPress,
}: {
  children: ReactNode;
  tone?: ChipTone;
  size?: ChipSize;
  mono?: boolean;
  onPress?: () => void;
}) {
  const palette: Record<ChipTone, { bg: string; fg: string; br: string }> = {
    default: { bg: T.paperAlt, fg: T.inkMid, br: T.rule },
    accent: { bg: T.accentSoft, fg: T.accentDeep, br: "transparent" },
    warn: { bg: T.warnSoft, fg: T.warn, br: "transparent" },
    good: { bg: T.goodSoft, fg: T.good, br: "transparent" },
    ink: { bg: T.ink, fg: T.paper, br: T.ink },
    outline: { bg: "transparent", fg: T.inkMid, br: T.rule },
  };
  const p = palette[tone];
  const isXs = size === "xs";
  const fs = isXs ? 10 : 11;
  const ls = isXs ? 0.8 : 0.44;
  const padV = isXs ? 3 : 5;
  const padH = isXs ? 8 : 10;

  const inner = (
    <Text
      style={{
        fontFamily: mono ? T.mono : T.sansMed,
        fontSize: fs,
        letterSpacing: ls,
        color: p.fg,
        textTransform: mono ? "uppercase" : "none",
      }}
    >
      {children}
    </Text>
  );

  const wrapStyle: ViewStyle = {
    backgroundColor: p.bg,
    borderColor: p.br,
    borderWidth: 1,
    borderRadius: T.radius.pill,
    paddingVertical: padV,
    paddingHorizontal: padH,
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
  };

  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={typeof children === "string" ? children : undefined}
        style={({ pressed }) => [wrapStyle, { opacity: pressed ? 0.7 : 1 }]}
      >
        {inner}
      </Pressable>
    );
  }
  return <View style={wrapStyle}>{inner}</View>;
}

// ─── Stat ────────────────────────────────────────────────────────────
// Mono numeric value over a mono uppercase label.

export function Stat({
  value,
  label,
  size = "md",
  align = "left",
  valueColor,
}: {
  value: string | number | ReactElement;
  label: string;
  size?: "sm" | "md" | "lg";
  align?: "left" | "center" | "right";
  valueColor?: string;
}) {
  const fs = size === "lg" ? 38 : size === "md" ? 28 : 20;
  const ls = size === "lg" ? -1.5 : size === "md" ? -0.6 : -0.4;
  return (
    <View style={{ alignItems: align === "center" ? "center" : align === "right" ? "flex-end" : "flex-start" }}>
      <Text
        style={{
          fontFamily: T.mono,
          fontSize: fs,
          letterSpacing: ls,
          color: valueColor ?? T.inkDeep,
          lineHeight: fs,
          fontVariant: ["tabular-nums"],
        }}
      >
        {value}
      </Text>
      <Text
        style={{
          marginTop: 6,
          fontFamily: T.mono,
          fontSize: 10,
          letterSpacing: 1.4,
          color: T.inkSoft,
          textTransform: "uppercase",
        }}
      >
        {label}
      </Text>
    </View>
  );
}

// ─── CTA ─────────────────────────────────────────────────────────────
// 56px fully-rounded primary button. ink / accent / ghost tones.

export function CTA({
  children,
  onPress,
  tone = "ink",
  icon,
  iconSide = "right",
  disabled = false,
}: {
  children: ReactNode;
  onPress?: () => void;
  tone?: "ink" | "accent" | "ghost";
  icon?: IconName;
  iconSide?: "left" | "right";
  disabled?: boolean;
}) {
  const palette = {
    ink: { bg: T.ink, fg: T.paper, br: T.ink },
    accent: { bg: T.accent, fg: T.paper, br: T.accent },
    ghost: { bg: "transparent", fg: T.ink, br: T.rule },
  }[tone];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      accessibilityLabel={typeof children === "string" ? children : undefined}
      style={({ pressed }) => [
        styles.cta,
        {
          backgroundColor: palette.bg,
          borderColor: palette.br,
          opacity: disabled ? 0.45 : 1,
          transform: [{ scale: pressed ? 0.98 : 1 }],
        },
      ]}
    >
      {icon && iconSide === "left" ? (
        <Icon name={icon} size={16} stroke={palette.fg} />
      ) : null}
      <Text
        style={{
          fontFamily: T.sansMed,
          fontSize: 15,
          letterSpacing: -0.075,
          color: palette.fg,
        }}
      >
        {children}
      </Text>
      {icon && iconSide === "right" ? (
        <Icon name={icon} size={16} stroke={palette.fg} />
      ) : null}
    </Pressable>
  );
}

// ─── SectionLabel ────────────────────────────────────────────────────
// Optional small index · uppercase caption · horizontal hairline.

export function SectionLabel({
  children,
  n,
  style,
}: {
  children: ReactNode;
  n?: ReactNode;
  style?: ViewStyle;
}) {
  return (
    <View style={[styles.sectionLabel, style]}>
      {n != null ? <Text style={styles.sectionN}>{n}</Text> : null}
      <Text style={styles.sectionText}>{children}</Text>
      <View style={{ flex: 1, height: 1, backgroundColor: T.rule, marginLeft: 10 }} />
    </View>
  );
}

// ─── Text helpers ────────────────────────────────────────────────────
// Pre-styled Text components for the recurring type roles.

export function Eyebrow({
  children,
  style,
  tone = "ink",
  numberOfLines,
}: {
  children: ReactNode;
  style?: TextStyle;
  tone?: "ink" | "paper";
  numberOfLines?: number;
}) {
  return (
    <Text
      numberOfLines={numberOfLines}
      style={[
        {
          fontFamily: T.mono,
          fontSize: 10.5,
          letterSpacing: 1.9,
          textTransform: "uppercase",
          color: tone === "paper" ? "rgba(255,255,255,0.55)" : T.inkSoft,
        },
        style,
      ]}
    >
      {children}
    </Text>
  );
}

// ─── RedactedText ────────────────────────────────────────────────────
// Renders a PII-redacted string: each ███ run becomes an inline span with a
// paperDim background + inkMid text, matching the redaction styling in the
// design spec. Non-redacted spans inherit the surrounding text style.

export function RedactedText({
  children,
  style,
  numberOfLines,
}: {
  children: string;
  style?: TextStyle;
  numberOfLines?: number;
}) {
  const parts = (children ?? "").split(/(█+)/g).filter((p) => p.length > 0);
  return (
    <Text style={style} numberOfLines={numberOfLines}>
      {parts.map((part, i) =>
        /^█+$/.test(part) ? (
          <Text key={i} style={styles.redactedRun}>
            {part}
          </Text>
        ) : (
          part
        )
      )}
    </Text>
  );
}

// ─── styles ──────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  circleBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 1,
    backgroundColor: "transparent",
    alignItems: "center",
    justifyContent: "center",
  },
  topbar: {
    flexDirection: "row",
    alignItems: "center",
    paddingTop: 14,
    paddingBottom: 18,
    paddingHorizontal: T.pad,
  },
  topbarSlot: {
    minWidth: 32,
    flexDirection: "row",
  },
  topbarEyebrow: {
    flex: 1,
    textAlign: "center",
    paddingHorizontal: 8,
  },
  cta: {
    width: "100%",
    height: 56,
    borderRadius: T.radius.pill,
    borderWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    paddingHorizontal: 24,
  },
  sectionLabel: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: T.pad,
  },
  sectionN: {
    fontFamily: T.mono,
    fontSize: 10,
    color: T.inkSoft,
    letterSpacing: 1.0,
    marginRight: 10,
  },
  sectionText: {
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.9,
    color: T.inkMid,
    textTransform: "uppercase",
  },
  redactedRun: {
    backgroundColor: T.paperDim,
    color: T.inkMid,
    borderRadius: 3,
  },
});
