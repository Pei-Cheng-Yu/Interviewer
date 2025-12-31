import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSessions } from "../api/interviews";

export default function HistoryPage() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setErr("");
    setLoading(true);
    try {
      const res = await listSessions();
      const data = res?.data ?? res; // axios-safe
      setItems(Array.isArray(data) ? data : data.items || []);
    } catch (e) {
      setErr(
        e?.response?.data?.detail ||
          e?.message ||
          "Failed to load sessions. (You probably need GET /interviews)",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const completedItems = useMemo(() => {
    return (items || []).filter(
      (s) => (s?.status || "").toLowerCase() === "completed",
    );
  }, [items]);

  const openReview = (s) => {
    const id = s?.id || s?.session_id;
    if (!id) return;
    nav(`/review/${id}`);
  };

  return (
    <div className="card">
      <h1 className="h1">History</h1>
      <p className="muted">Completed interview sessions.</p>

      <div className="row">
        <button
          className="btn"
          disabled={loading}
          onClick={() => nav("/onboard")}
        >
          + Start new interview
        </button>

        <button className="btnSecondary" disabled={loading} onClick={load}>
          Refresh
        </button>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="list">
        {completedItems.length === 0 && !loading && (
          <div className="muted">No completed sessions.</div>
        )}

        {completedItems.map((s) => {
          const id = s?.id || s?.session_id;
          return (
            <div
              key={id}
              className="listItem"
              onClick={() => openReview(s)}
              role="button"
              tabIndex={0}
            >
              <div className="listTitle">{id}</div>
              <div className="listMeta">
                <span className="badgeDone">completed</span>
                {s.created_at ? (
                  <span className="muted">Created: {String(s.created_at)}</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
