import { useEffect } from "react";
import type { ReactNode } from "react";

interface Props {
  title: string;
  children: ReactNode;
  busy?: boolean;
  onConfirm: () => void; // chỉ chạy khi bấm "Đồng ý"
  onCancel: () => void; // bấm "Hủy" hoặc Esc: không gửi request nào
}

export default function ConfirmModal({ title, children, busy = false, onConfirm, onCancel }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 id="modal-title">{title}</h2>
        <div className="modal-body">{children}</div>
        <div className="modal-actions">
          <button className="btn" onClick={onCancel} disabled={busy}>
            Hủy
          </button>
          <button className="btn btn-primary" onClick={onConfirm} disabled={busy}>
            {busy ? "Đang lưu..." : "Đồng ý"}
          </button>
        </div>
      </div>
    </div>
  );
}
