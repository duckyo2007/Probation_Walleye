import { useEffect, useState } from "react";

const POMODORO_SECONDS = 25 * 60;

interface Props {
  completed: number;
  target: number;
  onPomodoroDone: () => void;
}

function mmss(total: number): string {
  const m = Math.floor(total / 60).toString().padStart(2, "0");
  const s = (total % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

export default function PomodoroTimer({ completed, target, onPomodoroDone }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(POMODORO_SECONDS);
  const [running, setRunning] = useState(false);

  // Đếm ngược mỗi giây khi đang chạy
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setSecondsLeft((s) => s - 1), 1000);
    return () => window.clearInterval(id);
  }, [running]);

  // Hết giờ: tính 1 pomodoro và đặt lại đồng hồ
  useEffect(() => {
    if (secondsLeft <= 0) {
      setRunning(false);
      setSecondsLeft(POMODORO_SECONDS);
      onPomodoroDone();
    }
  }, [secondsLeft, onPomodoroDone]);

  return (
    <div className="pomodoro">
      <div className="pomodoro-time" aria-live="off">
        {mmss(secondsLeft)}
      </div>
      <p className="muted">
        Đã xong {completed}/{target} pomodoro
      </p>
      <div className="row">
        <button className="btn btn-primary" onClick={() => setRunning((r) => !r)}>
          {running ? "Tạm dừng" : "Bắt đầu"}
        </button>
        <button
          className="btn"
          onClick={() => {
            setRunning(false);
            setSecondsLeft(POMODORO_SECONDS);
          }}
        >
          Đặt lại
        </button>
        <button className="btn btn-quiet" onClick={onPomodoroDone} title="Dùng khi demo, không cần chờ 25 phút">
          Tính xong 1 pomodoro (demo)
        </button>
      </div>
    </div>
  );
}
