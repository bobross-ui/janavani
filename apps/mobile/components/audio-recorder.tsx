import { Audio } from "expo-av";
import { useCallback, useEffect, useRef, useState } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface AudioRecorderProps {
  onRecordingComplete?: (uri: string) => void;
}

type RecorderState = "idle" | "recording" | "review";

export function AudioRecorder({ onRecordingComplete }: AudioRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [recordedUri, setRecordedUri] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recordingRef = useRef<Audio.Recording | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Request microphone permissions on mount.
  useEffect(() => {
    (async () => {
      const { status } = await Audio.requestPermissionsAsync();
      setPermissionDenied(status !== "granted");
    })();

    return () => {
      // Cleanup timer and recording on unmount.
      if (timerRef.current) clearInterval(timerRef.current);
      if (recordingRef.current) {
        recordingRef.current.stopAndUnloadAsync().catch(() => {});
      }
    };
  }, []);

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      // Re-check permission.
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== "granted") {
        setPermissionDenied(true);
        return;
      }

      // Configure audio mode for recording.
      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      await recording.startAsync();

      recordingRef.current = recording;
      setState("recording");
      setElapsedSeconds(0);

      timerRef.current = setInterval(() => {
        setElapsedSeconds((s) => s + 1);
      }, 1000);
    } catch (e: any) {
      setError(e?.message || "Failed to start recording");
    }
  }, []);

  const stopRecording = useCallback(async () => {
    if (!recordingRef.current) return;

    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    try {
      await recordingRef.current.stopAndUnloadAsync();
      const uri = recordingRef.current.getURI();
      recordingRef.current = null;

      if (uri) {
        setRecordedUri(uri);
        setState("review");
      } else {
        setError("Recording produced no file");
        setState("idle");
      }
    } catch (e: any) {
      setError(e?.message || "Failed to stop recording");
      setState("idle");
    }
  }, []);

  const handleReRecord = useCallback(() => {
    setRecordedUri(null);
    setElapsedSeconds(0);
    setState("idle");
  }, []);

  const handleUpload = useCallback(() => {
    if (recordedUri && onRecordingComplete) {
      onRecordingComplete(recordedUri);
    }
  }, [recordedUri, onRecordingComplete]);

  const formatTime = (totalSec: number): string => {
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Permission denied state.
  if (permissionDenied) {
    return (
      <View style={styles.container}>
        <View style={[styles.micButton, styles.micDenied]}>
          <Text style={styles.micIcon}>🎤</Text>
        </View>
        <View style={styles.info}>
          <Text style={styles.title}>Microphone permission needed</Text>
          <Text style={styles.subtitle}>
            Grant microphone access in Settings to record voice grievances.
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {state === "idle" && (
        <>
          <TouchableOpacity
            style={styles.micButton}
            onPress={startRecording}
            activeOpacity={0.7}
          >
            <Text style={styles.micIcon}>🎤</Text>
          </TouchableOpacity>
          <View style={styles.info}>
            <Text style={styles.title}>Voice grievance</Text>
            <Text style={styles.subtitle}>
              Tap the mic to record — no language selection needed.
            </Text>
          </View>
        </>
      )}

      {state === "recording" && (
        <>
          <TouchableOpacity
            style={[styles.micButton, styles.micRecording]}
            onPress={stopRecording}
            activeOpacity={0.7}
          >
            <Text style={styles.micIcon}>⏹</Text>
          </TouchableOpacity>
          <View style={styles.info}>
            <Text style={styles.title}>Recording…</Text>
            <Text style={styles.timer}>{formatTime(elapsedSeconds)}</Text>
          </View>
        </>
      )}

      {state === "review" && (
        <View style={styles.reviewContainer}>
          <View style={styles.reviewRow}>
            <View style={[styles.micButton, styles.micDone]}>
              <Text style={styles.micIcon}>✅</Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.title}>Recording complete</Text>
              <Text style={styles.subtitle}>
                Duration: {formatTime(elapsedSeconds)}
              </Text>
            </View>
          </View>
          <View style={styles.reviewButtons}>
            <TouchableOpacity
              style={styles.reRecordButton}
              onPress={handleReRecord}
              activeOpacity={0.7}
            >
              <Text style={styles.reRecordText}>Re-record</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.uploadButton}
              onPress={handleUpload}
              activeOpacity={0.7}
            >
              <Text style={styles.uploadText}>Upload</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#f7fafc",
    borderRadius: 12,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
  },
  reviewContainer: {
    width: "100%",
  },
  reviewRow: {
    flexDirection: "row",
    alignItems: "center",
  },
  reviewButtons: {
    flexDirection: "row",
    marginTop: 12,
    gap: 8,
  },
  micButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#E6F4FE",
    alignItems: "center",
    justifyContent: "center",
  },
  micRecording: {
    backgroundColor: "#FEE2E2",
  },
  micDone: {
    backgroundColor: "#D1FAE5",
  },
  micDenied: {
    backgroundColor: "#FEF3C7",
  },
  micIcon: { fontSize: 22 },
  info: { marginLeft: 14, flex: 1 },
  title: { fontSize: 14, fontWeight: "700", color: "#2d3748" },
  subtitle: { fontSize: 12, color: "#718096", marginTop: 2 },
  timer: {
    fontSize: 18,
    fontWeight: "600",
    color: "#e53e3e",
    marginTop: 2,
  },
  reRecordButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#cbd5e0",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  reRecordText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#4a5568",
  },
  uploadButton: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: "#2b6cb0",
    alignItems: "center",
  },
  uploadText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#fff",
  },
  errorBanner: {
    width: "100%",
    marginTop: 8,
    backgroundColor: "#fff5f5",
    padding: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#fecaca",
  },
  errorText: {
    fontSize: 12,
    color: "#e53e3e",
  },
});
