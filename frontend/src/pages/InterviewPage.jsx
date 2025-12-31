import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  startInterview,
  submitAnswer,
  normalizeAudioUrl,
} from "../api/interviews";

function getSpeechRecognition() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export default function InterviewPage() {
  const { sessionId } = useParams();
  const nav = useNavigate();

  const [status, setStatus] = useState("in_progress"); // in_progress | generating | completed
  const [questionText, setQuestionText] = useState("");
  const [questionAudioUrl, setQuestionAudioUrl] = useState(null);

  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  // local preview before submit
  const [pendingBlob, setPendingBlob] = useState(null);
  const [pendingAudioUrl, setPendingAudioUrl] = useState(null);

  const audioRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const recognitionRef = useRef(null);
  const SpeechRecognition = useMemo(() => getSpeechRecognition(), []);

  const isWaiting = status === "generating" || status === "waiting";
  const isCompleted = status === "completed";
  const canRecord =
    !busy &&
    !isWaiting &&
    !isCompleted &&
    status === "in_progress" &&
    !pendingBlob;

  const clearPending = useCallback(() => {
    if (pendingAudioUrl) URL.revokeObjectURL(pendingAudioUrl);
    setPendingAudioUrl(null);
    setPendingBlob(null);
  }, [pendingAudioUrl]);

  const applyStartResponse = useCallback(
    (res) => {
      setStatus(res.status);
      setQuestionText(res.question_text || "");
      setQuestionAudioUrl(normalizeAudioUrl(res.question_audio_url));
      if (res.status === "completed") {
        nav(`/review/${sessionId}`, { replace: true });
      }
    },
    [nav, sessionId],
  );

  const loadStart = useCallback(async () => {
    setErr("");
    setBusy(true);
    try {
      const res = await startInterview(sessionId);
      applyStartResponse(res);
    } catch (e) {
      setErr(
        e?.response?.data?.detail || e.message || "Failed to start interview.",
      );
    } finally {
      setBusy(false);
    }
  }, [sessionId, applyStartResponse]);

  useEffect(() => {
    loadStart();
  }, [loadStart]);

  // poll while waiting for next question
  useEffect(() => {
    const waiting = status === "waiting";
    const completed = status === "completed";

    // ✅ only poll if truly waiting and user isn't mid-record/preview
    if (!waiting || completed || isRecording || pendingBlob) return;

    let cancelled = false;

    const timer = setInterval(async () => {
      try {
        const res = await startInterview(sessionId);
        if (cancelled) return;
        applyStartResponse(res);
      } catch {
        // ignore transient errors while polling
      }
    }, 1200);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [status, sessionId, isRecording, pendingBlob, applyStartResponse]);

  // auto play assistant audio when it changes
  useEffect(() => {
    if (!questionAudioUrl) return;
    const el = audioRef.current;
    if (!el) return;

    el.pause();
    el.src = questionAudioUrl; // already absolute now
    el.load();
    el.play().catch(() => {});
  }, [questionAudioUrl]);

  // cleanup object url on unmount
  useEffect(() => {
    return () => {
      if (pendingAudioUrl) URL.revokeObjectURL(pendingAudioUrl);
    };
  }, [pendingAudioUrl]);

  const startRecording = async () => {
    setErr("");
    setTranscript("");
    setInterim("");

    // clear preview if starting again
    clearPending();

    if (!SpeechRecognition) {
      setErr("SpeechRecognition not supported in this browser. Use Chrome.");
      return;
    }

    setBusy(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      chunksRef.current = [];
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.start();

      const rec = new SpeechRecognition();
      recognitionRef.current = rec;
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = "en-US";

      rec.onresult = (event) => {
        let finalText = "";
        let interimText = "";
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const r = event.results[i];
          const text = r[0]?.transcript || "";
          if (r.isFinal) finalText += text;
          else interimText += text;
        }
        if (finalText) setTranscript((prev) => (prev + " " + finalText).trim());
        setInterim(interimText.trim());
      };

      rec.onerror = () => {
        // ignore recognition errors; audio recording still works
      };

      rec.start();
      setIsRecording(true);
    } catch (e) {
      setErr(e?.message || "Failed to access microphone.");
    } finally {
      setBusy(false);
    }
  };

  // Stop recording -> preview (NO submit)
  const stopRecording = async () => {
    setBusy(true);
    try {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch {
          // ignore stop errors
        }
      }

      const mr = mediaRecorderRef.current;
      if (!mr) return;

      await new Promise((resolve) => {
        mr.onstop = resolve;
        mr.stop();
      });

      if (streamRef.current) {
        for (const t of streamRef.current.getTracks()) t.stop();
        streamRef.current = null;
      }

      setIsRecording(false);

      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const finalText = (transcript || "").trim();

      if (!finalText) {
        setErr(
          "No transcript detected. Please speak clearly (Chrome) or add STT in frontend.",
        );
        return;
      }

      setPendingBlob(blob);
      const url = URL.createObjectURL(blob);
      setPendingAudioUrl(url);
      setErr("");
    } catch (e) {
      setErr(e?.message || "Failed to stop recording.");
    } finally {
      setBusy(false);
    }
  };

  const submitPending = async () => {
    if (!pendingBlob) return;

    const finalText = (transcript || "").trim();
    if (!finalText) return setErr("No transcript detected.");

    setBusy(true);
    setErr("");
    try {
      const res = await submitAnswer({
        sessionId,
        answerAudioBlob: pendingBlob,
        answerText: finalText,
      });

      setStatus(res.status);

      if (res.status === "completed") {
        clearPending();
        nav(`/review/${sessionId}`, { replace: true });
        return;
      }

      // If backend is still generating, show waiting UI (poll effect will kick in)
      setQuestionText(res.question_text || "");
      setQuestionAudioUrl(normalizeAudioUrl(res.question_audio_url));

      clearPending();
      setTranscript("");
      setInterim("");
    } catch (e) {
      setErr(
        e?.response?.data?.detail || e.message || "Failed to submit answer.",
      );
    } finally {
      setBusy(false);
    }
  };

  const rerecord = () => {
    clearPending();
    setTranscript("");
    setInterim("");
    setErr("");
    startRecording();
  };

  const endInterview = () => {
    // leaving page does NOT end interview on backend
    // disable leaving while recording to prevent weird states
    if (isRecording) return;
    nav(`/history`, { replace: true });
  };

  return (
    <div className="card">
      <h1 className="h1">Interview</h1>
      <p className="muted">
        Voice Q/A loop — record, preview, re-record, submit.
      </p>

      <div className="panel">
        <div className="panelTitle">Assistant question</div>
        <div className="question">
          {questionText
            ? questionText
            : isWaiting
              ? "Generating next question…"
              : busy
                ? "Loading..."
                : "—"}
        </div>

        <div className="row">
          <audio
            ref={audioRef}
            controls
            className="audio"
            crossOrigin="use-credentials"
          />
          {!questionAudioUrl && (
            <span className="hint">
              {isWaiting ? "Waiting for audio…" : "No audio url returned"}
            </span>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panelTitle">Your answer (voice)</div>

        <div className="row">
          {!isRecording ? (
            <button
              className="btn"
              disabled={!canRecord}
              onClick={startRecording}
            >
              {isWaiting ? "⏳ Waiting..." : "🎙 Start recording"}
            </button>
          ) : (
            <button
              className="btnDanger"
              disabled={busy}
              onClick={stopRecording}
            >
              ⏹ Stop (preview)
            </button>
          )}

          <button
            className="btnSecondary"
            disabled={busy || isRecording}
            onClick={endInterview}
          >
            Back to history
          </button>
        </div>

        <div className="transcriptBox">
          <div className="smallLabel">Transcript (auto)</div>
          <div className="transcriptText">
            {transcript || <span className="muted">…</span>}
          </div>
          {interim && <div className="interim">({interim})</div>}
        </div>

        {pendingBlob && (
          <div className="panel" style={{ marginTop: 12 }}>
            <div className="panelTitle">Preview your answer</div>
            <audio controls className="audio" src={pendingAudioUrl || ""} />
            <div className="row" style={{ marginTop: 8 }}>
              <button
                className="btnSecondary"
                disabled={busy || isWaiting}
                onClick={rerecord}
              >
                🔁 Re-record
              </button>
              <button
                className="btn"
                disabled={busy || isWaiting}
                onClick={submitPending}
              >
                ✅ Submit
              </button>
            </div>
          </div>
        )}

        {SpeechRecognition === null && (
          <div className="error">
            SpeechRecognition is not supported. Use Chrome.
          </div>
        )}
      </div>

      {err && <div className="error">{err}</div>}
    </div>
  );
}
