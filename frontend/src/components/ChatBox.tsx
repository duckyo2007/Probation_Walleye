import { useState } from "react";
import { chatWithTutor, errorMessage } from "../services/api";
import type { ChatMessage } from "../services/types";

interface UiMessage extends ChatMessage {
  provider?: string;
}

export default function ChatBox({ taskId }: { taskId: string }) {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [code, setCode] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;
    const history: ChatMessage[] = messages.map((m) => ({ role: m.role, content: m.content }));
    setMessages([...messages, { role: "user", content: text }]);
    setInput("");
    setError(null);
    setSending(true);
    try {
      const res = await chatWithTutor(taskId, text, code.trim() || null, history);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply_markdown, provider: res.provider_used },
      ]);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat">
      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && <p className="muted">Hỏi gia sư AI về nội dung buổi học này.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-${m.role}`}>
            <div className="chat-text">{m.content}</div>
            {m.provider && <div className="muted small">Nguồn trả lời: {m.provider}</div>}
          </div>
        ))}
      </div>
      {error && <p className="notice notice-error">{error}</p>}
      <details>
        <summary>Đính kèm đoạn code</summary>
        <textarea
          className="input mono"
          rows={4}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="Dán đoạn code cần hỏi (không bắt buộc)"
        />
      </details>
      <div className="row">
        <input
          className="input grow"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") send();
          }}
          placeholder="Nhập câu hỏi"
        />
        <button className="btn btn-primary" onClick={send} disabled={sending || !input.trim()}>
          {sending ? "Đang gửi..." : "Gửi"}
        </button>
      </div>
    </div>
  );
}
