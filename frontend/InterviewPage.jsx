import React, { useEffect, useMemo, useRef, useState } from "react";
import api from "./api";
import { useNavigate, useParams } from "react-router-dom";

function speak(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = "en-US"; // adjust
  window.speechSynthesis.speak(utter);
}

export default function InterviewPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [status, setStatus] = useState("loading"); // loading | in_progress | completed
  const [question, setQuestion] = useState("");
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);

  const SpeechRecognition = useMemo(() => {
    return window.SpeechRecognition || window.webkitSpeechRecognition;
  }, []);

  const recogRef = useRef(null);

  const loadSession = async () => {
    const res = await api.get(`/interviews/${id}`);
    if (res.data.status === "completed") {
      navigate(`/review/${id}`, { replace: true });
      return;
    }
    setStatus("in_progress");
  };

  const getFirstQuestion = async () => {
    setBusy(true);
    try {
      const res = await api.post(`/interviews/${id}/start`);
      setQuestion(res.data.question);
      speak(res.data.question);
    } finally {
      setBusy(false);
    }
  };

  const startListening = () => {
    if (!SpeechRecognition) {
      alert("SpeechRecognition not supported in this browser.");
      return;
    }
    setTranscript("");
    const r = new SpeechRecognition();
    r.lang = "en-US"; // adjust
    r.interimResults = true;
    r.continuous = true;

    r.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      setTranscript(text.trim());
    };

    r.onerror = () => setListening(false);
    r.onend = () => setListening(false);

    recogRef.current = r;
    setListening(true);
    r.start();
  };

  const stopListening = () => {
    recogRef.current?.stop();
    setListening(false);
  };

  const submitAnswer = async () => {
    if (!transcript.trim()) return;
    setBusy(true);
    try {
      const res = await api.post(`/interviews/${id}/answer`, {
        answer: transcript,
      });

      if (res.data.status === "completed") {
        navigate(`/review/${id}`, { replace: true });
        return;
      }

      setQuestion(res.data.question);
      setTranscript("");
      speak(res.data.question);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    loadSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Interview Session</h1>

      {status === "loading" ? (
        <p>Loading...</p>
      ) : (
        <>
          <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 12, marginTop: 16 }}>
            <div style={{ opacity: 0.7, marginBottom: 8 }}>Question</div>
            <div style={{ fontSize: 18, lineHeight: 1.5 }}>{question || "Press Start to begin."}</div>
          </div>

          <div style={{ marginTop: 16, display: "flex", gap: 12 }}>
            <button onClick={getFirstQuestion} disabled={busy || !!question}>
              Start
            </button>

            {!listening ? (
              <button onClick={startListening} disabled={busy || !question}>
                🎙️ Answer (Start)
              </button>
            ) : (
              <button onClick={stopListening} disabled={busy}>
                ⏹ Stop
              </button>
            )}

            <button onClick={submitAnswer} disabled={busy || !transcript.trim()}>
              Submit Answer
            </button>
          </div>

          <div style={{ marginTop: 16, padding: 16, border: "1px solid #eee", borderRadius: 12 }}>
            <div style={{ opacity: 0.7, marginBottom: 8 }}>
              Transcript {listening ? "(listening...)" : ""}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{transcript || "—"}</div>
          </div>
        </>
      )}
    </div>
  );
}
