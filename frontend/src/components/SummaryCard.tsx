import type { SummaryCardData } from "../services/types";

export default function SummaryCard({ data, onClose }: { data: SummaryCardData; onClose: () => void }) {
  return (
    <section className="card summary">
      <h2>Đã lưu buổi học</h2>
      <p className="muted">
        {data.title} ({data.course_name})
      </p>
      <dl className="stats">
        <div>
          <dt>Thời gian tập trung</dt>
          <dd>{data.total_focus_minutes} phút</dd>
        </div>
        <div>
          <dt>Pomodoro</dt>
          <dd>{data.pomodoro_result}</dd>
        </div>
        <div>
          <dt>Việc đã xong</dt>
          <dd>
            {data.completed_tasks_count}/{data.total_subtasks}
          </dd>
        </div>
        <div>
          <dt>Tỉ lệ hoàn thành</dt>
          <dd>{data.completion_rate_percent}%</dd>
        </div>
      </dl>
      <h3>Việc còn lại</h3>
      {data.remaining_subtasks.length === 0 ? (
        <p>Bạn đã hoàn thành toàn bộ checklist.</p>
      ) : (
        <ul>
          {data.remaining_subtasks.map((s) => (
            <li key={s.sub_id}>{s.content}</li>
          ))}
        </ul>
      )}
      <button className="btn btn-primary" onClick={onClose}>
        Về trang lịch học
      </button>
    </section>
  );
}
