import { useCallback, useEffect, useState } from "react";
import ConfirmModal from "../components/ConfirmModal";
import ConflictTable from "../components/ConflictTable";
import { confirmReschedule, errorMessage, syncSchedule } from "../services/api";
import { formatDate, formatDateTime } from "../services/format";
import type { RescheduleResponse, SyncResponse } from "../services/types";

const SOURCE_LABEL: Record<string, string> = {
  qldt_fallback_file: "file dự phòng qldt_fallback_response.json (mock, chưa kết nối QLĐT thật)",
  lessons_json_sample: "dữ liệu mẫu lessons.json (mock, chưa kết nối QLĐT thật)",
};
const STATUS_LABEL = { pending: "Chưa bắt đầu", in_progress: "Đang học", completed: "Đã hoàn thành" };
const RISK_LABEL = { low: "Thấp", medium: "Trung bình", high: "Cao" };

export default function DashboardPage({ onOpenWorkspace }: { onOpenWorkspace: (taskId: string) => void }) {
  const [data, setData] = useState<SyncResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [modalOpen, setModalOpen] = useState(false);
  const [syncGcal, setSyncGcal] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [result, setResult] = useState<RescheduleResponse | null>(null);

  const load = useCallback(async (forceRefresh: boolean) => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await syncSchedule(forceRefresh);
      setData(res);
      // Mặc định chọn sẵn các xung đột đã có khung giờ đề xuất
      setSelected(new Set(res.conflicts.filter((c) => c.suggested_slot).map((c) => c.task_id)));
    } catch (e) {
      setLoadError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  function toggle(taskId: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  }

  const chosen = data ? data.conflicts.filter((c) => c.suggested_slot && selected.has(c.task_id)) : [];

  // Chỉ chạy khi người dùng bấm "Đồng ý" trong modal.
  async function handleConfirm() {
    setSubmitting(true);
    setModalError(null);
    try {
      const items = chosen.map((c) => ({
        task_id: c.task_id,
        new_date: c.suggested_slot!.date,
        new_start: c.suggested_slot!.start,
        new_end: c.suggested_slot!.end,
      }));
      const res = await confirmReschedule(items, syncGcal);
      setResult(res);
      setModalOpen(false);
      await load(false);
    } catch (e) {
      setModalError(errorMessage(e)); // hiển thị nguyên lỗi từ backend (ví dụ 403)
    } finally {
      setSubmitting(false);
    }
  }

  // "Hủy": chỉ đóng modal, không gửi request nào.
  function handleCancel() {
    setModalOpen(false);
    setModalError(null);
  }

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Lịch học</h1>
          {data && (
            <p className="muted">
              Nguồn: {SOURCE_LABEL[data.source] ?? data.source}. Cập nhật lúc {formatDateTime(data.last_updated)}.
            </p>
          )}
        </div>
        <button className="btn btn-primary" onClick={() => load(true)} disabled={loading}>
          {loading ? "Đang cập nhật..." : "Cập nhật lịch"}
        </button>
      </div>

      {loadError && <p className="notice notice-error">{loadError}</p>}
      {result && (
        <div className="notice notice-info">
          <p>{result.message}</p>
          {!result.gcal_synced && result.gcal_mode !== "skipped" && (
            <p>Google Calendar: chưa đồng bộ (chỉ chạy mock).</p>
          )}
        </div>
      )}

      {data && data.conflicts.length > 0 && (
        <section className="card">
          <h2>Có {data.conflicts.length} buổi tự học trùng lịch</h2>
          <p className="muted">Đây chỉ là đề xuất. Lịch tự học chỉ đổi sau khi bạn đồng ý.</p>
          <ConflictTable conflicts={data.conflicts} selected={selected} onToggle={toggle} />
          <button
            className="btn btn-primary"
            disabled={chosen.length === 0}
            onClick={() => {
              setModalError(null);
              setModalOpen(true);
            }}
          >
            Dời lịch theo đề xuất ({chosen.length})
          </button>
        </section>
      )}
      {data && data.conflicts.length === 0 && <p className="notice notice-info">Không có buổi tự học nào trùng lịch học.</p>}

      {data && (
        <>
          <section className="card">
            <h2>Buổi tự học</h2>
            <ul className="session-list">
              {data.tasks.map((t) => (
                <li key={t.task_id} className="session">
                  <div>
                    <strong>{t.title}</strong>
                    <div className="muted">
                      {t.course_name}, {formatDate(t.date)} {t.start}–{t.end}
                    </div>
                    <div className="muted small">
                      Pomodoro {t.pomodoro_completed}/{t.pomodoro_target}
                    </div>
                  </div>
                  <div className="session-side">
                    <span className={`badge badge-${t.status}`}>{STATUS_LABEL[t.status]}</span>
                    <button className="btn" onClick={() => onOpenWorkspace(t.task_id)}>
                      Vào workspace
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section className="card">
            <h2>Nguy cơ trễ hạn</h2>
            <p className="muted">Dữ liệu dự đoán giả lập (mock) từ tasks.json.</p>
            {(data.delay_prediction.predictions ?? []).length === 0 ? (
              <p>Chưa có dự đoán.</p>
            ) : (
              <ul className="session-list">
                {(data.delay_prediction.predictions ?? []).map((p) => {
                  const task = data.tasks.find((t) => t.task_id === p.task_id);
                  return (
                    <li key={p.task_id} className="session">
                      <div>
                        <strong>{task ? task.title : p.task_id}</strong>
                        <div className="muted">{p.reason}</div>
                      </div>
                      <span className={`badge badge-risk-${p.risk_level}`}>Nguy cơ {RISK_LABEL[p.risk_level]}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="card">
            <h2>Lịch học trên lớp</h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Ngày</th>
                    <th>Giờ</th>
                    <th>Môn</th>
                    <th>Phòng</th>
                    <th>Ghi chú</th>
                  </tr>
                </thead>
                <tbody>
                  {data.lessons.map((l) => (
                    <tr key={l.key} className={l.cancelled ? "row-cancelled" : ""}>
                      <td>{formatDate(l.date)}</td>
                      <td>
                        {l.start}–{l.end}
                      </td>
                      <td>{l.course_name}</td>
                      <td>{l.room}</td>
                      <td>{[l.cancelled && "Đã hủy", l.makeup && "Học bù", l.online && "Online"].filter(Boolean).join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
      {loading && !data && <p className="muted">Đang tải lịch...</p>}

      {modalOpen && (
        <ConfirmModal title="Xác nhận dời lịch tự học" busy={submitting} onConfirm={handleConfirm} onCancel={handleCancel}>
          <p>Các buổi tự học sau sẽ được đổi giờ:</p>
          <ul>
            {chosen.map((c) => (
              <li key={c.task_id}>
                {c.task_title}: từ {formatDate(c.date)} {c.task_start}–{c.task_end} sang{" "}
                {formatDate(c.suggested_slot!.date)} {c.suggested_slot!.start}–{c.suggested_slot!.end}
              </li>
            ))}
          </ul>
          <label className="check">
            <input type="checkbox" checked={syncGcal} onChange={(e) => setSyncGcal(e.target.checked)} />
            Đồng bộ Google Calendar (hiện là mock, chưa đồng bộ thật)
          </label>
          {modalError && <p className="notice notice-error">{modalError}</p>}
        </ConfirmModal>
      )}
    </div>
  );
}
