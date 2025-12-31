import api, { API_BASE } from ".";

// --- helper: make relative -> absolute ---
const abs = (u) => {
  if (!u) return null;
  if (u.startsWith("http://") || u.startsWith("https://")) return u;
  return `${API_BASE}${u}`;
};

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

// ✅ NEW: audio stream URL builder
// Backend streaming endpoint: GET /interviews/:id/audio/:orderIndex
export function getQuestionAudioUrl(sessionId, orderIndex) {
  return `${API_BASE}/interviews/${sessionId}/audio/${orderIndex}`;
}

// ✅ NEW: convert question_audio_url from backend (relative) to absolute
export function normalizeAudioUrl(questionAudioUrl) {
  return abs(questionAudioUrl);
}

// GET /interviews
export async function listSessions() {
  const res = await api.get("/interviews");
  return res.data;
}

// GET /interviews/:id/review
export async function getReview(sessionId) {
  const res = await api.get(`/interviews/${sessionId}/review`);
  return res.data;
}
