import { Audio } from "expo-av";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { requestTTS } from "../lib/api";

interface AudioPlayerProps {
  text: string;
  language: string;
}

type PlaybackState = "loading" | "ready" | "playing" | "paused" | "error";

export function AudioPlayer({ text, language }: AudioPlayerProps) {
  const [state, setState] = useState<PlaybackState>("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [skipped, setSkipped] = useState(false);

  const soundRef = useRef<Audio.Sound | null>(null);

  // Fetch TTS audio and load into Audio.Sound on mount.
  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const uri = await requestTTS({ text, language });
        if (cancelled) return;

        // Configure audio mode for playback.
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: false,
          playsInSilentModeIOS: true,
          staysActiveInBackground: false,
          shouldDuckAndroid: true,
        });

        const { sound } = await Audio.Sound.createAsync(
          { uri },
          { shouldPlay: false },
          onPlaybackStatusUpdate
        );
        if (cancelled) {
          await sound.unloadAsync();
          return;
        }
        soundRef.current = sound;
        setState("ready");
      } catch (e: any) {
        if (cancelled) return;
        setErrorMessage(e?.message || "Failed to load audio");
        setState("error");
      }
    })();

    return () => {
      cancelled = true;
      // Cleanup sound.
      if (soundRef.current) {
        soundRef.current.unloadAsync().catch(() => {});
        soundRef.current = null;
      }
    };
  }, [text, language]);

  const onPlaybackStatusUpdate = useCallback(
    (status: any) => {
      if (!status.isLoaded) return;
      if (status.didJustFinish) {
        setState("ready");
        // Seek back to start for replay.
        soundRef.current?.setPositionAsync(0).catch(() => {});
      }
    },
    []
  );

  const handlePlayPause = useCallback(async () => {
    if (!soundRef.current) return;
    try {
      if (state === "playing") {
        await soundRef.current.pauseAsync();
        setState("paused");
      } else {
        await soundRef.current.playAsync();
        setState("playing");
      }
    } catch (e: any) {
      setErrorMessage(e?.message || "Playback error");
      setState("error");
    }
  }, [state]);

  const handleReplay = useCallback(async () => {
    if (!soundRef.current) return;
    try {
      await soundRef.current.setPositionAsync(0);
      await soundRef.current.playAsync();
      setState("playing");
    } catch (e: any) {
      setErrorMessage(e?.message || "Playback error");
      setState("error");
    }
  }, []);

  const handleSkip = useCallback(() => {
    setSkipped(true);
    if (soundRef.current) {
      soundRef.current.unloadAsync().catch(() => {});
      soundRef.current = null;
    }
  }, []);

  if (skipped) {
    return null;
  }

  // Loading state.
  if (state === "loading") {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="small" color="#2b6cb0" />
        <Text style={styles.loadingText}>Generating voice response…</Text>
      </View>
    );
  }

  // Error state — subtle, doesn't crash.
  if (state === "error") {
    return (
      <View style={styles.container}>
        <View style={styles.errorRow}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>
            {errorMessage || "Audio unavailable"}
          </Text>
        </View>
      </View>
    );
  }

  // Ready / playing / paused states.
  const isPlaying = state === "playing";
  const isPaused = state === "paused";

  return (
    <View style={styles.container}>
      <View style={styles.playerRow}>
        <Text style={styles.speakerIcon}>🔊</Text>
        <Text style={styles.label}>Voice response</Text>

        <TouchableOpacity
          style={[styles.button, isPlaying && styles.buttonActive]}
          onPress={handlePlayPause}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>
            {isPlaying ? "⏸" : "▶️"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, styles.replayButton]}
          onPress={handleReplay}
          activeOpacity={0.7}
        >
          <Text style={styles.buttonIcon}>🔄</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.skipButton}
          onPress={handleSkip}
          activeOpacity={0.7}
        >
          <Text style={styles.skipText}>Skip</Text>
        </TouchableOpacity>
      </View>

      {isPaused && (
        <Text style={styles.statusText}>Paused — tap play to resume</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#ebf4ff",
    borderRadius: 12,
    padding: 14,
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#bee3f8",
  },
  playerRow: {
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 8,
  },
  speakerIcon: {
    fontSize: 18,
  },
  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#2d3748",
    flex: 1,
  },
  button: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: "#2b6cb0",
    alignItems: "center",
    justifyContent: "center",
  },
  buttonActive: {
    backgroundColor: "#e53e3e",
  },
  buttonIcon: {
    fontSize: 16,
  },
  replayButton: {
    backgroundColor: "#718096",
  },
  skipButton: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#a0aec0",
  },
  skipText: {
    fontSize: 12,
    fontWeight: "600",
    color: "#718096",
  },
  statusText: {
    fontSize: 12,
    color: "#718096",
    marginTop: 6,
    textAlign: "center",
  },
  loadingText: {
    fontSize: 13,
    color: "#2d3748",
    marginLeft: 10,
  },
  errorRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  errorIcon: {
    fontSize: 16,
  },
  errorText: {
    fontSize: 13,
    color: "#e53e3e",
    flex: 1,
  },
});
