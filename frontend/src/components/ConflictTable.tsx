import type { Conflict } from "../services/types";
import { formatDate } from "../services/format";

interface Props {
  conflicts: Conflict[];
  selected: Set<string>;
  onToggle: (taskId: string) => void;
}

export default function ConflictTable({ conflicts, selected, onToggle }: Props) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th aria-label="Chọn"></th>
            <th>Buổi tự học</th>
            <th>Giờ hiện tại</th>
            <th>Lý do</th>
            <th>Khung giờ đề xuất</th>
          </tr>
        </thead>
        <tbody>
          {conflicts.map((c) => (
            <tr key={`${c.task_id}-${c.lesson_key}`}>
              <td>
                <input
                  type="checkbox"
                  aria-label={`Chọn ${c.task_title}`}
                  checked={selected.has(c.task_id)}
                  disabled={!c.suggested_slot}
                  onChange={() => onToggle(c.task_id)}
                />
              </td>
              <td>
                <strong>{c.task_title}</strong>
                <div className="muted">{c.course_name}</div>
              </td>
              <td>
                {formatDate(c.date)}, {c.task_start}–{c.task_end}
              </td>
              <td>{c.reason}</td>
              <td>
                {c.suggested_slot ? (
                  <strong>
                    {formatDate(c.suggested_slot.date)}, {c.suggested_slot.start}–{c.suggested_slot.end}
                  </strong>
                ) : (
                  <span className="muted">Chưa có đề xuất (buổi này không linh hoạt hoặc hết giờ trống)</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
