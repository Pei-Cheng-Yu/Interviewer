import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getReview } from "../api/interviews";

export default function ReviewPage() {
  const { sessionId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const MAX_SCORE = 10;

  const load = async () => {
    setErr("");
    setLoading(true);
    try {
      const res = await getReview(sessionId);
      setData(res?.data ?? res);
    } catch (e) {
      setErr(
        e?.response?.data?.detail || e?.message || "Failed to load review.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const gradedItems = useMemo(() => {
    return (data?.items || []).filter((x) => x?.grade_data);
  }, [data]);

  const overall = useMemo(() => {
    if (gradedItems.length === 0) return { score: null, feedback: null };

    const avg =
      gradedItems.reduce(
        (sum, it) => sum + Number(it.grade_data?.final_score ?? 0),
        0,
      ) / gradedItems.length;

    const lastFeedback =
      gradedItems[gradedItems.length - 1]?.grade_data?.feedback ?? null;

    return { score: avg, feedback: lastFeedback };
  }, [gradedItems]);

  // ONLY the number is red, "/10" stays normal color
  const ScoreOutOf10 = ({ value }) => {
    if (value === null || value === undefined || Number.isNaN(Number(value)))
      return <span>—</span>;
    const n = Number(value);

    const numStyle = n < 5 ? { color: "var(--danger)", fontWeight: 800 } : {};
    const denomStyle = { color: "var(--text)", fontWeight: 400 };

    return (
      <span>
        <span style={numStyle}>{n.toFixed(1)}</span>
        <span style={denomStyle}>/{MAX_SCORE}</span>
      </span>
    );
  };

  return (
    <div className="card">
      <h1 className="h1">Review</h1>
      <p className="muted">Score + feedback for session: {sessionId}</p>

      <div className="row">
        <button className="btnSecondary" onClick={() => nav("/history")}>
          Back to history
        </button>
        <button className="btnSecondary" disabled={loading} onClick={load}>
          Refresh
        </button>
      </div>

      {err && <div className="error">{err}</div>}

      {!data && !err && (
        <div className="muted">{loading ? "Loading..." : "No data."}</div>
      )}

      {data && (
        <>
          <div className="panel">
            <div className="panelTitle">Summary</div>
            <div className="grid2">
              <div>
                <div className="smallLabel">Overall score (avg)</div>
                <div className="big">
                  <ScoreOutOf10 value={overall.score} />
                </div>
                <div className="muted">
                  Graded: {gradedItems.length} / {(data.items || []).length}
                </div>
              </div>

              <div>
                <div className="smallLabel">Overall feedback (latest)</div>
                <div className="textBlock">{overall.feedback ?? "—"}</div>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panelTitle">Per question</div>

            {(data.items || []).map((it, idx) => {
              const g = it.grade_data;
              return (
                <div key={idx} className="qaCard">
                  <div className="smallLabel">Q{idx + 1}</div>

                  <div className="question">
                    {it.question_text || it.question_content || "—"}
                  </div>

                  <div className="smallLabel">Your answer</div>
                  <div className="textBlock">{it.user_answer_text || "—"}</div>

                  <div className="grid2">
                    <div>
                      <div className="smallLabel">Final score</div>
                      <div className="big">
                        <ScoreOutOf10 value={g?.final_score} />
                      </div>

                      <div className="muted" style={{ marginTop: 8 }}>
                        Accuracy: {g?.accuracy_score ?? "—"} · Communication:{" "}
                        {g?.communication_score ?? "—"} · Completeness:{" "}
                        {g?.completeness_score ?? "—"}
                      </div>
                    </div>

                    <div>
                      <div className="smallLabel">Feedback</div>
                      <div className="textBlock">{g?.feedback ?? "—"}</div>
                    </div>
                  </div>
                </div>
              );
            })}

            {Array.isArray(data.items) && data.items.length === 0 && (
              <div className="muted">No interactions yet.</div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
