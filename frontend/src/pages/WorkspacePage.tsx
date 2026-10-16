import { useCallback, useEffect, useState } from "react";
import ChatBox from "../components/ChatBox";
import PomodoroTimer from "../components/PomodoroTimer";
import SummaryCard from "../components/SummaryCard";
import { checkInactivity, completeSession, enterWorkspace, errorMessage } from "../services/api";
import { formatDate } from "../services/format";
import type { InactivityResponse, Subtask, SummaryCardData, WorkspaceResponse } from "../services/types";

interface Props {
  taskId: string;
  onBack: () => void;
}

export default function WorkspacePage({ taskId, onBack }: Props) {
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [checklist, setChecklist] = useState<Subtask[]>([]);
  const [pomodoros, setPomodoros] = useState(0);
  const [notes, setNotes] = useState("");

  const [reminder, setReminder] = useState<InactivityResponse | null>(null);
  const [reminderError, setReminderError] = useState<string | null>(null);

  const [completing, setCompleting] = useState(false);
  const [completeError, setCompleteError] = useState<string | null>(null);
  const [summary, setSummary] = useState<SummaryCardData | null>(null);

  useEffect(() => {
    let cancelled = false;
    enterWorkspace(taskId)
      .then((res) => {
        if (cancelled) return;
        setWorkspace(res);
        setChecklist(res.checklist);
        setPomodoros(res.task_info.pomodoro_completed);
        setNotes(res.task_info.personal_notes);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [taskId]);

  const addPomodoro = useCallback(() => setPomodoros((n) => n + 1), []);

  function toggleSubtask(subId: string) {
    setChecklist((list) => list.map((s) => (s.sub_id === subId ? { ...s, done: !s.done } : s)));
  }

  // Nút thử nghiệm: giả lập "đã không hoạt động 10 phút"
  async function handleInactivityDemo() {
    setReminderError(null);
    const current = checklist.find((s) => !s.done)?.content ?? null;
    try {
      setReminder(await checkInactivity(taskId, 10, current));
    } catch (e) {
      setReminder(null);
      setReminderError(errorMessage(e));
    }
  }

  // Chỉ chạy khi người dùng chủ động bấm "Hoàn thành buổi học"
  async function handleComplete() {
    setCompleting(true);
    setCompleteError(null);
    try {
      const res = await completeSession({
        task_id: taskId,
        pomodoro_completed: pomodoros,
        completed_subtask_ids: checklist.filter((s) => s.done).map((s) => s.sub_id),
        personal_notes: notes,
      });
      setSummary(res.summary_card);
    } catch (e) {
      setCompleteError(errorMessage(e));
    } finally {
      setCompleting(false);
    }
  }

  if (summary) return <SummaryCard data={summary} onClose={onBack} />;

  if (error) {
    return (
      <div className="stack">
        <p className="notice notice-error">{error}</p>
        <button className="btn" onClick={onBack}>
          Quay lại
        </button>
      </div>
    );
  }
  if (!workspace) return <p className="muted">Đang mở workspace...</p>;

  const info = workspace.task_info;
  const doc = workspace.document;

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>{info.title}</h1>
          <p className="muted">
            {info.course_name}, {formatDate(info.date)} {info.start}–{info.end}
          </p>
        </div>
        <button className="btn" onClick={onBack}>
          Quay lại
        </button>
      </div>

      <p className="notice notice-warn">
        Tài liệu: {doc.message}
        {doc.slide_url && (
          <>
            {" "}
            <a href={doc.slide_url} target="_blank" rel="noreferrer">
              Mở link slide
            </a>
          </>
        )}
      </p>

      <div className="grid-2">
        <section className="card">
          <h2>Checklist</h2>
          <ul className="checklist">
            {checklist.map((s) => (
              <li key={s.sub_id}>
                <label className="check">
                  <input type="checkbox" checked={s.done} onChange={() => toggleSubtask(s.sub_id)} />
                  <span className={s.done ? "done" : ""}>{s.content}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2>Pomodoro</h2>
          <PomodoroTimer completed={pomodoros} target={info.pomodoro_target} onPomodoroDone={addPomodoro} />
        </section>
      </div>

      <section className="card">
        <h2>Ghi chú</h2>
        <textarea
          className="input"
          rows={4}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Ghi chú của bạn sẽ được lưu khi bấm Hoàn thành buổi học"
        />
      </section>

      <section className="card">
        <h2>Hỏi gia sư AI</h2>
        <ChatBox taskId={taskId} />
      </section>

      <section className="card">
        <h2>Thử nghiệm nhắc học</h2>
        <p className="muted">Giả lập trường hợp bạn đã không hoạt động 10 phút.</p>
        <button className="btn" onClick={handleInactivityDemo}>
          Thử nhắc học
        </button>
        {reminder && reminder.should_remind && <p className="notice notice-info">{reminder.message}</p>}
        {reminder && !reminder.should_remind && (
          <p className="notice notice-warn">
            Không nhắc:{" "}
            {reminder.skip_reason === "rate_limited"
              ? `vừa nhắc gần đây, thử lại sau ${reminder.retry_after_seconds ?? 0} giây.`
              : "chưa đủ 10 phút không hoạt động."}
          </p>
        )}
        {reminderError && <p className="notice notice-error">{reminderError}</p>}
      </section>

      {completeError && <p className="notice notice-error">{completeError}</p>}
      <div>
        <button className="btn btn-primary" onClick={handleComplete} disabled={completing}>
          {completing ? "Đang lưu..." : "Hoàn thành buổi học"}
        </button>
      </div>
    </div>
  );
}
