import { useState } from "react";
import DashboardPage from "./pages/DashboardPage";
import RoadmapPage from "./pages/RoadmapPage";
import WorkspacePage from "./pages/WorkspacePage";

// Điều hướng đơn giản bằng state (chưa cần react-router).
type View = { name: "dashboard" } | { name: "roadmap" } | { name: "workspace"; taskId: string };

export default function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });

  return (
    <>
      <header className="app-header">
        <span className="brand">EasyPlan</span>
        <nav className="nav" aria-label="Điều hướng chính">
          <button
            className={view.name === "dashboard" ? "nav-link active" : "nav-link"}
            onClick={() => setView({ name: "dashboard" })}
          >
            Lịch học
          </button>
          <button
            className={view.name === "roadmap" ? "nav-link active" : "nav-link"}
            onClick={() => setView({ name: "roadmap" })}
          >
            Tạo lộ trình
          </button>
        </nav>
      </header>
      <main className="container">
        {view.name === "dashboard" && (
          <DashboardPage onOpenWorkspace={(taskId) => setView({ name: "workspace", taskId })} />
        )}
        {view.name === "roadmap" && <RoadmapPage />}
        {view.name === "workspace" && (
          <WorkspacePage key={view.taskId} taskId={view.taskId} onBack={() => setView({ name: "dashboard" })} />
        )}
      </main>
    </>
  );
}
