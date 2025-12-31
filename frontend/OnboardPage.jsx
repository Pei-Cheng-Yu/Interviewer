import React, { useRef, useState } from "react";
import api from "./api";
import { useNavigate } from "react-router-dom";

export default function OnboardPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [jd, setJd] = useState("");
  const [resumeFile, setResumeFile] = useState(null);
  const [role, setRole] = useState("");
  const [loading, setLoading] = useState(false);

  const createSession = async () => {
    setLoading(true);
    try {
      const form = new FormData();
      form.append("raw_jd", jd);
      form.append("apply_role", role);
      if (resumeFile) form.append("resume_file", resumeFile);

      const res = await api.post("/interviews", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      navigate(`/interview/${res.data.interview_id}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Interview Onboarding</h1>

      <div style={{ marginTop: 16 }}>
        <label>Target role (optional)</label>
        <input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="e.g., Backend Intern"
        />
      </div>

      <div style={{ marginTop: 16 }}>
        <label>Job Description</label>
        <textarea
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          rows={10}
          placeholder="Paste JD here..."
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ marginTop: 16 }}>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.txt"
          style={{ display: "none" }}
          onChange={(e) => setResumeFile(e.target.files?.[0] || null)}
        />
        <button onClick={() => fileRef.current?.click()} disabled={loading}>
          Upload Resume (optional)
        </button>
        {resumeFile && (
          <span style={{ marginLeft: 12 }}>{resumeFile.name}</span>
        )}
      </div>

      <div style={{ marginTop: 24 }}>
        <button onClick={createSession} disabled={loading || !jd.trim()}>
          {loading ? "Creating..." : "Start Interview"}
        </button>
      </div>
    </div>
  );
}
