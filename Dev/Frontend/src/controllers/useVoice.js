import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../models/api.js";

const MAX_SECONDS = 60;
const MAX_BYTES = 10 * 1024 * 1024;

export function useVoice(api, onTranscript) {
  const [state, setState] = useState("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const current = useRef(null);
  const supported = Boolean(
    globalThis.isSecureContext &&
      navigator.mediaDevices?.getUserMedia &&
      globalThis.MediaRecorder,
  );

  function release(session) {
    clearInterval(session.timer);
    session.stream?.getTracks().forEach((track) => track.stop());
  }

  function dispose() {
    const session = current.current;
    current.current = null;
    if (!session) return;
    session.controller.abort();
    if (session.recorder?.state === "recording") session.recorder.stop();
    release(session);
  }

  function cancel() {
    dispose();
    setState("idle");
    setSeconds(0);
  }

  function stop() {
    const session = current.current;
    if (session?.recorder?.state !== "recording") return;
    session.recorder.stop();
    release(session);
    setState("transcribing");
  }

  async function start() {
    if (current.current) return;
    setError("");
    if (!supported) {
      setError(
        "Recording is unavailable in this browser. You can still type your message.",
      );
      return;
    }
    const session = { controller: new AbortController(), chunks: [], bytes: 0 };
    current.current = session;
    setState("permission");
    setSeconds(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      session.stream = stream;
      if (current.current !== session) {
        release(session);
        return;
      }
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      if (!mimeType)
        throw new Error(
          "This browser cannot record a supported audio format. You can still type your message.",
        );
      const recorder = new MediaRecorder(stream, { mimeType });
      session.recorder = recorder;
      recorder.ondataavailable = ({ data }) => {
        if (current.current !== session || !data.size) return;
        session.bytes += data.size;
        if (session.bytes > MAX_BYTES) {
          cancel();
          setError(
            "The recording is too large. Please record a shorter message.",
          );
          return;
        }
        session.chunks.push(data);
      };
      recorder.onerror = () => {
        if (current.current !== session) return;
        cancel();
        setError("Recording stopped unexpectedly. Please try again.");
      };
      recorder.onstop = async () => {
        release(session);
        if (current.current !== session) return;
        setState("transcribing");
        try {
          const blob = new Blob(session.chunks, { type: recorder.mimeType });
          if (!blob.size)
            throw new Error("No audio was recorded. Please try again.");
          const text = await api.transcribe(blob, session.controller.signal);
          if (current.current === session) onTranscript(text);
        } catch (error) {
          if (current.current === session) setError(errorMessage(error));
        } finally {
          if (current.current === session) {
            current.current = null;
            setState("idle");
          }
        }
      };
      recorder.start(1000);
      setState("recording");
      const started = Date.now();
      session.timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000);
        setSeconds(Math.min(elapsed, MAX_SECONDS));
        if (elapsed >= MAX_SECONDS) stop();
      }, 250);
    } catch (error) {
      release(session);
      if (current.current !== session) return;
      current.current = null;
      setState("idle");
      setError(
        error.name === "NotAllowedError"
          ? "Microphone access was denied. Allow microphone access in your browser, or type your message."
          : error.name === "NotFoundError"
            ? "No microphone was found. You can still type your message."
            : error.message ||
              "The microphone could not start. Please try again.",
      );
    }
  }

  useEffect(() => () => dispose(), []);
  return { state, seconds, error, supported, start, stop, cancel };
}

export function useSpeechPlayback(api) {
  const [playback, setPlayback] = useState({
    id: null,
    state: "idle",
    error: "",
  });
  const current = useRef(null);

  function dispose() {
    const session = current.current;
    current.current = null;
    if (!session) return;
    session.controller.abort();
    if (session.audio) {
      session.audio.onended = null;
      session.audio.onerror = null;
      session.audio.pause();
      session.audio.removeAttribute("src");
      session.audio.load();
    }
    if (session.url) URL.revokeObjectURL(session.url);
  }

  function stop() {
    dispose();
    setPlayback({ id: null, state: "idle", error: "" });
  }

  async function play(text, id) {
    dispose();
    const session = { controller: new AbortController() };
    current.current = session;
    setPlayback({ id, state: "loading", error: "" });
    try {
      const blob = await api.synthesize(text, session.controller.signal);
      if (current.current !== session) return;
      session.url = URL.createObjectURL(blob);
      session.audio = new Audio(session.url);
      const fail = (message) => {
        if (current.current !== session) return;
        dispose();
        setPlayback({ id, state: "error", error: message });
      };
      session.audio.onended = () => {
        if (current.current === session) stop();
      };
      session.audio.onerror = () =>
        fail("This audio could not play. Please try again, or read the reply.");
      await session.audio.play();
      if (current.current === session)
        setPlayback({ id, state: "playing", error: "" });
    } catch (error) {
      if (current.current !== session) return;
      dispose();
      setPlayback({
        id,
        state: "error",
        error:
          error.name === "NotAllowedError"
            ? "Your browser blocked playback. Select Play reply to try again."
            : errorMessage(error),
      });
    }
  }

  useEffect(() => () => dispose(), []);
  return { ...playback, play, stop };
}
