import api from ".";

// POST /interviews
export async function createInterview({ rawJd, rawResume, resumeFile }) {
  const fd = new FormData();
  fd.append("raw_jd", rawJd);
  if (rawResume) fd.append("raw_resume", rawResume);
  if (resumeFile) fd.append("resume_file", resumeFile);

  const res = await api.post("/interviews", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

// POST /interviews/:id/start
export async function startInterview(sessionId) {
  const res = await api.post(`/interviews/${sessionId}/start`);
  return res.data;
}

// POST /interviews/:id/answer
export async function submitAnswer({ sessionId, answerAudioBlob, answerText }) {
  const fd = new FormData();
  fd.append("answer_audio", answerAudioBlob, "answer.webm");
  fd.append("answer_text", answerText);

  const res = await api.post(`/interviews/${sessionId}/answer`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

// GET /interviews (you need backend)
export async function listSessions() {
  const res = await api.get("/interviews");
  return res.data;
}

// GET /interviews/:id/review (you need backend)
export async function getReview(sessionId) {
  const res = await api.get(`/interviews/${sessionId}/review`);
  return res.data;
}
