import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Animated,
  Easing,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
// TODO(expo-audio): expo-av is deprecated in Expo SDK 54 and emits warnings.
// Recording still depends on it here; migrate to expo-audio in a follow-up —
// out of scope for the redesign.
import { Audio } from "expo-av";
import * as Location from "expo-location";
import { getCluster, submitGrievance, supportCluster, uploadAudioGrievance } from "../lib/api";
import type { ClusterDetail, GrievanceResponse } from "../lib/types";
import { T } from "../lib/theme";
import { MOCK_USER_ID, WARD_LABEL } from "../lib/config";
import { daysOpenLabel, humanize, humanLanguage } from "../lib/format";
import {
  BackBtn,
  CTA,
  CircleBtn,
  Chip,
  Eyebrow,
  Icon,
  RedactedText,
  Rule,
  SectionLabel,
  Stat,
  TopBar,
} from "../components/ui";
import { StaticWaveform, Waveform } from "../components/waveform";

const LANGUAGES: Array<{ key: string; label: string }> = [
  { key: "hi-Latn", label: "Hinglish" },
  { key: "hi", label: "हिन्दी" },
  { key: "mr", label: "मराठी" },
  { key: "ta", label: "தமிழ்" },
  { key: "en", label: "English" },
];

type Phase = "idle" | "recording" | "result";

export default function SubmitScreen() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");

  // Input state
  const [text, setText] = useState("");
  const [showTextInput, setShowTextInput] = useState(false);
  const [language, setLanguage] = useState("hi-Latn");

  // Location
  const [locationConsent, setLocationConsent] = useState<string | null>(null);
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  // Mirror coords into a ref. GPS resolves asynchronously after mount, but
  // finishRecording → uploadAudio are created with empty deps and would
  // otherwise close over the initial coords (null) and drop them on upload.
  const coordsRef = useRef(coords);
  useEffect(() => {
    coordsRef.current = coords;
  }, [coords]);

  // Recording
  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [permissionDenied, setPermissionDenied] = useState(false);

  // Submission
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GrievanceResponse | null>(null);
  const [error, setError] = useState("");

  // Bootstrap mic + location permissions on mount.
  useEffect(() => {
    (async () => {
      const mic = await Audio.requestPermissionsAsync();
      setPermissionDenied(mic.status !== "granted");

      const loc = await Location.requestForegroundPermissionsAsync();
      setLocationConsent(loc.status);
      if (loc.status === "granted") {
        try {
          const pos = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          });
          setCoords({
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
          });
        } catch {
          // GPS unavailable — submit will fall through without coords.
        }
      }
    })();

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (recordingRef.current) recordingRef.current.stopAndUnloadAsync().catch(() => {});
    };
  }, []);

  const requestLocation = useCallback(async () => {
    const { status } = await Location.requestForegroundPermissionsAsync();
    setLocationConsent(status);
    if (status === "granted") {
      try {
        const pos = await Location.getCurrentPositionAsync({
          accuracy: Location.Accuracy.Balanced,
        });
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
      } catch {
        /* ignore */
      }
    }
  }, []);

  const startRecording = useCallback(async () => {
    setError("");
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== "granted") {
        setPermissionDenied(true);
        return;
      }
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });
      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();
      recordingRef.current = recording;
      setElapsedSeconds(0);
      setPhase("recording");
      timerRef.current = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    } catch (e: any) {
      setError(e?.message || "Could not start recording.");
    }
  }, []);

  const finishRecording = useCallback(
    async (upload: boolean): Promise<void> => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      const rec = recordingRef.current;
      recordingRef.current = null;
      if (!rec) {
        setPhase("idle");
        return;
      }
      try {
        await rec.stopAndUnloadAsync();
        const uri = rec.getURI();
        if (!upload || !uri) {
          setPhase("idle");
          return;
        }
        await uploadAudio(uri);
      } catch (e: any) {
        setError(e?.message || "Recording failed.");
        setPhase("idle");
      }
    },
    []
  );

  const uploadAudio = useCallback(
    async (uri: string) => {
      setLoading(true);
      setError("");
      try {
        const formData = new FormData();
        formData.append("audio", { uri, type: "audio/m4a", name: "recording.m4a" } as any);
        formData.append("user_id", MOCK_USER_ID);
        formData.append("consent_public", "true");
        // Read from the ref so a recording started before GPS resolved still
        // uploads the coordinates that arrived in the meantime.
        const cur = coordsRef.current;
        if (cur) {
          formData.append("latitude", String(cur.latitude));
          formData.append("longitude", String(cur.longitude));
        }
        const res = await uploadAudioGrievance(formData);
        setResult(res);
        setPhase("result");
      } catch (e: any) {
        setError(e?.message || "Upload failed.");
        setPhase("idle");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const submitText = useCallback(async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await submitGrievance({
        user_id: MOCK_USER_ID,
        text: text.trim(),
        language,
        consent_public: true,
        ...(coords ? { latitude: coords.latitude, longitude: coords.longitude } : {}),
      });
      setResult(res);
      setPhase("result");
    } catch (e: any) {
      setError(e?.message || "Submission failed.");
    } finally {
      setLoading(false);
    }
  }, [text, language, coords]);

  const resetToIdle = useCallback(() => {
    setResult(null);
    setError("");
    setText("");
    setShowTextInput(false);
    setPhase("idle");
  }, []);

  if (phase === "recording") {
    return (
      <RecordingView
        elapsedSeconds={elapsedSeconds}
        onCancel={() => finishRecording(false)}
        onStop={() => finishRecording(true)}
        loading={loading}
      />
    );
  }

  if (phase === "result" && result) {
    return (
      <ResultView
        result={result}
        onBack={resetToIdle}
        onSubmittedAlone={() => router.push("/profile")}
        onJoinedCluster={(cid) => router.push(`/cluster/${cid}?grievance_id=${result.grievance.id}`)}
      />
    );
  }

  return (
    <IdleView
      language={language}
      onLanguageChange={setLanguage}
      onMic={startRecording}
      permissionDenied={permissionDenied}
      showTextInput={showTextInput}
      onShowTextInput={() => setShowTextInput(true)}
      text={text}
      onTextChange={setText}
      onSubmitText={submitText}
      loading={loading}
      coords={coords}
      locationConsent={locationConsent}
      onRequestLocation={requestLocation}
      error={error}
    />
  );
}

