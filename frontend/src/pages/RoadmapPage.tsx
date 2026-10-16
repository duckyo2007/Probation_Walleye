import { useState } from "react";
import type { FormEvent } from "react";
import { errorMessage, generateRoadmap } from "../services/api";
import { formatDate } from "../services/format";
import type { RoadmapResponse } from "../services/types";

export default function RoadmapPage() {
  const [courseCode, setCourseCode] = useState("");
  const [courseName, setCourseName] = useState("");
  const [examDate, setExamDate] = useState("");
  const [hours, setHours] = useState("2");
  const [slideUrl, setSlideUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<RoadmapResponse | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await generateRoadmap({
        course_code: courseCode.trim(),
        course_name: courseName.trim(),
        exam_date: examDate,
        daily_free_hours: Number(hours),
        slide_url: slideUrl.trim() || null,
      });
      setDraft(res);
    } catch (err) {
      setDraft(null);
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <h1>Tạo lộ trình học</h1>
      <form className="card form" onSubmit={handleSubmit}>
        <label>
          Mã môn
          <input className="input" required value={courseCode} onChange={(e) => setCourseCode(e.target.value)} />
        </label>
        <label>
          Tên môn
          <input className="input" required value={courseName} onChange={(e) => setCourseName(e.target.value)} />
        </label>
        <label>
          Ngày thi
          <input className="input" type="date" required value={examDate} onChange={(e) => setExamDate(e.target.value)} />
        </label>
        <label>
          Số giờ rảnh mỗi ngày
          <input
            className="input"
            type="number"
            min="0.5"
            max="12"
            step="0.5"
            required
            value={hours}
            onChange={(e) => setHours(e.target.value)}
          />
        </label>
        <label>
          Link slide (không bắt buộc)
          <input className="input" value={slideUrl} onChange={(e) => setSlideUrl(e.target.value)} />
        </label>
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Đang tạo..." : "Tạo bản nháp"}
        </button>
      </form>

      {error && <p className="notice notice-error">{error}</p>}

      {draft && (
        <section className="card">
          <h2>Bản nháp lộ trình</h2>
          <p className="notice notice-warn">
            Chưa được lưu. {draft.is_mock ? "Đây là kết quả mock theo mẫu cố định. " : ""}
            {draft.note}
          </p>
          <p>{draft.summary}</p>
          <ol className="draft-list">
            {draft.suggested_sessions.map((s, i) => (
              <li key={i}>
                <strong>{s.title}</strong>
                <div className="muted">
                  {formatDate(s.date)}, {s.start}–{s.end}
                </div>
                <ul>
                  {s.subtasks.map((t) => (
                    <li key={t.sub_id}>{t.content}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
