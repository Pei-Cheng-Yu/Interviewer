import React, { useEffect, useState } from "react";
import api from "./api";
import { useParams } from "react-router-dom";

export default function ReviewPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get(`/interviews/${id}/result`).then((res) => setData(res.data));
  }, [id]);

  if (!data) return <div style={{ padding: 24 }}>Loading review...</div>;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      <h1>Interview Review</h1>
      <p>
        <b>Overall score:</b> {data.overall_score}
      </p>

      <h3>Feedback</h3>
      <div style={{ whiteSpace: "pre-wrap" }}>{data.feedback}</div>

      <h3 style={{ marginTop: 24 }}>Breakdown</h3>
      <pre>{JSON.stringify(data.breakdown, null, 2)}</pre>
    </div>
  );
}
