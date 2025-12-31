import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createInterview } from "../api/interviews";

export default function OnboardPage() {
  const nav = useNavigate();
  const [rawJd, setRawJd] = useState("");
  const [rawResume, setRawResume] = useState("");
  const [resumeFile, setResumeFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const handleStart = async ({ resumeLater }) => {
    setErr("");
    if (!rawJd.trim()) return setErr("JD is required.");

    setLoading(true);
    try {
      const created = await createInterview({
        rawJd: rawJd.trim(),
        rawResume: resumeLater ? "" : rawResume.trim(),
        resumeFile: resumeLater ? null : resumeFile,
      });

      nav(`/interview/${created.session_id}`, { replace: true });
    } catch (e) {
      setErr(
        e?.response?.data?.detail || e.message || "Create interview failed",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h1 className="h1">Onboard</h1>

      <div className="field">
        <label className="label">Job Description (required)</label>
        <textarea
          className="textarea"
          value={rawJd}
          onChange={(e) => setRawJd(e.target.value)}
          rows={10}
        />
      </div>

      <div className="grid2">
        <div className="field">
          <label className="label">Resume (paste, optional)</label>
          <textarea
            className="textarea"
            value={rawResume}
            onChange={(e) => setRawResume(e.target.value)}
            rows={8}
          />
        </div>

        <div className="field">
          <label className="label">Resume (upload, optional)</label>
          <input
            className="input"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => {
              const f = e.target.files?.[0] || null;
              if (!f) return setResumeFile(null);

              const isPdf =
                f.type === "application/pdf" ||
                f.name.toLowerCase().endsWith(".pdf");

              if (!isPdf) {
                setErr("Only PDF is allowed for resume upload.");
                e.target.value = ""; // reset file input
                setResumeFile(null);
                return;
              }

              setErr("");
              setResumeFile(f);
            }}
          />
          <div className="hint">PDF only.</div>
        </div>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="row">
        <button
          className="btn"
          disabled={loading}
          onClick={() => handleStart({ resumeLater: false })}
        >
          {loading ? "Starting..." : "Start interview"}
        </button>
        <button
          className="btnSecondary"
          disabled={loading}
          onClick={() => handleStart({ resumeLater: true })}
        >
          {loading ? "Starting..." : "Resume later"}
        </button>
      </div>
    </div>
  );
}
