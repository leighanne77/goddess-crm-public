/**
 * Phase 3 Slice 2 — voice recorder hook.
 *
 * State machine:
 *   idle → requesting-permission → recording → uploading → done
 *                                                       ↘ error
 *   (cancel from `recording` returns to `idle`, no upload.)
 *
 * MediaRecorder output format depends on the browser:
 *   - Chrome/Edge: audio/webm;codecs=opus
 *   - Firefox:     audio/ogg;codecs=opus   (or audio/webm)
 *   - Safari:      audio/mp4               (AAC inside MP4)
 * All three are handled server-side — webm/ogg/mp3/wav are passthrough
 * to Chirp; mp4 (Safari) gets transcoded to WAV via ffmpeg before the
 * provider call.
 *
 * Auto-stop at MAX_RECORDING_SEC (60s, matches Chirp's sync limit). One
 * second before that, the hook flips `nearMax` true so the UI can warn.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderState =
  | "idle"
  | "requesting-permission"
  | "recording"
  | "uploading"
  | "error";

export interface UseVoiceRecorder {
  state: RecorderState;
  transcript: string | null;
  error: string | null;
  /** Seconds elapsed in the current recording. 0 outside `recording`. */
  elapsedSec: number;
  /** True in the final 1s before auto-stop fires. */
  nearMax: boolean;
  start: () => Promise<void>;
  stop: () => void;
  cancel: () => void;
  /** Caller acks transcript so the hook can return to idle without re-rendering. */
  reset: () => void;
}

const MAX_RECORDING_SEC = 60;
const NEAR_MAX_WARNING_SEC = 59;

interface TranscribeResponse {
  text: string;
  duration_sec: number;
  cost_usd: number;
  provider: string;
  model_id: string;
}

export function useVoiceRecorder(): UseVoiceRecorder {
  const [state, setState] = useState<RecorderState>("idle");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [nearMax, setNearMax] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const tickRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);
  // `cancelled` is read inside the `onstop` handler. Use a ref because
  // setState is async — the stop event can fire before React rerenders.
  const cancelledRef = useRef(false);

  const cleanup = useCallback(() => {
    if (tickRef.current !== null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    setElapsedSec(0);
    setNearMax(false);
  }, []);

  // Tear down on unmount so a navigation away while recording doesn't
  // leak the microphone.
  useEffect(() => cleanup, [cleanup]);

  const start = useCallback(async () => {
    setError(null);
    setTranscript(null);
    setState("requesting-permission");
    cancelledRef.current = false;

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = (e as DOMException)?.name ?? "Error";
      setError(
        name === "NotAllowedError"
          ? "Microphone access denied. Enable it in your browser settings and try again."
          : `Couldn't access the microphone (${name}).`,
      );
      setState("error");
      return;
    }
    streamRef.current = stream;

    const recorder = new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      const wasCancelled = cancelledRef.current;
      const chunks = chunksRef.current;
      const mimeType = recorder.mimeType || "audio/webm";
      cleanup();

      if (wasCancelled || chunks.length === 0) {
        setState("idle");
        return;
      }

      setState("uploading");
      const blob = new Blob(chunks, { type: mimeType });
      const form = new FormData();
      // Filename hint helps server-side logging — the server doesn't
      // parse this for routing (content_type is what matters).
      form.append("audio", blob, "recording");

      try {
        const resp = await fetch("/api/voice/transcribe", {
          method: "POST",
          credentials: "include",
          body: form,
        });
        if (!resp.ok) {
          const body = await resp.text();
          setError(
            resp.status === 503
              ? "Voice mode isn't enabled yet."
              : `Transcription failed (HTTP ${resp.status}): ${body.slice(
                  0,
                  200,
                )}`,
          );
          setState("error");
          return;
        }
        const data: TranscribeResponse = await resp.json();
        setTranscript(data.text);
        setState("idle");
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Network error during upload",
        );
        setState("error");
      }
    };

    startedAtRef.current = Date.now();
    setState("recording");
    setElapsedSec(0);
    setNearMax(false);
    recorder.start();

    tickRef.current = window.setInterval(() => {
      const sec = Math.floor((Date.now() - startedAtRef.current) / 1000);
      setElapsedSec(sec);
      if (sec >= NEAR_MAX_WARNING_SEC && !nearMax) setNearMax(true);
      if (sec >= MAX_RECORDING_SEC) {
        // Auto-stop. Same path as a user-initiated stop.
        recorder.stop();
      }
    }, 200);
  }, [cleanup, nearMax]);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      cancelledRef.current = false;
      mediaRecorderRef.current.stop();
    }
  }, []);

  const cancel = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      cancelledRef.current = true;
      mediaRecorderRef.current.stop();
    } else {
      // Not recording yet (e.g. still asking for permission) — clean up
      // whatever we set up and return to idle.
      cleanup();
      setState("idle");
    }
  }, [cleanup]);

  const reset = useCallback(() => {
    setTranscript(null);
    setError(null);
    setState("idle");
  }, []);

  return {
    state,
    transcript,
    error,
    elapsedSec,
    nearMax,
    start,
    stop,
    cancel,
    reset,
  };
}