// ─── Idle view ───────────────────────────────────────────────────────

function IdleView({
  language,
  onLanguageChange,
  onMic,
  permissionDenied,
  showTextInput,
  onShowTextInput,
  text,
  onTextChange,
  onSubmitText,
  loading,
  coords,
  locationConsent,
  onRequestLocation,
  error,
}: {
  language: string;
  onLanguageChange: (v: string) => void;
  onMic: () => void;
  permissionDenied: boolean;
  showTextInput: boolean;
  onShowTextInput: () => void;
  text: string;
  onTextChange: (v: string) => void;
  onSubmitText: () => void;
  loading: boolean;
  coords: { latitude: number; longitude: number } | null;
  locationConsent: string | null;
  onRequestLocation: () => void;
  error: string;
}) {
  const router = useRouter();
  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 48 }}>
        <TopBar leading={<BackBtn onPress={() => router.back()} />} eyebrow="New grievance" />

        <View style={{ paddingHorizontal: T.pad, paddingTop: 20, paddingBottom: 28 }}>
          <Eyebrow style={{ marginBottom: 12 }}>Step 01 / 02</Eyebrow>
          <Text style={styles.h1}>What's</Text>
          <Text style={styles.h1}>happening near you?</Text>
          <Text style={styles.lede}>
            Speak in any language — Hindi, Tamil, Marathi, Hinglish. We'll transcribe and
            route it for you.
          </Text>
        </View>

        {/* Mic well */}
        <View style={styles.micWell}>
          <DotGrid />
          <Pressable
            onPress={onMic}
            disabled={permissionDenied || loading}
            accessibilityRole="button"
            accessibilityLabel="Record grievance"
            accessibilityState={{ disabled: permissionDenied || loading }}
            style={({ pressed }) => [
              styles.micButton,
              { transform: [{ scale: pressed ? 0.97 : 1 }] },
            ]}
          >
            <Icon name="mic" size={36} stroke={T.paper} weight={1.4} />
          </Pressable>
          <Text style={styles.micCaption}>
            {permissionDenied ? "Microphone access needed" : "Tap to begin speaking"}
          </Text>
          <Text style={styles.micSubcaption}>Hold up to 60 seconds</Text>
        </View>

        {/* Language picker */}
        <View style={{ marginTop: 26 }}>
          <SectionLabel n="A">Language hint (optional)</SectionLabel>
          <View style={styles.langRow}>
            {LANGUAGES.map((l) => {
              const active = l.key === language;
              return (
                <Pressable
                  key={l.key}
                  onPress={() => onLanguageChange(l.key)}
                  accessibilityRole="button"
                  accessibilityLabel={l.label}
                  accessibilityState={{ selected: active }}
                  style={[
                    styles.langChip,
                    active && { backgroundColor: T.ink, borderColor: T.ink },
                  ]}
                >
                  <Text
                    style={{
                      fontFamily: T.sansMed,
                      fontSize: 13,
                      color: active ? T.paper : T.inkMid,
                      letterSpacing: -0.07,
                    }}
                  >
                    {l.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* Alt text input */}
        <View style={{ marginTop: 28, paddingHorizontal: T.pad }}>
          {showTextInput ? (
            <View style={styles.textInputBlock}>
              <TextInput
                value={text}
                onChangeText={onTextChange}
                placeholder="Describe the issue…"
                placeholderTextColor={T.inkSoft}
                multiline
                style={styles.textInput}
              />
              <CTA tone="ink" icon="arrow-right" onPress={onSubmitText} disabled={!text.trim() || loading}>
                {loading ? "Submitting…" : "Submit grievance"}
              </CTA>
            </View>
          ) : (
            <Pressable
              onPress={onShowTextInput}
              accessibilityRole="button"
              accessibilityLabel="Type your grievance instead"
              style={({ pressed }) => [styles.altInputPill, { opacity: pressed ? 0.7 : 1 }]}
            >
              <Icon name="pen" size={16} stroke={T.inkMid} />
              <Text style={styles.altInputText}>Or type it instead</Text>
              <View style={{ flex: 1 }} />
              <Icon name="arrow-right" size={14} stroke={T.inkSoft} />
            </Pressable>
          )}
        </View>

        {/* Location chip */}
        <Pressable
          onPress={locationConsent !== "granted" ? onRequestLocation : undefined}
          accessibilityRole={locationConsent !== "granted" ? "button" : undefined}
          accessibilityLabel="Location sharing"
          style={styles.locationRow}
        >
          <Icon name="pin" size={14} stroke={T.inkSoft} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text style={styles.locationLabel}>Location shared</Text>
            <Text style={styles.locationCoords}>
              {coords
                ? `${WARD_LABEL} · ${coords.latitude.toFixed(4)}°N, ${coords.longitude.toFixed(4)}°E`
                : locationConsent === "denied"
                ? "Tap to enable"
                : "Detecting…"}
            </Text>
          </View>
          <Text
            style={[
              styles.locationStatus,
              {
                color:
                  locationConsent === "granted" && coords
                    ? T.good
                    : locationConsent === "denied"
                    ? T.warn
                    : T.inkSoft,
              },
            ]}
          >
            {locationConsent === "granted" && coords
              ? "On"
              : locationConsent === "denied"
              ? "Off"
              : "…"}
          </Text>
        </Pressable>

        {error ? <Text style={styles.errorText}>{error}</Text> : null}
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── Recording view ──────────────────────────────────────────────────

function RecordingView({
  elapsedSeconds,
  onCancel,
  onStop,
  loading,
}: {
  elapsedSeconds: number;
  onCancel: () => void;
  onStop: () => void;
  loading: boolean;
}) {
  return (
    <SafeAreaView style={[styles.shell, { backgroundColor: T.inkDeep }]} edges={["top", "bottom"]}>
      <StatusBar style="light" />
      <TopBar
        tone="paper"
        leading={
          <CircleBtn tone="paper" onPress={onCancel} accessibilityLabel="Cancel recording">
            <Icon name="arrow-left" size={15} stroke={T.paper} />
          </CircleBtn>
        }
        eyebrow="Recording · live"
        trailing={<RecPulse />}
      />

      <View style={{ alignItems: "center", paddingTop: 40, paddingBottom: 12 }}>
        <Text style={styles.recordingListening}>Listening</Text>
        <Text style={styles.recordingTimer}>{formatTime(elapsedSeconds)}</Text>
      </View>

      <View style={{ paddingHorizontal: T.pad, paddingTop: 36, paddingBottom: 28 }}>
        <Waveform active={!loading} color={T.accent} height={80} bars={32} />
      </View>

      <View
        style={{
          marginHorizontal: T.pad,
          paddingVertical: 20,
          paddingHorizontal: 22,
          borderTopWidth: 1,
          borderTopColor: "rgba(255,255,255,0.12)",
          borderBottomWidth: 1,
          borderBottomColor: "rgba(255,255,255,0.12)",
        }}
      >
        {/*
          The spec shows a live partial transcript here (e.g. "yahaan paani
          nahin aa raha hai…"), but the backend transcribes only after upload —
          it does not stream partials. We keep an on-brand static caption and
          surface upload progress via the loading state instead.
        */}
        <Text style={styles.recordingHearingLabel}>{loading ? "Sending" : "Hearing"}</Text>
        <Text style={styles.recordingHearingBody}>
          {loading ? "Sending to server…" : "Capturing your voice. Tap stop when done."}
        </Text>
      </View>

      <View style={{ flex: 1 }} />

      <View style={styles.recordingControls}>
        <Pressable
          onPress={onCancel}
          accessibilityRole="button"
          accessibilityLabel="Cancel"
          style={({ pressed }) => [styles.smallDarkBtn, { opacity: pressed ? 0.55 : 1 }]}
        >
          <Text style={styles.smallDarkBtnText}>Cancel</Text>
        </Pressable>

        <Pressable
          onPress={onStop}
          accessibilityRole="button"
          accessibilityLabel="Stop recording"
          style={({ pressed }) => [styles.stopBtn, { transform: [{ scale: pressed ? 0.95 : 1 }] }]}
        >
          <View style={styles.stopHalo} />
          <View style={styles.stopInner}>
            <Icon name="stop" size={28} stroke={T.paper} />
          </View>
        </Pressable>

        <Pressable
          onPress={onStop}
          accessibilityRole="button"
          accessibilityLabel="Stop and finish"
          style={({ pressed }) => [styles.smallDarkBtn, { opacity: pressed ? 0.55 : 1 }]}
        >
          <Text style={styles.smallDarkBtnText}>Done</Text>
        </Pressable>
      </View>

      <Text style={styles.recordingHint}>Tap the centre to stop</Text>
    </SafeAreaView>
  );
}

function RecPulse() {
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 0,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 1,
          duration: 600,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  const opacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.45, 1] });
  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.9, 1] });
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
      <Animated.View
        style={{
          width: 7,
          height: 7,
          borderRadius: 4,
          backgroundColor: T.warn,
          opacity,
          transform: [{ scale }],
        }}
      />
      <Text
        style={{
          fontFamily: T.mono,
          fontSize: 10,
          letterSpacing: 1.6,
          color: "rgba(255,255,255,0.7)",
          textTransform: "uppercase",
        }}
      >
        REC
      </Text>
    </View>
  );
}

// ─── Result view ─────────────────────────────────────────────────────

function ResultView({
  result,
  onBack,
  onJoinedCluster,
  onSubmittedAlone,
}: {
  result: GrievanceResponse;
  onBack: () => void;
  onJoinedCluster: (clusterId: string) => void;
  onSubmittedAlone: () => void;
}) {
  const [matched, setMatched] = useState<ClusterDetail | null>(null);
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchError, setMatchError] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joined, setJoined] = useState(false);
  const [joinError, setJoinError] = useState("");

  useEffect(() => {
    if (!result.matched_cluster_id) return;
    setMatchLoading(true);
    setMatchError(false);
    getCluster(result.matched_cluster_id, MOCK_USER_ID)
      .then((c) => setMatched(c))
      .catch(() => setMatchError(true))
      .finally(() => setMatchLoading(false));
  }, [result.matched_cluster_id]);

  const handleJoin = useCallback(async () => {
    if (!result.matched_cluster_id) return;
    setJoining(true);
    setJoinError("");
    try {
      const body = {
        user_id: result.grievance.user_id || MOCK_USER_ID,
        grievance_id: result.grievance.id,
        consent_to_file: true,
      };
      console.log("[join] supportCluster", { clusterId: result.matched_cluster_id, body });
      await supportCluster(result.matched_cluster_id, body);
      setJoined(true);
    } catch (e: any) {
      console.log("[join] supportCluster ERROR:", JSON.stringify({
        message: e?.message,
        name: e?.name,
        status: e?.status,
        code: e?.code,
        stack: e?.stack?.slice(0, 300),
      }));
      setJoinError(e?.message || "Could not join.");
    } finally {
      setJoining(false);
    }
  }, [result.matched_cluster_id, result.grievance.id, result.grievance.user_id]);

  const ex = result.extraction;
  const recordingSeconds = Math.max(8, Math.round((result.grievance.raw_text || "").length / 8));
  const durationLabel = formatTime(recordingSeconds);

  return (
    <SafeAreaView style={styles.shell} edges={["top"]}>
      <ScrollView contentContainerStyle={{ paddingBottom: 56 }}>
        <TopBar
          leading={<BackBtn onPress={onBack} />}
          eyebrow="Heard"
          trailing={
            <Text style={{ fontFamily: T.mono, fontSize: 10, color: T.good, letterSpacing: 1.4 }}>
              SAVED
            </Text>
          }
        />

        <View style={{ paddingHorizontal: T.pad, paddingTop: 14, paddingBottom: 26 }}>
          <Text style={styles.h2}>We heard you.</Text>
          <Text style={styles.lede}>
            Here's the structured signal we extracted. Names and numbers were automatically
            redacted.
          </Text>
        </View>

        {/* Transcript card */}
        <View style={{ marginHorizontal: T.pad, marginBottom: 24 }}>
          <View style={styles.transcriptHeader}>
            <Eyebrow>Transcript · {humanLanguage(ex.language)}</Eyebrow>
            <Text style={{ fontFamily: T.mono, fontSize: 10, color: T.inkSoft, letterSpacing: 1.0 }}>
              {durationLabel}
            </Text>
          </View>
          <View style={styles.transcriptCard}>
            <StaticWaveform color={T.inkMid} height={28} bars={56} progress={1} />
            <RedactedText style={styles.transcriptText}>
              {`"${ex.pii_redacted_text || ex.normalized_text}"`}
            </RedactedText>
          </View>
        </View>

        {/* Extraction grid */}
        <SectionLabel n="01">Extracted signal</SectionLabel>
        <View style={styles.extractionGrid}>
          {[
            { label: "Category", value: humanize(ex.category), color: T.inkDeep },
            { label: "Department", value: ex.department || "—", color: T.inkDeep },
            {
              label: "Urgency",
              value: humanize(ex.urgency),
              color: (ex.urgency || "").toLowerCase() === "high" ? T.warn : T.inkDeep,
            },
            { label: "Ward", value: ex.ward || "—", color: T.inkDeep },
            { label: "Landmark", value: ex.landmark || "—", color: T.inkDeep },
            { label: "Language", value: ex.language || "—", color: T.inkDeep },
          ].map((cell) => (
            <View key={cell.label} style={styles.extractionCell}>
              <Text style={styles.extractionLabel}>{cell.label}</Text>
              <Text style={[styles.extractionValue, { color: cell.color }]}>{cell.value}</Text>
            </View>
          ))}
        </View>

        {/* Cluster suggestion */}
        {result.suggested_action === "join_cluster" && result.matched_cluster_id ? (
          <View style={{ marginTop: 32 }}>
            <SectionLabel n="02">Joins existing signal</SectionLabel>
            <View style={{ paddingHorizontal: T.pad, paddingTop: 14 }}>
              <View style={styles.clusterCard}>
                <View style={styles.clusterCardHeader}>
                  <Text style={styles.clusterCardEyebrow}>
                    CLUSTER MATCH{matched ? ` · ${matched.support_count} JOINED` : ""}
                  </Text>
                  <Text style={styles.clusterCardId}>#{result.matched_cluster_id.slice(0, 8)}</Text>
                </View>
                <Text style={styles.clusterCardTitle}>
                  {result.matched_cluster_title || matched?.title || "Existing signal"}
                </Text>
                {matched ? (
                  <View style={styles.clusterCardStats}>
                    <Stat value={matched.grievance_count} label="Reports" size="sm" />
                    <Stat value={matched.support_count} label="Joined" size="sm" />
                    <Stat value={daysOpenLabel(matched.created_at)} label="Open" size="sm" />
                  </View>
                ) : matchLoading ? (
                  <View style={[styles.clusterCardStats, { justifyContent: "center" }]}>
                    <ActivityIndicator color={T.accentDeep} />
                  </View>
                ) : matchError ? (
                  <Text style={styles.clusterCardNote}>Couldn't load cluster details.</Text>
                ) : null}
              </View>

              {joinError ? <Text style={styles.errorText}>{joinError}</Text> : null}

              {joined ? (
                <View style={{ marginTop: 14, gap: 10 }}>
                  <View style={styles.joinedRow}>
                    <Icon name="check" size={16} stroke={T.good} />
                    <Text style={styles.joinedText}>Joined · your voice was added</Text>
                  </View>
                  <CTA
                    tone="ghost"
                    icon="arrow-right"
                    onPress={() => onJoinedCluster(result.matched_cluster_id!)}
                  >
                    View cluster
                  </CTA>
                </View>
              ) : (
                <View style={{ marginTop: 14, gap: 10 }}>
                  <CTA tone="accent" icon="arrow-right" onPress={handleJoin} disabled={joining}>
                    {joining ? "Joining…" : "Add your voice"}
                  </CTA>
                  <Pressable
                    onPress={onSubmittedAlone}
                    accessibilityRole="button"
                    accessibilityLabel="Submit on its own instead"
                    style={styles.submitAlonePill}
                  >
                    <Text style={styles.submitAloneText}>Submit on its own instead</Text>
                  </Pressable>
                </View>
              )}
            </View>
          </View>
        ) : (
          <View style={{ marginTop: 32 }}>
            <SectionLabel n="02">New civic signal</SectionLabel>
            <View style={{ paddingHorizontal: T.pad, paddingTop: 14 }}>
              <View style={styles.newClusterCard}>
                <Text style={styles.clusterCardEyebrow}>FIRST OF ITS KIND NEARBY</Text>
                <Text style={styles.clusterCardTitle}>
                  Your report opened a new cluster.
                </Text>
                <Text style={styles.newClusterBody}>
                  Other citizens reporting the same issue will be grouped with yours.
                </Text>
              </View>
              <View style={{ marginTop: 14 }}>
                <CTA tone="ink" icon="arrow-right" onPress={onSubmittedAlone}>
                  View my reports
                </CTA>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ─── helpers ─────────────────────────────────────────────────────────

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

// Dot grid texture for the mic well background.
function DotGrid() {
  // 9×6 grid of subtle dots, plus a soft center vignette via a paperAlt disc.
  const cols = 13;
  const rows = 8;
  const dots: React.ReactNode[] = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      dots.push(
        <View
          key={`${r}-${c}`}
          style={{
            position: "absolute",
            left: `${(c / (cols - 1)) * 100}%`,
            top: `${(r / (rows - 1)) * 100}%`,
            width: 2,
            height: 2,
            borderRadius: 1,
            backgroundColor: T.rule,
            opacity: 0.55,
            transform: [{ translateX: -1 }, { translateY: -1 }],
          }}
        />
      );
    }
  }
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFillObject}>
      {dots}
      <View style={styles.micVignette} />
    </View>
  );
}

// ─── styles ──────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  shell: { flex: 1, backgroundColor: T.paper },

  h1: {
    fontFamily: T.serif,
    fontSize: 44,
    lineHeight: 44,
    color: T.inkDeep,
    letterSpacing: -1.1,
  },
  h2: {
    fontFamily: T.serif,
    fontSize: 38,
    lineHeight: 39,
    color: T.inkDeep,
    letterSpacing: -0.95,
  },
  lede: {
    marginTop: 14,
    fontFamily: T.sans,
    fontSize: 13.5,
    lineHeight: 20,
    color: T.inkSoft,
    maxWidth: 340,
  },

  // Mic well
  micWell: {
    marginHorizontal: T.pad,
    paddingTop: 44,
    paddingBottom: 36,
    paddingHorizontal: 24,
    backgroundColor: T.paperAlt,
    borderRadius: T.radius.well,
    borderWidth: 1,
    borderColor: T.rule,
    alignItems: "center",
    overflow: "hidden",
    position: "relative",
  },
  micButton: {
    width: 116,
    height: 116,
    borderRadius: 58,
    backgroundColor: T.ink,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: T.inkDeep,
    shadowOpacity: 0.25,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 14 },
    elevation: 6,
  },
  micVignette: {
    position: "absolute",
    left: "50%",
    top: "50%",
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: T.paperAlt,
    opacity: 0.85,
    transform: [{ translateX: -110 }, { translateY: -110 }],
  },
  micCaption: {
    marginTop: 26,
    fontFamily: T.serif,
    fontSize: 20,
    color: T.inkDeep,
    letterSpacing: -0.2,
  },
  micSubcaption: {
    marginTop: 10,
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.8,
    color: T.inkSoft,
    textTransform: "uppercase",
  },

  // Language picker
  langRow: {
    paddingHorizontal: T.pad,
    paddingTop: 14,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  langChip: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: T.radius.pill,
    borderWidth: 1,
    borderColor: T.rule,
  },

  // Alt input
  altInputPill: {
    width: "100%",
    paddingVertical: 16,
    paddingHorizontal: 18,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
  },
  altInputText: {
    fontFamily: T.sans,
    fontSize: 14,
    color: T.inkMid,
  },
  textInputBlock: { gap: 12 },
  textInput: {
    minHeight: 120,
    padding: 14,
    fontFamily: T.serif,
    fontSize: 17,
    lineHeight: 24,
    color: T.inkDeep,
    backgroundColor: T.paperAlt,
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
    textAlignVertical: "top",
  },

  // Location chip
  locationRow: {
    marginTop: 24,
    marginHorizontal: T.pad,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderTopWidth: 1,
    borderTopColor: T.rule,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  locationLabel: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  locationCoords: {
    fontFamily: T.sans,
    fontSize: 12.5,
    color: T.inkMid,
    marginTop: 2,
  },
  locationStatus: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.0,
    textTransform: "uppercase",
  },

  // Recording
  recordingListening: {
    fontFamily: T.mono,
    fontSize: 12,
    letterSpacing: 2.6,
    color: "rgba(255,255,255,0.5)",
    textTransform: "uppercase",
    marginBottom: 18,
  },
  recordingTimer: {
    fontFamily: T.monoLight,
    fontSize: 92,
    lineHeight: 92,
    letterSpacing: -4.6,
    color: T.paper,
    fontVariant: ["tabular-nums"],
  },
  recordingHearingLabel: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.8,
    color: "rgba(255,255,255,0.5)",
    textTransform: "uppercase",
    marginBottom: 10,
  },
  recordingHearingBody: {
    fontFamily: T.serif,
    fontSize: 18,
    lineHeight: 24,
    color: T.paper,
    letterSpacing: -0.09,
  },
  recordingControls: {
    paddingHorizontal: T.pad,
    paddingBottom: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 24,
  },
  smallDarkBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.22)",
    alignItems: "center",
    justifyContent: "center",
  },
  smallDarkBtnText: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.0,
    color: T.paper,
    textTransform: "uppercase",
  },
  stopBtn: {
    width: 112,
    height: 112,
    alignItems: "center",
    justifyContent: "center",
  },
  stopHalo: {
    position: "absolute",
    width: 112,
    height: 112,
    borderRadius: 56,
    backgroundColor: T.accent,
    opacity: 0.22,
  },
  stopInner: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: T.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  recordingHint: {
    textAlign: "center",
    paddingBottom: 8,
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: "rgba(255,255,255,0.4)",
    textTransform: "uppercase",
  },

  // Result — transcript card
  transcriptHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 10,
  },
  transcriptCard: {
    padding: 18,
    backgroundColor: T.paperAlt,
    borderRadius: T.radius.card,
    borderWidth: 1,
    borderColor: T.rule,
  },
  transcriptText: {
    marginTop: 14,
    fontFamily: T.serif,
    fontSize: 17,
    lineHeight: 25,
    color: T.inkDeep,
    letterSpacing: -0.085,
  },

  // Result — extraction grid
  extractionGrid: {
    paddingHorizontal: T.pad,
    paddingTop: 14,
    flexDirection: "row",
    flexWrap: "wrap",
  },
  extractionCell: {
    width: "50%",
    paddingTop: 10,
    paddingRight: 8,
    paddingBottom: 12,
    borderTopWidth: 1,
    borderTopColor: T.rule,
  },
  extractionLabel: {
    fontFamily: T.mono,
    fontSize: 9.5,
    letterSpacing: 1.5,
    color: T.inkSoft,
    textTransform: "uppercase",
  },
  extractionValue: {
    marginTop: 4,
    fontFamily: T.serif,
    fontSize: 17,
    letterSpacing: -0.085,
  },

  // Result — cluster card
  clusterCard: {
    padding: 18,
    backgroundColor: T.accentSoft,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: T.accent,
  },
  clusterCardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 6,
  },
  clusterCardEyebrow: {
    fontFamily: T.mono,
    fontSize: 10,
    letterSpacing: 1.6,
    color: T.accentDeep,
    textTransform: "uppercase",
  },
  clusterCardId: {
    fontFamily: T.mono,
    fontSize: 11,
    color: T.accentDeep,
    fontVariant: ["tabular-nums"],
  },
  clusterCardTitle: {
    marginTop: 6,
    fontFamily: T.serif,
    fontSize: 22,
    color: T.inkDeep,
    lineHeight: 25,
    letterSpacing: -0.33,
  },
  clusterCardStats: {
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: T.accent,
    flexDirection: "row",
    gap: 18,
  },
  clusterCardNote: {
    marginTop: 14,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: T.accent,
    fontFamily: T.mono,
    fontSize: 10.5,
    letterSpacing: 1.0,
    color: T.accentDeep,
    textTransform: "uppercase",
  },
  newClusterCard: {
    padding: 18,
    backgroundColor: T.paperAlt,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: T.rule,
    // NOTE: Android renders dashed borders inconsistently (may fall back to
    // solid). Accepted per spec; revisit with an SVG overlay if it regresses.
    borderStyle: "dashed",
  },
  newClusterBody: {
    marginTop: 10,
    fontFamily: T.sans,
    fontSize: 13.5,
    lineHeight: 20,
    color: T.inkSoft,
  },
  joinedRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  joinedText: {
    fontFamily: T.mono,
    fontSize: 11,
    letterSpacing: 1.0,
    color: T.good,
    textTransform: "uppercase",
  },
  submitAlonePill: {
    alignItems: "center",
    paddingVertical: 14,
  },
  submitAloneText: {
    fontFamily: T.sans,
    fontSize: 13,
    color: T.inkSoft,
    textDecorationLine: "underline",
    textDecorationColor: T.rule,
  },
  errorText: {
    marginTop: 12,
    marginHorizontal: T.pad,
    fontFamily: T.sans,
    fontSize: 13,
    color: T.warn,
  },
});
