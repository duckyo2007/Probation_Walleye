import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  addExtraStudySession,
  checkTutorInactivity,
  completeWorkspaceSession,
  confirmReschedule,
  confirmSaveRoadmap,
  deleteRoadmaps,
  enterWorkspace,
  fetchFlashcards,
  fetchRoadmapsList,
  generateRoadmap,
  getAgentSettings,
  getStaticUrl,
  removeTaskDocument,
  sendTutorChat,
  simulateConflictDemo,
  syncSchedule,
  updateAgentSettings,
  uploadPdfDocuments,
} from './api';
import {
  AgentSettings,
  ChatMessage,
  ConflictItem,
  DelayPrediction,
  DocumentContext,
  Flashcard,
  Lesson,
  RoadmapDraftResponse,
  RoadmapItem,
  StudyTask,
  SummaryCard,
  WeekMetadata,
} from './types';

type ScreenMode = 'dashboard' | 'workspace' | 'summary';

const DAY_LABELS = [
  'Thứ 2',
  'Thứ 3',
  'Thứ 4',
  'Thứ 5',
  'Thứ 6',
  'Thứ 7',
  'Chủ nhật',
];

const COURSE_OPTIONS = [
  {
    code: 'INT1306',
    name: 'Cấu trúc dữ liệu và giải thuật',
    slides: [
      '/static/slides/INT1306_Chuong3_CayNhiPhan.pdf',
      '/static/slides/INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf',
    ],
  },
  {
    code: 'INT1359',
    name: 'Toán rời rạc 2',
    slides: ['/static/slides/INT1359_ToanRoiRac2.pdf'],
  },
  {
    code: 'ELE1309',
    name: 'Điện tử số',
    slides: ['/static/slides/ELE1309_DienTuSo.pdf'],
  },
  {
    code: 'BAS1269',
    name: 'Xác suất thống kê',
    slides: ['/static/slides/BAS1269_XacSuatThongKe.pdf'],
  },
  {
    code: 'BAS1152',
    name: 'Chủ nghĩa xã hội khoa học',
    slides: ['/static/slides/BAS1152_CNXHKH.pdf'],
  },
  {
    code: 'SKD1101',
    name: 'Kỹ năng thuyết trình',
    slides: ['/static/slides/SKD1101_KyNangThuyetTrinh.pdf'],
  },
  {
    code: 'BAS1158',
    name: 'Tiếng Anh (Course 2)',
    slides: ['/static/slides/BAS1158_TiengAnhCourse2.pdf'],
  },
];

function parseDdMmYyyyToIso(ddmmyyyy: string): string {
  const parts = ddmmyyyy.split('/');
  if (parts.length !== 3) return '2026-10-12';
  return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
}

function getWeekDates(startIso: string): string[] {
  const base = new Date(`${startIso}T00:00:00`);
  if (Number.isNaN(base.getTime())) {
    return [
      '2026-10-12',
      '2026-10-13',
      '2026-10-14',
      '2026-10-15',
      '2026-10-16',
      '2026-10-17',
      '2026-10-18',
    ];
  }
  const result: string[] = [];
  for (let i = 0; i < 7; i++) {
    const d = new Date(base);
    d.setDate(base.getDate() + i);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    result.push(`${yyyy}-${mm}-${dd}`);
  }
  return result;
}

function formatShortDate(iso: string): string {
  const parts = iso.split('-');
  if (parts.length !== 3) return iso;
  return `${parts[2]}/${parts[1]}`;
}

/**
 * Lightweight inline Markdown parser for bold (**text**) and inline code (`code`)
 */
function renderInlineMarkdown(line: string): React.ReactNode {
  const tokens = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return tokens.map((tok, idx) => {
    if (tok.startsWith('**') && tok.endsWith('**') && tok.length > 4) {
      return <strong key={idx}>{tok.slice(2, -2)}</strong>;
    }
    if (tok.startsWith('`') && tok.endsWith('`') && tok.length > 2) {
      return (
        <code
          key={idx}
          style={{
            background: 'rgba(15, 23, 42, 0.08)',
            padding: '0.1rem 0.35rem',
            borderRadius: '4px',
            fontFamily: 'monospace',
            fontSize: '0.82em',
          }}
        >
          {tok.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={idx}>{tok}</React.Fragment>;
  });
}

/**
 * Renders AI Tutor Markdown (headings, code blocks, lists, bold, inline code) cleanly
 */
function renderFormattedMarkdown(markdown: string): React.ReactNode {
  const segments = markdown.split(/(```[\s\S]*?```)/g);
  return segments.map((seg, sIdx) => {
    if (seg.startsWith('```') && seg.endsWith('```')) {
      const lines = seg.slice(3, -3).trim().split('\n');
      const firstLine = lines[0]?.trim() || '';
      const hasLang = /^[a-zA-Z0-9_+-]+$/.test(firstLine);
      const codeBody = hasLang ? lines.slice(1).join('\n') : lines.join('\n');
      return (
        <pre
          key={sIdx}
          style={{
            background: '#0f172a',
            color: '#f8fafc',
            padding: '0.75rem 0.9rem',
            borderRadius: '0.55rem',
            overflowX: 'auto',
            fontFamily: 'monospace',
            fontSize: '0.78rem',
            margin: '0.55rem 0',
            lineHeight: 1.45,
          }}
        >
          <code>{codeBody}</code>
        </pre>
      );
    }

    const lines = seg.split('\n');
    return (
      <div key={sIdx} style={{ display: 'grid', gap: '0.35rem' }}>
        {lines.map((rawLine, lIdx) => {
          const line = rawLine.trimEnd();
          if (!line.trim()) {
            return <div key={lIdx} style={{ height: '0.2rem' }} />;
          }
          if (line.startsWith('#### ')) {
            return (
              <h5
                key={lIdx}
                style={{ fontSize: '0.88rem', fontWeight: 700, marginTop: '0.35rem', color: '#1e1b4b' }}
              >
                {renderInlineMarkdown(line.slice(5))}
              </h5>
            );
          }
          if (line.startsWith('### ')) {
            return (
              <h4
                key={lIdx}
                style={{ fontSize: '0.94rem', fontWeight: 800, marginTop: '0.4rem', color: '#312e81' }}
              >
                {renderInlineMarkdown(line.slice(4))}
              </h4>
            );
          }
          if (line.startsWith('## ')) {
            return (
              <h3
                key={lIdx}
                style={{ fontSize: '1rem', fontWeight: 800, marginTop: '0.45rem', color: '#1e1b4b' }}
              >
                {renderInlineMarkdown(line.slice(3))}
              </h3>
            );
          }
          if (line.trim() === '---') {
            return (
              <hr
                key={lIdx}
                style={{ border: 'none', borderTop: '1px solid #e2e8f0', margin: '0.3rem 0' }}
              />
            );
          }
          if (/^(\*|-)\s+/.test(line.trim())) {
            const itemText = line.trim().replace(/^(\*|-)\s+/, '');
            return (
              <div
                key={lIdx}
                style={{ display: 'flex', gap: '0.45rem', paddingLeft: '0.35rem' }}
              >
                <span style={{ color: '#4f46e5', fontWeight: 700 }}>•</span>
                <div>{renderInlineMarkdown(itemText)}</div>
              </div>
            );
          }
          return <div key={lIdx}>{renderInlineMarkdown(line)}</div>;
        })}
      </div>
    );
  });
}

export function App() {
  const [screen, setScreen] = useState<ScreenMode>('dashboard');
  const [loading, setLoading] = useState<boolean>(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(
    null
  );

  // Schedule & Dashboard State
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [tasks, setTasks] = useState<StudyTask[]>([]);
  const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
  const [delayPrediction, setDelayPrediction] = useState<DelayPrediction | null>(null);
  const [syncSource, setSyncSource] = useState<'live_api' | 'fallback_cache'>('fallback_cache');
  const [lastUpdated, setLastUpdated] = useState<string>('--:--');
  const [weeksMeta, setWeeksMeta] = useState<WeekMetadata[]>([]);
  const [selectedWeek, setSelectedWeek] = useState<number>(10);
  const [liveInternetDate, setLiveInternetDate] = useState<string>('2026-10-22');
  const [liveDateSource, setLiveDateSource] = useState<string>('timeapi.io (Live Internet)');

  // Modals State
  const [showConflictModal, setShowConflictModal] = useState<boolean>(false);
  const [customRescheduleMode, setCustomRescheduleMode] = useState<boolean>(false);
  const [syncGcalChecked, setSyncGcalChecked] = useState<boolean>(true);
  const [editableConflicts, setEditableConflicts] = useState<
    Record<string, { new_date: string; new_start: string; new_end: string }>
  >({});

  // Roadmap Modal State (supports multiple PDFs)
  const [showRoadmapModal, setShowRoadmapModal] = useState<boolean>(false);
  const [rmCourseCode, setRmCourseCode] = useState<string>('INT1306');
  const [rmExamDate, setRmExamDate] = useState<string>('2026-10-25');
  const [rmDailyHours, setRmDailyHours] = useState<number>(2.0);
  const [rmSlideUrls, setRmSlideUrls] = useState<string[]>([
    '/static/slides/INT1306_Chuong3_CayNhiPhan.pdf',
    '/static/slides/INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf',
  ]);
  const [roadmapDraft, setRoadmapDraft] = useState<RoadmapDraftResponse | null>(null);

  // Roadmap List & Management Modal State
  const [showRoadmapListModal, setShowRoadmapListModal] = useState<boolean>(false);
  const [roadmapsList, setRoadmapsList] = useState<RoadmapItem[]>([]);
  const [selectedRoadmapIds, setSelectedRoadmapIds] = useState<string[]>([]);
  const [roadmapsLoading, setRoadmapsLoading] = useState<boolean>(false);

  // Settings Modal State
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [qldtUserForm, setQldtUserForm] = useState<string>('');
  const [qldtPassForm, setQldtPassForm] = useState<string>('');
  const [hocKyForm, setHocKyForm] = useState<number>(20261);
  const [autoSyncSundayForm, setAutoSyncSundayForm] = useState<boolean>(true);
  const [geminiKeyForm, setGeminiKeyForm] = useState<string>('');
  const [groqKeyForm, setGroqKeyForm] = useState<string>('');

  // Screen 03: Workspace State (with Multi-PDF Viewer)
  const [activeTask, setActiveTask] = useState<StudyTask | null>(null);
  const [activeDoc, setActiveDoc] = useState<DocumentContext | null>(null);
  const [selectedPdfUrl, setSelectedPdfUrl] = useState<string>('');
  const [leftPaneTab, setLeftPaneTab] = useState<'pdf' | 'extracted'>('pdf');
  const [rightPaneTab, setRightPaneTab] = useState<'tutor' | 'flashcards'>('tutor');
  const [checkedSubtasks, setCheckedSubtasks] = useState<Record<string, boolean>>({});
  const [personalNotes, setPersonalNotes] = useState<string>('');

  // Pomodoro Timer State (25:00)
  const [pomoSeconds, setPomoSeconds] = useState<number>(25 * 60);
  const [pomoRunning, setPomoRunning] = useState<boolean>(false);
  const [pomoCompletedCount, setPomoCompletedCount] = useState<number>(1);

  // AI Tutor Chat State
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userMessage, setUserMessage] = useState<string>('');
  const [showCodeInput, setShowCodeInput] = useState<boolean>(false);
  const [codeSnippet, setCodeSnippet] = useState<string>(
    'void preOrder(Node* root) {\n    cout << root->data;\n    preOrder(root->left);\n    preOrder(root->right);\n}'
  );
  const [tutorLoading, setTutorLoading] = useState<boolean>(false);

  // Flashcards State
  const [flashcards, setFlashcards] = useState<Flashcard[]>([]);
  const [flippedCards, setFlippedCards] = useState<Record<string, boolean>>({});

  // Screen 04: Summary Card State
  const [summaryCard, setSummaryCard] = useState<SummaryCard | null>(null);

  const workspaceFileInputRef = useRef<HTMLInputElement | null>(null);
  const roadmapFileInputRef = useRef<HTMLInputElement | null>(null);

  function showNotification(type: 'success' | 'error' | 'info', text: string) {
    setToast({ type, text });
    setTimeout(() => {
      setToast((prev) => (prev?.text === text ? null : prev));
    }, 5000);
  }

  function initEditableConflicts(conflictList: ConflictItem[]) {
    const map: Record<string, { new_date: string; new_start: string; new_end: string }> = {};
    for (const c of conflictList) {
      const parts = c.new_suggested_time.split('-').map((s) => s.trim());
      map[c.task_id] = {
        new_date: c.new_suggested_date,
        new_start: parts[0] || '19:30',
        new_end: parts[1] || '21:00',
      };
    }
    setEditableConflicts(map);
  }

  async function handleSyncSchedule(forceRefresh = true) {
    setLoading(true);
    try {
      const data = await syncSchedule({ force_refresh: forceRefresh });
      setLessons(data.lessons);
      setTasks(data.tasks);
      setConflicts(data.conflicts);
      setDelayPrediction(data.delay_prediction);
      setSyncSource(data.source);
      setLastUpdated(data.last_updated);
      if (data.today) setLiveInternetDate(data.today);
      if (data.today_source) setLiveDateSource(data.today_source);
      if (data.current_week) setSelectedWeek(data.current_week);
      if (data.weeks_metadata && data.weeks_metadata.length > 0) {
        setWeeksMeta(data.weeks_metadata);
      }
      initEditableConflicts(data.conflicts);
      if (data.conflicts.length > 0) {
        setShowConflictModal(true);
      }
      showNotification(
        'success',
        `Đã đồng bộ lịch học (${data.source === 'live_api' ? 'QLĐT Trực tiếp' : 'Dữ liệu QLĐT đã lưu'}) lúc ${data.last_updated}.`
      );
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi khi đồng bộ lịch học');
    } finally {
      setLoading(false);
    }
  }

  async function loadInitialSettings() {
    try {
      const s = await getAgentSettings();
      setSettings(s);
      setQldtUserForm(s.qldt_username || '');
      setHocKyForm(s.hoc_ky || 20261);
      setAutoSyncSundayForm(s.auto_sync_sunday);
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    handleSyncSchedule(false);
    loadInitialSettings();
  }, []);

  // Pomodoro countdown effect
  useEffect(() => {
    if (!pomoRunning) return;
    const timer = setInterval(() => {
      setPomoSeconds((prev) => {
        if (prev <= 1) {
          setPomoRunning(false);
          setPomoCompletedCount((c) => c + 1);
          showNotification('success', '🎉 Hoàn thành 1 phiên Pomodoro (25 phút tập trung)!');
          return 25 * 60;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [pomoRunning]);

  // Automatic 10-minute inactivity check in Workspace (Screen 03)
  useEffect(() => {
    if (screen !== 'workspace' || !activeTask) return;
    const timer = setTimeout(() => {
      handleTriggerInactivityCheck();
    }, 10 * 60 * 1000);
    return () => clearTimeout(timer);
  }, [screen, activeTask, userMessage, checkedSubtasks]);

  // Compute week date columns
  const currentWeekInfo = useMemo(() => {
    const found = weeksMeta.find((w) => w.week === selectedWeek);
    if (found && found.start_date) {
      const startIso = parseDdMmYyyyToIso(found.start_date);
      return {
        label: found.info || `Tuần ${selectedWeek}`,
        dates: getWeekDates(startIso),
      };
    }
    const base = new Date('2026-08-10T00:00:00');
    base.setDate(base.getDate() + (selectedWeek - 1) * 7);
    const yyyy = base.getFullYear();
    const mm = String(base.getMonth() + 1).padStart(2, '0');
    const dd = String(base.getDate()).padStart(2, '0');
    const startIso = `${yyyy}-${mm}-${dd}`;
    const dates = getWeekDates(startIso);
    return {
      label: `Tuần ${selectedWeek} (${formatShortDate(dates[0])} - ${formatShortDate(dates[6])}/2026)`,
      dates,
    };
  }, [weeksMeta, selectedWeek]);

  const conflictTaskIds = useMemo(
    () => new Set(conflicts.map((c) => c.task_id)),
    [conflicts]
  );

  // Tuần hiện tại tính theo ngày internet live
  const currentLiveWeek = useMemo(() => {
    if (!liveInternetDate) return 10;
    if (weeksMeta && weeksMeta.length > 0) {
      for (const w of weeksMeta) {
        if (w.start_date && w.end_date) {
          const s = parseDdMmYyyyToIso(w.start_date);
          const e = parseDdMmYyyyToIso(w.end_date);
          if (liveInternetDate >= s && liveInternetDate <= e) {
            return w.week;
          }
        }
      }
    }
    const semStart = new Date('2026-08-10T00:00:00');
    const today = new Date(`${liveInternetDate}T00:00:00`);
    const diffDays = Math.floor((today.getTime() - semStart.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays >= 0) {
      return Math.min(31, Math.floor(diffDays / 7) + 1);
    }
    return 10;
  }, [liveInternetDate, weeksMeta]);

  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => (a.date + a.start).localeCompare(b.date + b.start)),
    [tasks]
  );

  // Buổi tự học sắp tới / hiện tại: chưa xong và từ hôm nay trở đi
  const upcomingTasks = useMemo(
    () => sortedTasks.filter((t) => t.status !== 'done' && t.date >= liveInternetDate),
    [sortedTasks, liveInternetDate]
  );

  // Buổi bị bỏ lỡ: chưa hoàn thành mà đã qua ngày => chậm tiến độ
  const overdueTasks = useMemo(
    () => sortedTasks.filter((t) => t.status !== 'done' && t.date < liveInternetDate),
    [sortedTasks, liveInternetDate]
  );

  const [showAllTasks, setShowAllTasks] = useState<boolean>(false);

  const nextTodoTask = useMemo(
    () => upcomingTasks[0] || overdueTasks[0] || null,
    [upcomingTasks, overdueTasks]
  );

  const weeklyProgress = useMemo(() => {
    const weekTasks = tasks.filter((t) => t.week === selectedWeek);
    const pool = weekTasks.length > 0 ? weekTasks : tasks;
    if (pool.length === 0) return { done: 0, total: 0, percent: 0 };
    const done = pool.filter((t) => t.status === 'done').length;
    return {
      done,
      total: pool.length,
      percent: Math.round((done / pool.length) * 100),
    };
  }, [tasks, selectedWeek]);

  // List of PDF documents in current workspace session
  const sessionDocuments = useMemo(() => {
    if (activeDoc?.documents && activeDoc.documents.length > 0) {
      return activeDoc.documents;
    }
    if (activeDoc?.slide_url) {
      return [
        {
          slide_url: activeDoc.slide_url,
          filename: activeDoc.slide_url.split('/').pop() || 'slide.pdf',
          context_loaded: activeDoc.context_loaded,
          page_count: activeDoc.page_count,
          document_status: activeDoc.document_status,
          extracted_text: activeDoc.extracted_text,
        },
      ];
    }
    return [];
  }, [activeDoc]);

  // Handlers for Screen 02: Confirm Reschedule (Hard Confirmation Gate)
  async function handleConfirmReschedule() {
    if (conflicts.length === 0) return;
    setLoading(true);
    try {
      const items = conflicts.map((c) => {
        const edited = editableConflicts[c.task_id];
        const parts = c.new_suggested_time.split('-').map((s) => s.trim());
        return {
          task_id: c.task_id,
          new_date: edited?.new_date || c.new_suggested_date,
          new_start: edited?.new_start || parts[0] || '19:30',
          new_end: edited?.new_end || parts[1] || '21:00',
        };
      });

      const res = await confirmReschedule({
        user_confirmed: true,
        sync_gcal: syncGcalChecked,
        reschedule_items: items,
      });

      showNotification('success', res.message);
      setShowConflictModal(false);
      setCustomRescheduleMode(false);
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Không thể dời lịch');
    } finally {
      setLoading(false);
    }
  }

  // Handler for Simulate Conflict Demo
  async function handleSimulateConflict() {
    setLoading(true);
    try {
      const res = await simulateConflictDemo();
      setLessons(res.lessons);
      setTasks(res.tasks);
      setConflicts(res.conflicts);
      setSelectedWeek(10);
      initEditableConflicts(res.conflicts);
      setShowConflictModal(true);
      showNotification('info', res.message);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi tạo xung đột mẫu');
    } finally {
      setLoading(false);
    }
  }

  // Handlers for Roadmap Generation & Confirmation Gate (API 3 & 3.1)
  async function handleGenerateRoadmap(e: React.FormEvent) {
    e.preventDefault();
    const courseObj =
      COURSE_OPTIONS.find((c) => c.code === rmCourseCode) || COURSE_OPTIONS[0];
    const effectiveUrls = rmSlideUrls.length > 0 ? rmSlideUrls : courseObj.slides;
    setLoading(true);
    try {
      const todayIso = liveInternetDate;
      const weekStartIso = currentWeekInfo?.dates?.[0] || todayIso;
      // Không bao giờ xếp lịch tự học ở các ngày trong quá khứ trước hôm nay (lấy từ Internet time API)
      const effectiveBaseDate = weekStartIso < todayIso ? todayIso : weekStartIso;

      const draft = await generateRoadmap({
        course_code: courseObj.code,
        course_name: courseObj.name,
        exam_date: rmExamDate,
        daily_free_hours: rmDailyHours,
        slide_url: effectiveUrls[0],
        slide_urls: effectiveUrls,
        base_date: effectiveBaseDate,
      });
      setRoadmapDraft(draft);
      showNotification(
        'info',
        `Đã phân tích ${effectiveUrls.length} file PDF & tạo lộ trình nháp. Vui lòng duyệt trước khi lưu!`
      );
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi khi tạo lộ trình');
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirmSaveRoadmap() {
    if (!roadmapDraft) return;
    const courseObj =
      COURSE_OPTIONS.find((c) => c.code === roadmapDraft.course_code) || COURSE_OPTIONS[0];
    const effectiveUrls = rmSlideUrls.length > 0 ? rmSlideUrls : courseObj.slides;
    setLoading(true);
    try {
      const res = await confirmSaveRoadmap({
        user_confirmed: true,
        course_code: roadmapDraft.course_code,
        course_name: courseObj.name,
        slide_url: effectiveUrls[0],
        slide_urls: effectiveUrls,
        approved_sessions: roadmapDraft.suggested_sessions.map((s) => ({
          title: s.title,
          date: s.suggested_date,
          start: s.suggested_start,
          end: s.suggested_end,
          is_flexible: true,
          slide_url: effectiveUrls[0],
          slide_urls: effectiveUrls,
          subtasks: s.subtasks,
        })),
      });
      showNotification('success', res.message);
      setRoadmapDraft(null);
      setShowRoadmapModal(false);
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi khi lưu lộ trình');
    } finally {
      setLoading(false);
    }
  }

  // Handlers for Roadmap List & Batch Delete
  async function handleOpenRoadmapListModal() {
    setRoadmapsLoading(true);
    setShowRoadmapListModal(true);
    try {
      const data = await fetchRoadmapsList();
      setRoadmapsList(data.roadmaps || []);
      setSelectedRoadmapIds([]);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi khi tải danh sách lộ trình');
    } finally {
      setRoadmapsLoading(false);
    }
  }

  function handleToggleSelectRoadmap(id: string) {
    setSelectedRoadmapIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function handleToggleSelectAllRoadmaps() {
    if (selectedRoadmapIds.length === roadmapsList.length) {
      setSelectedRoadmapIds([]);
    } else {
      setSelectedRoadmapIds(roadmapsList.map((r) => r.roadmap_id));
    }
  }

  async function handleDeleteRoadmaps(idsToDelete: string[]) {
    if (idsToDelete.length === 0) return;
    const count = idsToDelete.length;
    const confirmed = window.confirm(
      `Xác nhận xóa: Bạn có chắc chắn muốn xóa ${count} lộ trình tự học đã chọn không?\nToàn bộ các buổi tự học thuộc các lộ trình này sẽ được xóa khỏi thời khóa biểu.`
    );
    if (!confirmed) return;

    setRoadmapsLoading(true);
    try {
      const res = await deleteRoadmaps({ roadmap_ids: idsToDelete });
      showNotification('success', res.message || `Đã xóa ${res.deleted_count} buổi tự học.`);
      const refreshed = await fetchRoadmapsList();
      setRoadmapsList(refreshed.roadmaps || []);
      setSelectedRoadmapIds([]);
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi khi xóa lộ trình');
    } finally {
      setRoadmapsLoading(false);
    }
  }

  // Handler for Delay Prediction Widget Action (with Confirmation Gate)
  async function handleAddExtraSessionFromWidget() {
    const confirmed = window.confirm(
      `Xác nhận (Confirmation Gate): Bạn có đồng ý để Agent xếp 1 buổi học bù ${
        delayPrediction?.suggested_date || liveInternetDate
      } (${delayPrediction?.suggested_start || '19:30'} - ${
        delayPrediction?.suggested_end || '21:00'
      }) cho các buổi bị chậm tiến độ vào lịch cá nhân không?`
    );
    if (!confirmed) return;
    setLoading(true);
    try {
      const res = await addExtraStudySession({
        user_confirmed: true,
        course_code: delayPrediction?.course_code || 'INT1306',
        course_name: 'Cấu trúc dữ liệu và giải thuật',
        title: 'Học bù tăng cường: Hoàn thành Bài tập lớn (Chống trễ hạn)',
        date: delayPrediction?.suggested_date || liveInternetDate,
        start: delayPrediction?.suggested_start || '19:30',
        end: delayPrediction?.suggested_end || '21:00',
        slide_url: '/static/slides/INT1306_Chuong3_CayNhiPhan.pdf',
        slide_urls: [
          '/static/slides/INT1306_Chuong3_CayNhiPhan.pdf',
          '/static/slides/INT1306_BaiTap_ThucHanh_CayNhiPhan.pdf',
        ],
      });
      showNotification('success', res.message);
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message);
    } finally {
      setLoading(false);
    }
  }

  // Handler for Enter Workspace (API 4 - 1-Click Entry)
  async function handleEnterWorkspace(taskId: string) {
    setLoading(true);
    try {
      const res = await enterWorkspace(taskId);
      setActiveTask(res.task_info);
      setActiveDoc(res.document);
      const firstPdf =
        res.document.documents?.[0]?.slide_url ||
        res.document.slide_url ||
        res.task_info.slide_url;
      setSelectedPdfUrl(firstPdf);

      const subMap: Record<string, boolean> = {};
      for (const s of res.task_info.subtasks || []) {
        subMap[s.sub_id] = Boolean(s.done);
      }
      setCheckedSubtasks(subMap);
      setPersonalNotes(res.task_info.personal_notes || '');
      setPomoSeconds(25 * 60);
      setPomoRunning(false);
      setPomoCompletedCount(Math.max(1, res.task_info.pomodoro_Completed || 1));

      const docCount = res.document.documents?.length || 1;
      setChatHistory([
        {
          role: 'assistant',
          content: `Chào bạn! Mình đã đọc xong **${docCount} tài liệu PDF** (tổng cộng **${res.document.page_count} trang**, trạng thái: \`${res.document.document_status}\`) của môn **${res.task_info.course_name}**.\n\nHôm nay chúng ta sẽ hoàn thành phiên **"${res.task_info.title}"**. Bạn có thể chuyển đổi qua lại giữa các file PDF ở khung bên trái hoặc hỏi mình bất kỳ câu hỏi lý thuyết / debug code nào nhé!`,
          provider: 'gemini-3.8-flash',
        },
      ]);
      const fcRes = await fetchFlashcards(taskId).catch(() => ({ flashcards: [] }));
      setFlashcards(fcRes.flashcards || []);
      setFlippedCards({});
      setScreen('workspace');
    } catch (err: any) {
      showNotification('error', err.message || 'Không thể mở không gian học tập');
    } finally {
      setLoading(false);
    }
  }

  // Handler for Tutor Chat (API 5)
  async function handleSendTutorMessage(customQuestion?: string) {
    if (!activeTask) return;
    const msgText = (customQuestion ?? userMessage).trim();
    if (!msgText) return;

    const updatedHistory: ChatMessage[] = [
      ...chatHistory,
      {
        role: 'user',
        content:
          showCodeInput && codeSnippet.trim()
            ? `${msgText}\n\n\`\`\`cpp\n${codeSnippet}\n\`\`\``
            : msgText,
      },
    ];
    setChatHistory(updatedHistory);
    if (!customQuestion) setUserMessage('');
    setTutorLoading(true);

    try {
      const res = await sendTutorChat({
        task_id: activeTask.task_id,
        user_message: msgText,
        code_snippet: showCodeInput ? codeSnippet : '',
        chat_history: chatHistory.map((m) => ({ role: m.role, content: m.content })),
      });
      setChatHistory((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply_markdown,
          provider: res.provider_used,
        },
      ]);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi kết nối AI Trợ giảng');
    } finally {
      setTutorLoading(false);
    }
  }

  // Handler for Inactivity Check (API 6)
  async function handleTriggerInactivityCheck() {
    if (!activeTask) return;
    const currentSub =
      activeTask.subtasks.find((s) => !checkedSubtasks[s.sub_id])?.content ||
      activeTask.subtasks[0]?.content ||
      'Đọc lý thuyết và làm bài tập vận dụng';

    try {
      const res = await checkTutorInactivity({
        task_id: activeTask.task_id,
        inactive_minutes: 10,
        current_subtask: currentSub,
      });
      if (res.should_remind && res.message) {
        setChatHistory((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `🔔 **[Nhắc nhở chủ động sau 10 phút không thao tác]**\n${res.message}`,
            provider: 'proactive-trigger',
            isProactive: true,
          },
        ]);
        showNotification('info', 'AI Trợ giảng vừa gửi gợi ý hỗ trợ chủ động!');
      } else if (res.skip_reason === 'rate_limited') {
        showNotification(
          'info',
          `Chống spam (Cooldown 300s): Đã nhắc gần đây, vui lòng thử lại sau ${res.retry_after_seconds} giây.`
        );
      }
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi kiểm tra trạng thái');
    }
  }

  // Handler for Multi-PDF Upload inside Workspace (appends to current session)
  async function handleWorkspacePdfUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0 || !activeTask) return;
    setLoading(true);
    try {
      const res = await uploadPdfDocuments(files, activeTask.task_id, true);
      setActiveTask({
        ...activeTask,
        slide_url: res.slide_url,
        slide_urls: res.slide_urls,
      });
      setActiveDoc(res.document);
      setSelectedPdfUrl(res.slide_url);
      showNotification(
        'success',
        `Đã thêm ${res.filenames.length} file PDF (${res.filename}) vào buổi học! Tổng cộng: ${res.document.documents?.length || 1} file (${res.document.page_count} trang).`
      );
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi tải file PDF');
    } finally {
      setLoading(false);
      if (workspaceFileInputRef.current) workspaceFileInputRef.current.value = '';
    }
  }

  // Handler for Removing a PDF from current Workspace session
  async function handleRemovePdfFromSession(slideUrlToRemove: string) {
    if (!activeTask) return;
    setLoading(true);
    try {
      const res = await removeTaskDocument(activeTask.task_id, slideUrlToRemove);
      setActiveTask(res.task_info);
      setActiveDoc(res.document);
      if (selectedPdfUrl === slideUrlToRemove) {
        setSelectedPdfUrl(res.document.slide_url);
      }
      showNotification('info', 'Đã gỡ tài liệu PDF khỏi buổi học.');
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Không thể gỡ file PDF');
    } finally {
      setLoading(false);
    }
  }

  // Handler for Multi-PDF Upload inside Roadmap Modal
  async function handleRoadmapPdfUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setLoading(true);
    try {
      const res = await uploadPdfDocuments(files, undefined, true);
      setRmSlideUrls((prev) => {
        const merged = [...prev];
        for (const u of res.uploaded_urls) {
          if (!merged.includes(u)) merged.push(u);
        }
        return merged;
      });
      showNotification(
        'success',
        `Đã tải lên ${res.filenames.length} file PDF (${res.filename}) cho lộ trình học!`
      );
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi tải file PDF');
    } finally {
      setLoading(false);
      if (roadmapFileInputRef.current) roadmapFileInputRef.current.value = '';
    }
  }

  // Handler for Complete Workspace Session (API 7 -> Screen 04)
  async function handleCompleteSession() {
    if (!activeTask) return;
    setLoading(true);
    try {
      const completedIds = Object.entries(checkedSubtasks)
        .filter(([, done]) => done)
        .map(([id]) => id);
      const res = await completeWorkspaceSession({
        task_id: activeTask.task_id,
        pomodoro_completed: pomoCompletedCount,
        completed_subtask_ids: completedIds,
        personal_notes: personalNotes,
      });
      setSummaryCard(res.summary_card);
      setPomoRunning(false);
      setScreen('summary');
      await handleSyncSchedule(false);
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi lưu kết quả buổi học');
    } finally {
      setLoading(false);
    }
  }

  // Handler for Saving QLĐT Credentials & Settings
  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await updateAgentSettings({
        qldt_username: qldtUserForm,
        qldt_password: qldtPassForm || undefined,
        hoc_ky: hocKyForm,
        auto_sync_sunday: autoSyncSundayForm,
        gemini_api_key: geminiKeyForm || undefined,
        groq_api_key: groqKeyForm || undefined,
      });
      setSettings(res);
      setQldtPassForm('');
      setGeminiKeyForm('');
      setGroqKeyForm('');
      setShowSettingsModal(false);
      showNotification('success', res.message);
      if (qldtUserForm && qldtPassForm) {
        await handleSyncSchedule(true);
      }
    } catch (err: any) {
      showNotification('error', err.message || 'Lỗi lưu cấu hình');
    } finally {
      setLoading(false);
    }
  }

  const formatTimer = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  return (
    <div>
      {/* Toast Notification */}
      {toast && (
        <div
          style={{
            position: 'fixed',
            bottom: '1.25rem',
            right: '1.25rem',
            zIndex: 200,
            background:
              toast.type === 'error'
                ? '#dc2626'
                : toast.type === 'success'
                ? '#059669'
                : '#4f46e5',
            color: '#fff',
            padding: '0.8rem 1.2rem',
            borderRadius: '0.65rem',
            boxShadow: '0 10px 25px rgba(0,0,0,0.2)',
            fontWeight: 600,
            fontSize: '0.86rem',
            maxWidth: '440px',
          }}
        >
          {toast.text}
        </div>
      )}

      {/* Hidden File Inputs for Multi-PDF Upload */}
      <input
        ref={workspaceFileInputRef}
        type="file"
        multiple
        accept=".pdf,application/pdf"
        style={{ display: 'none' }}
        onChange={handleWorkspacePdfUpload}
      />
      <input
        ref={roadmapFileInputRef}
        type="file"
        multiple
        accept=".pdf,application/pdf"
        style={{ display: 'none' }}
        onChange={handleRoadmapPdfUpload}
      />

      {/* =====================================================================
          SCREEN 01: UNIFIED DASHBOARD & WEEKLY SCHEDULE
         ===================================================================== */}
      {screen === 'dashboard' && (
        <>
          <header className="top-navbar">
            <div className="brand-group">
              <div className="brand-logo">
                <span>🎓 EasyPlan AI</span>
                <span className="brand-badge">PTIT QLĐT Sync</span>
              </div>
            </div>

            <div className="nav-actions">
              <span style={{ fontSize: '0.78rem', opacity: 0.9 }}>
                Nguồn:{' '}
                <strong>
                  {syncSource === 'live_api' ? '🟢 Live QLĐT API' : '📦 Cache tkb_ptit'}
                </strong>{' '}
                ({lastUpdated})
              </span>

              <button
                className="btn btn-white"
                onClick={() => handleSyncSchedule(true)}
                disabled={loading}
              >
                🔄 {loading ? 'Đang đồng bộ...' : 'Đồng bộ lịch QLĐT'}
              </button>

              <button
                className="btn btn-glass"
                onClick={handleOpenRoadmapListModal}
                title="Xem và quản lý các lộ trình học hiện có, xóa lộ trình không dùng"
              >
                🗺️ Quản lý lộ trình
              </button>

              <button
                className="btn btn-glass"
                onClick={() => {
                  setRoadmapDraft(null);
                  setShowRoadmapModal(true);
                }}
              >
                ✨ Tạo lộ trình AI (Nhiều PDF)
              </button>

              <button
                className="btn btn-glass"
                onClick={handleSimulateConflict}
                disabled={loading}
                title="Khôi phục xung đột lịch học mẫu tại Tuần 10 để kiểm thử Confirmation Gate"
              >
                ⚠️ Tạo xung đột mẫu
              </button>

              <button
                className="btn btn-glass"
                onClick={() => setShowSettingsModal(true)}
              >
                ⚙️ Tài khoản QLĐT & API Key
              </button>
            </div>
          </header>

          <main className="main-container">
            {/* 1-Click Enter Banner (Figma Screen 01) */}
            {nextTodoTask && (
              <div className="one-click-banner">
                <div className="banner-left">
                  <div className="pulse-dot" />
                  <div>
                    <div className="banner-title">
                      🚀 Đến phiên tự học: {nextTodoTask.title} ({nextTodoTask.course_code})
                    </div>
                    <div className="banner-sub">
                      Lịch dự kiến: {nextTodoTask.date} | {nextTodoTask.start} - {nextTodoTask.end}{' '}
                      • Đính kèm{' '}
                      <strong>
                        {nextTodoTask.slide_urls?.length || 1} tài liệu PDF
                      </strong>{' '}
                      & AI Trợ giảng Gemini 3.8 Flash sẵn sàng
                    </div>
                  </div>
                </div>
                <button
                  className="btn btn-emerald"
                  style={{ padding: '0.65rem 1.25rem', fontSize: '0.92rem' }}
                  onClick={() => handleEnterWorkspace(nextTodoTask.task_id)}
                >
                  VÀO TỰ HỌC NGAY →
                </button>
              </div>
            )}

            {/* Conflict Alert Strip if conflicts exist */}
            {conflicts.length > 0 && (
              <div className="conflict-strip">
                <div>
                  <strong style={{ color: '#991b1b', fontSize: '0.95rem' }}>
                    ⚠️ Phát hiện {conflicts.length} xung đột giữa Lịch học cố định trên trường (QLĐT) và Lịch tự học!
                  </strong>
                  <div style={{ fontSize: '0.83rem', color: '#b91c1c' }}>
                    Agent đã tính toán khung giờ trống thay thế ({conflicts[0].new_suggested_time} ngày{' '}
                    {conflicts[0].new_suggested_date}) và đang chờ bạn xác nhận (Confirmation Gate).
                  </div>
                </div>
                <button
                  className="btn btn-danger"
                  onClick={() => setShowConflictModal(true)}
                >
                  Xem & Xử lý Xung đột ({conflicts.length})
                </button>
              </div>
            )}

            <div className="dashboard-layout">
              {/* Left Column: Weekly Schedule Grid */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">
                      📅 Thời khóa biểu Tuần {selectedWeek} — Kết hợp Lịch Trường (QLĐT) & Lịch Tự Học AI
                    </div>
                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                      Nhấn vào bất kỳ thẻ Tự học màu xanh lá nào để vào thẳng phòng học 1-Click
                    </div>
                  </div>

                  <div className="calendar-legend">
                    <span className="legend-item">
                      <span
                        className="legend-dot"
                        style={{ background: '#eff6ff', border: '2px solid #1d4ed8' }}
                      />
                      Lịch học cố định (QLĐT)
                    </span>
                    <span className="legend-item">
                      <span
                        className="legend-dot"
                        style={{ background: '#ecfdf5', border: '2px solid #059669' }}
                      />
                      Phiên tự học AI (Linh hoạt)
                    </span>
                    <span className="legend-item">
                      <span
                        className="legend-dot"
                        style={{ background: '#fef2f2', border: '2px dashed #dc2626' }}
                      />
                      Xung đột chờ duyệt
                    </span>
                  </div>
                </div>

                {/* THANH CHUYỂN TUẦN NGAY TRÊN BẢNG LỊCH */}
                <div className="schedule-toolbar">
                  <div className="schedule-week-controls">
                    <button
                      className="btn btn-outline"
                      style={{ padding: '0.35rem 0.7rem', fontSize: '0.84rem' }}
                      onClick={() => setSelectedWeek((w) => Math.max(1, w - 1))}
                      title="Chuyển sang tuần trước"
                    >
                      ◀ Tuần trước
                    </button>

                    <div className="schedule-week-picker">
                      <span style={{ fontSize: '1rem' }}>🗓️</span>
                      <select
                        className="schedule-week-select"
                        value={selectedWeek}
                        onChange={(e) => setSelectedWeek(Number(e.target.value))}
                      >
                        {(weeksMeta.length > 0
                          ? weeksMeta
                          : Array.from({ length: 25 }, (_, idx) => ({
                              week: idx + 1,
                              info: `Tuần ${idx + 1}`,
                              start_date: '',
                              end_date: '',
                              lesson_count: 0,
                            }))
                        ).map((w) => (
                          <option key={w.week} value={w.week}>
                            {w.info || `Tuần ${w.week}`}
                          </option>
                        ))}
                      </select>
                    </div>

                    <button
                      className="btn btn-outline"
                      style={{ padding: '0.35rem 0.7rem', fontSize: '0.84rem' }}
                      onClick={() => setSelectedWeek((w) => Math.min(31, w + 1))}
                      title="Chuyển sang tuần kế tiếp"
                    >
                      Tuần sau ▶
                    </button>

                    {selectedWeek !== currentLiveWeek && (
                      <button
                        className="btn btn-glass"
                        style={{
                          padding: '0.3rem 0.65rem',
                          fontSize: '0.78rem',
                          color: 'var(--primary-700)',
                          borderColor: 'var(--primary-200)',
                          background: 'var(--primary-50)',
                          fontWeight: 600,
                        }}
                        onClick={() => setSelectedWeek(currentLiveWeek)}
                        title="Quay lại tuần học hiện tại"
                      >
                        🎯 Về tuần hiện tại (Tuần {currentLiveWeek})
                      </button>
                    )}
                  </div>

                  <div className="schedule-week-stats">
                    <span>
                      📅 Khoảng thời gian: <strong>{formatShortDate(currentWeekInfo.dates[0])}</strong> đến{' '}
                      <strong>{formatShortDate(currentWeekInfo.dates[6])}</strong>
                    </span>
                    <span
                      style={{
                        marginLeft: '0.75rem',
                        padding: '0.2rem 0.55rem',
                        borderRadius: '6px',
                        background: '#eff6ff',
                        color: '#1d4ed8',
                        fontSize: '0.78rem',
                        fontWeight: 600,
                        border: '1px solid #bfdbfe',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                      }}
                      title={`Nguồn ngày giờ: ${liveDateSource}`}
                    >
                      🌐 Hôm nay: <strong>{liveInternetDate}</strong>
                    </span>
                  </div>
                </div>

                <div className="week-columns">
                  {currentWeekInfo.dates.map((isoDate, dayIdx) => {
                    const dayLessons = lessons.filter(
                      (l) => l.date === isoDate && !l.cancelled
                    );
                    const dayTasks = tasks
                      .filter((t) => t.date === isoDate)
                      .sort((a, b) => a.start.localeCompare(b.start));
                    const isToday = isoDate === liveInternetDate;

                    return (
                      <div key={isoDate} className="day-col">
                        <div className={`day-col-header ${isToday ? 'today' : ''}`}>
                          <div className="day-name">{DAY_LABELS[dayIdx]}</div>
                          <div className="day-date">{formatShortDate(isoDate)}</div>
                        </div>

                        <div className="day-events">
                          {dayLessons.map((les) => (
                            <div key={les.key} className="event-card event-lesson">
                              <div className="event-time">
                                <span>
                                  🏫 {les.start} - {les.end}
                                </span>
                                {les.makeup && (
                                  <span
                                    style={{
                                      background: '#dbeafe',
                                      color: '#1e40af',
                                      padding: '0 4px',
                                      borderRadius: '4px',
                                      fontSize: '0.65rem',
                                    }}
                                  >
                                    Học bù
                                  </span>
                                )}
                              </div>
                              <div className="event-title">
                                {les.course_name} ({les.course_code})
                              </div>
                              <div className="event-meta">📍 {les.room}</div>
                              <div className="event-meta">👨‍🏫 {les.teacher}</div>
                            </div>
                          ))}

                          {dayTasks.map((tsk) => {
                            const isConflicting = conflictTaskIds.has(tsk.task_id);
                            const pdfCount = tsk.slide_urls?.length || 1;
                            return (
                              <div
                                key={tsk.task_id}
                                className={`event-card ${
                                  isConflicting
                                    ? 'event-conflict'
                                    : `event-task ${tsk.status === 'done' ? 'done' : ''}`
                                }`}
                                onClick={() => {
                                  if (isConflicting) {
                                    setShowConflictModal(true);
                                  } else {
                                    handleEnterWorkspace(tsk.task_id);
                                  }
                                }}
                              >
                                <div className="event-time">
                                  <span>
                                    {isConflicting ? '⚠️' : tsk.status === 'done' ? '✅' : '📗'}{' '}
                                    {tsk.start} - {tsk.end}
                                  </span>
                                  <span>📚 {pdfCount} PDF</span>
                                </div>
                                <div className="event-title">{tsk.title}</div>
                                <div className="event-meta">
                                  Môn: {tsk.course_name} ({tsk.course_code})
                                </div>
                                {isConflicting && (
                                  <div
                                    style={{
                                      marginTop: '0.3rem',
                                      fontWeight: 700,
                                      color: '#dc2626',
                                      fontSize: '0.7rem',
                                    }}
                                  >
                                    👉 Nhấn để duyệt dời lịch
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {dayLessons.length === 0 && dayTasks.length === 0 && (
                            <div
                              style={{
                                fontSize: '0.73rem',
                                color: '#94a3b8',
                                textAlign: 'center',
                                marginTop: '1.5rem',
                              }}
                            >
                              Trống lịch
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Sidebar: Internal To-Do List, Delay Prediction Mock Widget, Weekly Progress */}
              <div className="sidebar-stack">
                {/* Widget 1: Việc cần tự học (Internal To-Do List) */}
                <div className="card">
                  <div className="card-header">
                    <span className="card-title">📝 Việc cần tự học ({upcomingTasks.length})</span>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                      <button
                        className="btn btn-outline"
                        style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                        onClick={handleOpenRoadmapListModal}
                        title="Xem và quản lý các lộ trình học hiện tại"
                      >
                        🗺️ Quản lý lộ trình
                      </button>
                      <button
                        className="btn btn-primary"
                        style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                        onClick={() => {
                          setRoadmapDraft(null);
                          setShowRoadmapModal(true);
                        }}
                      >
                        + Thêm lộ trình
                      </button>
                    </div>
                  </div>
                  <div style={{ padding: '0.9rem 1.1rem' }}>
                    {overdueTasks.length > 0 && (
                      <div
                        style={{
                          marginBottom: '0.6rem',
                          padding: '0.4rem 0.6rem',
                          background: '#fee2e2',
                          color: '#991b1b',
                          borderRadius: '6px',
                          fontSize: '0.76rem',
                          fontWeight: 600,
                        }}
                      >
                        ⏰ {overdueTasks.length} buổi tự học chậm tiến độ (đã qua ngày chưa hoàn thành)
                        {delayPrediction?.suggested_action && !delayPrediction.is_resolved
                          ? ' — xem đề xuất học bù bên dưới.'
                          : '.'}
                      </div>
                    )}
                    {tasks.length === 0 && (
                      <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                        Chưa có buổi tự học nào. Nhấn “+ Thêm lộ trình” để AI chia lịch tự học từ tài liệu PDF.
                      </div>
                    )}
                    {tasks.length > 0 && !showAllTasks && upcomingTasks.length === 0 && (
                      <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                        Không có buổi tự học sắp tới.
                      </div>
                    )}
                    {(showAllTasks ? sortedTasks : upcomingTasks.slice(0, 3)).map((t) => {
                      const isOverdue = t.status !== 'done' && t.date < liveInternetDate;
                      const doneSubs = (t.subtasks || []).filter((s) => s.done).length;
                      const totalSubs = (t.subtasks || []).length;
                      const isConf = conflictTaskIds.has(t.task_id);
                      const pdfCount = t.slide_urls?.length || 1;
                      return (
                        <div key={t.task_id} className="todo-list-item">
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              gap: '0.4rem',
                            }}
                          >
                            <span
                              style={{
                                fontSize: '0.72rem',
                                fontWeight: 700,
                                padding: '0.1rem 0.45rem',
                                borderRadius: '4px',
                                background: isConf || isOverdue
                                  ? '#fee2e2'
                                  : t.status === 'done'
                                  ? '#e2e8f0'
                                  : '#d1fae5',
                                color: isConf || isOverdue
                                  ? '#991b1b'
                                  : t.status === 'done'
                                  ? '#475569'
                                  : '#065f46',
                              }}
                            >
                              {t.course_code} • {t.date} ({t.start})
                            </span>
                            <span style={{ fontSize: '0.72rem', color: '#64748b' }}>
                              📚 {pdfCount} PDF • {doneSubs}/{totalSubs} mục
                            </span>
                          </div>

                          <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>{t.title}</div>

                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              marginTop: '0.2rem',
                            }}
                          >
                            <span
                              style={{
                                fontSize: '0.72rem',
                                color: isOverdue ? '#b91c1c' : '#64748b',
                                fontWeight: isOverdue ? 700 : 400,
                              }}
                            >
                              {t.status === 'done'
                                ? '✅ Đã hoàn thành'
                                : isOverdue
                                ? '⏰ Chậm tiến độ — cần học bù'
                                : '⏳ Đang chờ học'}
                            </span>
                            <button
                              className="btn btn-primary"
                              style={{ padding: '0.25rem 0.65rem', fontSize: '0.74rem' }}
                              onClick={() => handleEnterWorkspace(t.task_id)}
                            >
                              Vào học →
                            </button>
                          </div>
                        </div>
                      );
                    })}
                    {(sortedTasks.length > 3 || (showAllTasks && sortedTasks.length > 0)) && (
                      <button
                        className="btn btn-outline"
                        style={{ width: '100%', marginTop: '0.5rem', fontSize: '0.78rem' }}
                        onClick={() => setShowAllTasks((v) => !v)}
                      >
                        {showAllTasks ? 'Thu gọn ▲' : `Xem thêm (${sortedTasks.length} buổi) ▼`}
                      </button>
                    )}
                  </div>
                </div>

                {/* Widget 2: Nguy cơ trễ hạn (Delay Prediction - MOCK) */}
                {delayPrediction && (
                  <div className={`risk-widget ${delayPrediction.is_resolved ? 'resolved' : ''}`}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '0.4rem',
                      }}
                    >
                      <strong
                        style={{
                          color: delayPrediction.is_resolved ? '#166534' : '#92400e',
                          fontSize: '0.92rem',
                        }}
                      >
                        {delayPrediction.is_resolved ? '✅ Tiến độ an toàn' : '⚡ Dự báo nguy cơ trễ hạn'}
                      </strong>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          background: delayPrediction.is_resolved ? '#bbf7d0' : '#fde68a',
                          color: delayPrediction.is_resolved ? '#14532d' : '#78350f',
                          padding: '0.15rem 0.45rem',
                          borderRadius: '4px',
                        }}
                      >
                        {delayPrediction.is_resolved
                          ? 'ĐÃ GIẢI QUYẾT • AN TOÀN'
                          : `MOCK • RỦI RO ${delayPrediction.risk_percent}%`}
                      </span>
                    </div>
                    <p
                      style={{
                        fontSize: '0.8rem',
                        color: delayPrediction.is_resolved ? '#166534' : '#78350f',
                        marginBottom: delayPrediction.suggested_action ? '0.65rem' : 0,
                      }}
                    >
                      Môn <strong>{delayPrediction.course_code}</strong>: {delayPrediction.reason}
                    </p>
                    {delayPrediction.suggested_action ? (
                      <button
                        className="btn btn-primary"
                        style={{ width: '100%', fontSize: '0.8rem' }}
                        onClick={handleAddExtraSessionFromWidget}
                      >
                        ➕ {delayPrediction.suggested_action}
                      </button>
                    ) : (
                      <div
                        style={{
                          marginTop: '0.45rem',
                          padding: '0.35rem 0.6rem',
                          background: '#dcfce7',
                          borderRadius: '6px',
                          fontSize: '0.75rem',
                          color: '#15803d',
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.35rem',
                        }}
                      >
                        <span>✓</span>
                        <span>Đã xếp 1 buổi học bù vào thời khóa biểu để chống trễ hạn.</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Widget 3: Mục tiêu tuần & Streak */}
                <div className="card" style={{ padding: '1rem 1.15rem' }}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <strong style={{ fontSize: '0.92rem' }}>🎯 Tiến độ mục tiêu tuần</strong>
                    <span
                      style={{
                        fontSize: '0.76rem',
                        fontWeight: 700,
                        color: '#059669',
                      }}
                    >
                      🔥 Chuỗi 5 ngày liên tiếp
                    </span>
                  </div>
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{ width: `${weeklyProgress.percent}%` }}
                    />
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.78rem',
                      color: '#64748b',
                    }}
                  >
                    <span>
                      Đã hoàn thành: <strong>{weeklyProgress.done}</strong> / {weeklyProgress.total}{' '}
                      phiên tự học
                    </span>
                    <strong>{weeklyProgress.percent}%</strong>
                  </div>
                </div>
              </div>
            </div>
          </main>
        </>
      )}

      {/* =====================================================================
          SCREEN 02: CONFLICT MODAL (CONFIRMATION GATE)
         ===================================================================== */}
      {showConflictModal && conflicts.length > 0 && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header-danger">
              <div>
                <h3 style={{ color: '#991b1b', fontSize: '1.1rem', fontWeight: 800 }}>
                  ⚠️ Xung đột lịch học trên lớp! (Confirmation Gate)
                </h3>
                <p style={{ fontSize: '0.8rem', color: '#b91c1c' }}>
                  Agent KHÔNG tự ý sửa lịch của bạn. Vui lòng kiểm tra và xác nhận phương án dời lịch bên dưới.
                </p>
              </div>
              <button
                className="btn btn-outline"
                style={{ padding: '0.3rem 0.6rem' }}
                onClick={() => setShowConflictModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {conflicts.map((c) => {
                const editState = editableConflicts[c.task_id] || {
                  new_date: c.new_suggested_date,
                  new_start: '19:30',
                  new_end: '21:00',
                };
                return (
                  <div
                    key={c.task_id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '0.75rem',
                      padding: '1rem',
                      marginBottom: '1rem',
                      background: '#f8fafc',
                    }}
                  >
                    <div
                      style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: '#dc2626',
                        marginBottom: '0.5rem',
                      }}
                    >
                      📌 Lý do: {c.reason}
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '0.75rem',
                        marginBottom: '0.85rem',
                      }}
                    >
                      <div
                        style={{
                          background: '#eff6ff',
                          border: '1px solid #93c5fd',
                          borderRadius: '0.55rem',
                          padding: '0.7rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1d4ed8' }}>
                          🏫 LỊCH CỐ ĐỊNH TRÊN TRƯỜNG (QLĐT)
                        </div>
                        <div style={{ fontWeight: 700, fontSize: '0.86rem', marginTop: '0.2rem' }}>
                          {c.conflict_with}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#1e40af' }}>
                          Ngày {c.old_date}
                        </div>
                      </div>

                      <div
                        style={{
                          background: '#fef2f2',
                          border: '1px solid #fca5a5',
                          borderRadius: '0.55rem',
                          padding: '0.7rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#dc2626' }}>
                          ❌ PHIÊN TỰ HỌC ĐANG BỊ TRÙNG
                        </div>
                        <div style={{ fontWeight: 700, fontSize: '0.86rem', marginTop: '0.2rem' }}>
                          {c.task_title}
                        </div>
                        <div style={{ fontSize: '0.78rem', color: '#991b1b' }}>
                          {c.old_date} | {c.old_time}
                        </div>
                      </div>
                    </div>

                    <div
                      style={{
                        background: '#ecfdf5',
                        border: '1.5px solid #34d399',
                        borderRadius: '0.6rem',
                        padding: '0.8rem',
                      }}
                    >
                      <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#065f46' }}>
                        ✅ ĐỀ XUẤT CỦA AI AGENT (KHUNG GIỜ TRỐNG KHÔNG TRÙNG):
                      </div>

                      {!customRescheduleMode ? (
                        <div
                          style={{
                            fontSize: '0.92rem',
                            fontWeight: 800,
                            color: '#047857',
                            marginTop: '0.25rem',
                          }}
                        >
                          Dời sang: Ngày {editState.new_date} • Khung giờ {editState.new_start} -{' '}
                          {editState.new_end}
                        </div>
                      ) : (
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr 1fr',
                            gap: '0.6rem',
                            marginTop: '0.5rem',
                          }}
                        >
                          <div>
                            <label style={{ fontSize: '0.72rem', fontWeight: 600 }}>Ngày mới</label>
                            <input
                              type="date"
                              className="input-field"
                              value={editState.new_date}
                              onChange={(e) =>
                                setEditableConflicts((prev) => ({
                                  ...prev,
                                  [c.task_id]: { ...editState, new_date: e.target.value },
                                }))
                              }
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.72rem', fontWeight: 600 }}>Bắt đầu</label>
                            <input
                              type="time"
                              className="input-field"
                              value={editState.new_start}
                              onChange={(e) =>
                                setEditableConflicts((prev) => ({
                                  ...prev,
                                  [c.task_id]: { ...editState, new_start: e.target.value },
                                }))
                              }
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: '0.72rem', fontWeight: 600 }}>Kết thúc</label>
                            <input
                              type="time"
                              className="input-field"
                              value={editState.new_end}
                              onChange={(e) =>
                                setEditableConflicts((prev) => ({
                                  ...prev,
                                  [c.task_id]: { ...editState, new_end: e.target.value },
                                }))
                              }
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={syncGcalChecked}
                  onChange={(e) => setSyncGcalChecked(e.target.checked)}
                />
                Đồng bộ cập nhật sự kiện lên Google Calendar (gcal_event_id)
              </label>
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-outline"
                onClick={() => setCustomRescheduleMode((v) => !v)}
              >
                ✏️ {customRescheduleMode ? 'Dùng giờ gợi ý của AI' : 'Để tôi tự chỉnh giờ'}
              </button>
              <button
                className="btn btn-emerald"
                onClick={handleConfirmReschedule}
                disabled={loading}
              >
                ✓ Đồng ý dời lịch & Đồng bộ Google Calendar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          ROADMAP GENERATOR & PREVIEW MODAL (MULTI-PDF SUPPORT)
         ===================================================================== */}
      {showRoadmapModal && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header-primary">
              <div>
                <h3 style={{ color: '#312e81', fontSize: '1.08rem', fontWeight: 800 }}>
                  ✨ Tạo lộ trình tự học AI từ Nhiều File Slide PDF
                </h3>
                <p style={{ fontSize: '0.78rem', color: '#4338ca' }}>
                  Cho phép đính kèm nhiều tài liệu PDF cho cùng một môn học / buổi học
                </p>
              </div>
              <button
                className="btn btn-outline"
                style={{ padding: '0.3rem 0.6rem' }}
                onClick={() => setShowRoadmapModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <form onSubmit={handleGenerateRoadmap} style={{ display: 'grid', gap: '0.85rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 600 }}>Chọn môn học PTIT</label>
                    <select
                      className="input-field"
                      value={rmCourseCode}
                      onChange={(e) => {
                        const code = e.target.value;
                        setRmCourseCode(code);
                        const found = COURSE_OPTIONS.find((c) => c.code === code);
                        if (found) setRmSlideUrls(found.slides);
                      }}
                    >
                      {COURSE_OPTIONS.map((c) => (
                        <option key={c.code} value={c.code}>
                          {c.code} - {c.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ fontSize: '0.78rem', fontWeight: 600 }}>
                      Ngày kiểm tra / Thi kết thúc
                    </label>
                    <input
                      type="date"
                      className="input-field"
                      value={rmExamDate}
                      onChange={(e) => setRmExamDate(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '0.78rem', fontWeight: 600 }}>
                    Số giờ rảnh mỗi ngày: <strong>{rmDailyHours} giờ</strong>
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    max="6"
                    className="input-field"
                    value={rmDailyHours}
                    onChange={(e) => setRmDailyHours(Number(e.target.value))}
                  />
                </div>

                <div>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '0.35rem',
                    }}
                  >
                    <label style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                      📚 Danh sách tài liệu PDF đính kèm ({rmSlideUrls.length} file):
                    </label>
                    <button
                      type="button"
                      className="btn btn-outline"
                      style={{ padding: '0.25rem 0.65rem', fontSize: '0.76rem' }}
                      onClick={() => roadmapFileInputRef.current?.click()}
                    >
                      ➕ Tải thêm PDF từ máy tính (Chọn nhiều file)
                    </button>
                  </div>

                  <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap' }}>
                    {rmSlideUrls.map((u, idx) => (
                      <span
                        key={u}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          background: '#eef2ff',
                          border: '1px solid #c7d2fe',
                          color: '#312e81',
                          padding: '0.25rem 0.6rem',
                          borderRadius: '0.45rem',
                          fontSize: '0.76rem',
                          fontWeight: 600,
                        }}
                      >
                        📄 {idx + 1}. {u.split('/').pop()}
                        {rmSlideUrls.length > 1 && (
                          <button
                            type="button"
                            style={{
                              border: 'none',
                              background: 'transparent',
                              color: '#dc2626',
                              cursor: 'pointer',
                              fontWeight: 800,
                            }}
                            onClick={() =>
                              setRmSlideUrls((prev) => prev.filter((item) => item !== u))
                            }
                          >
                            ✕
                          </button>
                        )}
                      </span>
                    ))}
                  </div>
                </div>

                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading
                    ? 'Đang đọc các file PDF & Tính lịch trống...'
                    : `🔍 Phân tích ${rmSlideUrls.length} file PDF & Tạo lộ trình nháp`}
                </button>
              </form>

              {roadmapDraft && (
                <div
                  style={{
                    marginTop: '1.15rem',
                    borderTop: '1px solid #e2e8f0',
                    paddingTop: '1rem',
                  }}
                >
                  <div
                    style={{
                      background: '#eef2ff',
                      padding: '0.75rem',
                      borderRadius: '0.6rem',
                      fontSize: '0.82rem',
                      color: '#312e81',
                      marginBottom: '0.85rem',
                    }}
                  >
                    <strong>Tóm tắt lộ trình AI:</strong> {roadmapDraft.summary}
                  </div>

                  <div style={{ display: 'grid', gap: '0.65rem' }}>
                    {roadmapDraft.suggested_sessions.map((s, idx) => (
                      <div
                        key={idx}
                        style={{
                          border: '1px solid #cbd5e1',
                          borderRadius: '0.6rem',
                          padding: '0.75rem',
                          background: '#f8fafc',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontWeight: 700,
                            fontSize: '0.85rem',
                            color: '#065f46',
                          }}
                        >
                          <span>{s.title}</span>
                          <span>
                            {s.suggested_date} ({s.suggested_start} - {s.suggested_end})
                          </span>
                        </div>
                        <ul
                          style={{
                            marginLeft: '1.1rem',
                            marginTop: '0.35rem',
                            fontSize: '0.78rem',
                            color: '#334155',
                          }}
                        >
                          {s.subtasks.map((sub) => (
                            <li key={sub.sub_id}>{sub.content}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {roadmapDraft && (
              <div className="modal-footer">
                <button className="btn btn-outline" onClick={() => setRoadmapDraft(null)}>
                  Hủy bản nháp
                </button>
                <button
                  className="btn btn-emerald"
                  onClick={handleConfirmSaveRoadmap}
                  disabled={loading}
                >
                  ✓ Xác nhận lưu {roadmapDraft.suggested_sessions.length} phiên vào lịch cá nhân
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* =====================================================================
          ROADMAP LIST & MANAGEMENT MODAL (VIEW / SELECT / DELETE ROADMAPS)
         ===================================================================== */}
      {showRoadmapListModal && (
        <div className="modal-backdrop">
          <div className="modal-box" style={{ maxWidth: '780px' }}>
            <div className="modal-header-primary">
              <div>
                <h3 style={{ color: '#312e81', fontSize: '1.08rem', fontWeight: 800 }}>
                  🗺️ Danh sách các Lộ trình Tự học Hiện tại
                </h3>
                <p style={{ fontSize: '0.78rem', color: '#4338ca' }}>
                  Quản lý các môn học đã lập kế hoạch. Bạn có thể chọn và xóa một hoặc nhiều lộ trình không còn cần thiết.
                </p>
              </div>
              <button
                className="btn btn-outline"
                style={{ padding: '0.3rem 0.6rem' }}
                onClick={() => setShowRoadmapListModal(false)}
              >
                ✕
              </button>
            </div>

            <div className="modal-body" style={{ padding: '1.25rem' }}>
              {roadmapsLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem 0', color: '#6366f1' }}>
                  ⏳ Đang tải danh sách lộ trình...
                </div>
              ) : roadmapsList.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2.5rem 1rem' }}>
                  <div style={{ fontSize: '2.5rem', marginBottom: '0.6rem' }}>📚</div>
                  <h4 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>
                    Chưa có lộ trình tự học nào
                  </h4>
                  <p style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '0.25rem', marginBottom: '1.2rem' }}>
                    Bạn chưa tạo lộ trình tự học nào từ slide PDF. Hãy tạo lộ trình để AI tự động chia mục tiêu và xếp lịch thông minh!
                  </p>
                  <button
                    className="btn btn-primary"
                    onClick={() => {
                      setShowRoadmapListModal(false);
                      setRoadmapDraft(null);
                      setShowRoadmapModal(true);
                    }}
                  >
                    ✨ + Tạo lộ trình mới ngay
                  </button>
                </div>
              ) : (
                <>
                  {/* Toolbar: Select All + Batch Delete */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '1rem',
                      padding: '0.6rem 0.85rem',
                      background: '#f8fafc',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0',
                      flexWrap: 'wrap',
                      gap: '0.5rem',
                    }}
                  >
                    <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.84rem', fontWeight: 600, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={selectedRoadmapIds.length === roadmapsList.length && roadmapsList.length > 0}
                        onChange={handleToggleSelectAllRoadmaps}
                      />
                      Chọn tất cả ({selectedRoadmapIds.length}/{roadmapsList.length} lộ trình)
                    </label>

                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {selectedRoadmapIds.length > 0 && (
                        <button
                          className="btn btn-danger"
                          style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem', fontWeight: 700 }}
                          onClick={() => handleDeleteRoadmaps(selectedRoadmapIds)}
                        >
                          🗑️ Xóa {selectedRoadmapIds.length} lộ trình đã chọn
                        </button>
                      )}

                      <button
                        className="btn btn-outline"
                        style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                        onClick={() => {
                          setShowRoadmapListModal(false);
                          setRoadmapDraft(null);
                          setShowRoadmapModal(true);
                        }}
                      >
                        + Thêm lộ trình khác
                      </button>
                    </div>
                  </div>

                  {/* List of Roadmaps */}
                  <div style={{ display: 'grid', gap: '0.85rem', maxHeight: '55vh', overflowY: 'auto' }}>
                    {roadmapsList.map((rm) => {
                      const isSelected = selectedRoadmapIds.includes(rm.roadmap_id);
                      return (
                        <div
                          key={rm.roadmap_id}
                          style={{
                            padding: '1rem',
                            borderRadius: '10px',
                            border: isSelected ? '2px solid #6366f1' : '1px solid #e2e8f0',
                            background: isSelected ? '#f5f3ff' : '#ffffff',
                            boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleSelectRoadmap(rm.roadmap_id)}
                                style={{ marginTop: '0.3rem', width: '1.1rem', height: '1.1rem', cursor: 'pointer' }}
                              />
                              <div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                  <span
                                    style={{
                                      fontSize: '0.75rem',
                                      fontWeight: 800,
                                      padding: '0.15rem 0.5rem',
                                      borderRadius: '6px',
                                      background: '#e0e7ff',
                                      color: '#3730a3',
                                    }}
                                  >
                                    {rm.course_code}
                                  </span>
                                  <strong style={{ fontSize: '0.98rem', color: '#1e293b' }}>
                                    {rm.course_name}
                                  </strong>
                                </div>

                                <div
                                  style={{
                                    display: 'flex',
                                    gap: '1rem',
                                    fontSize: '0.78rem',
                                    color: '#475569',
                                    marginTop: '0.45rem',
                                    flexWrap: 'wrap',
                                  }}
                                >
                                  <span>📅 <strong>{rm.start_date}</strong> → <strong>{rm.end_date}</strong></span>
                                  <span>📚 Tổng số: <strong>{rm.total_sessions} buổi</strong></span>
                                  <span style={{ color: '#15803d' }}>✓ Hoàn thành: <strong>{rm.completed_sessions}</strong></span>
                                  {rm.overdue_sessions > 0 && (
                                    <span style={{ color: '#b91c1c', fontWeight: 700 }}>
                                      ⏰ Chậm tiến độ: {rm.overdue_sessions}
                                    </span>
                                  )}
                                </div>

                                {rm.slide_urls && rm.slide_urls.length > 0 && (
                                  <div style={{ marginTop: '0.4rem', fontSize: '0.74rem', color: '#64748b' }}>
                                    📄 Tài liệu: {rm.slide_urls.map((u) => u.split('/').pop()).join(', ')}
                                  </div>
                                )}
                              </div>
                            </div>

                            <button
                              className="btn btn-outline"
                              style={{
                                padding: '0.3rem 0.65rem',
                                fontSize: '0.78rem',
                                color: '#b91c1c',
                                borderColor: '#fca5a5',
                                background: '#fef2f2',
                                whiteSpace: 'nowrap',
                              }}
                              onClick={() => handleDeleteRoadmaps([rm.roadmap_id])}
                              title="Xóa lộ trình này"
                            >
                              🗑️ Xóa lộ trình
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>

            <div
              style={{
                padding: '0.85rem 1.25rem',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'flex-end',
                background: '#f8fafc',
                borderBottomLeftRadius: '1rem',
                borderBottomRightRadius: '1rem',
              }}
            >
              <button
                className="btn btn-outline"
                onClick={() => setShowRoadmapListModal(false)}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          SETTINGS MODAL (1-TIME QLĐT LOGIN + SUNDAY AUTO-SYNC + API KEYS)
         ===================================================================== */}
      {showSettingsModal && (
        <div className="modal-backdrop">
          <div className="modal-box">
            <div className="modal-header-primary">
              <div>
                <h3 style={{ color: '#312e81', fontSize: '1.08rem', fontWeight: 800 }}>
                  ⚙️ Cấu hình Tài khoản QLĐT PTIT & AI Agent
                </h3>
                <p style={{ fontSize: '0.78rem', color: '#4338ca' }}>
                  Chỉ cần nhập tài khoản QLĐT 1 lần duy nhất — Agent sẽ lưu lại và tự động cào lịch vào mỗi Chủ Nhật
                </p>
              </div>
              <button
                className="btn btn-outline"
                style={{ padding: '0.3rem 0.6rem' }}
                onClick={() => setShowSettingsModal(false)}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveSettings}>
              <div className="modal-body" style={{ display: 'grid', gap: '0.9rem' }}>
                <div
                  style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '0.65rem',
                    padding: '0.9rem',
                    display: 'grid',
                    gap: '0.7rem',
                  }}
                >
                  <strong style={{ fontSize: '0.88rem', color: '#1e293b' }}>
                    1. Tài khoản Cổng QLĐT PTIT (https://qldt.ptit.edu.vn)
                  </strong>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.7rem' }}>
                    <div>
                      <label style={{ fontSize: '0.76rem', fontWeight: 600 }}>
                        Mã sinh viên (Username)
                      </label>
                      <input
                        type="text"
                        className="input-field"
                        placeholder="VD: B25DCCN609"
                        value={qldtUserForm}
                        onChange={(e) => setQldtUserForm(e.target.value)}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '0.76rem', fontWeight: 600 }}>
                        Mật khẩu QLĐT{' '}
                        {settings?.has_qldt_password ? '(Đã lưu - để trống nếu giữ nguyên)' : ''}
                      </label>
                      <input
                        type="password"
                        className="input-field"
                        placeholder="Nhập mật khẩu QLĐT..."
                        value={qldtPassForm}
                        onChange={(e) => setQldtPassForm(e.target.value)}
                      />
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '0.7rem' }}>
                    <div>
                      <label style={{ fontSize: '0.76rem', fontWeight: 600 }}>Mã học kỳ</label>
                      <input
                        type="number"
                        className="input-field"
                        value={hocKyForm}
                        onChange={(e) => setHocKyForm(Number(e.target.value))}
                      />
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', paddingTop: '1.2rem' }}>
                      <label
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={autoSyncSundayForm}
                          onChange={(e) => setAutoSyncSundayForm(e.target.checked)}
                        />
                        Tự động cào lịch QLĐT vào mỗi cuối tuần (Chủ Nhật)
                      </label>
                    </div>
                  </div>
                </div>

                <div
                  style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '0.65rem',
                    padding: '0.9rem',
                    display: 'grid',
                    gap: '0.7rem',
                  }}
                >
                  <strong style={{ fontSize: '0.88rem', color: '#1e293b' }}>
                    2. Cấu hình LLM API Keys (Gemini 3.8 Flash Primary + Groq Fallback)
                  </strong>
                  <div>
                    <label style={{ fontSize: '0.76rem', fontWeight: 600 }}>
                      Google Gemini API Key (gemini-3.8-flash){' '}
                      {settings?.has_gemini_api_key ? '✅ Đã cấu hình' : '(Tùy chọn)'}
                    </label>
                    <input
                      type="password"
                      className="input-field"
                      placeholder="Để trống nếu muốn giữ nguyên key đã lưu..."
                      value={geminiKeyForm}
                      onChange={(e) => setGeminiKeyForm(e.target.value)}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.76rem', fontWeight: 600 }}>
                      Groq API Key (Fallback khi Gemini vượt quota 429){' '}
                      {settings?.has_groq_api_key ? '✅ Đã cấu hình' : '(Tùy chọn)'}
                    </label>
                    <input
                      type="password"
                      className="input-field"
                      placeholder="gsk_..."
                      value={groqKeyForm}
                      onChange={(e) => setGroqKeyForm(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={() => setShowSettingsModal(false)}
                >
                  Đóng
                </button>
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  💾 Lưu cấu hình & Đồng bộ
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =====================================================================
          SCREEN 03: SPLIT-SCREEN 50/50 DEEP WORKING WORKSPACE (MULTI-PDF)
         ===================================================================== */}
      {screen === 'workspace' && activeTask && (
        <div>
          <header className="workspace-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
              <button
                className="btn btn-glass"
                onClick={() => setScreen('dashboard')}
              >
                ← Trở về Lịch tuần
              </button>
              <div>
                <div style={{ fontWeight: 800, fontSize: '1.02rem' }}>
                  {activeTask.title} ({activeTask.course_code})
                </div>
                <div style={{ fontSize: '0.76rem', opacity: 0.85 }}>
                  Môn: {activeTask.course_name} • Khung giờ: {activeTask.date} ({activeTask.start} -{' '}
                  {activeTask.end}) • Đang nạp {sessionDocuments.length} tài liệu PDF
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <button
                className="btn btn-glass"
                onClick={() => workspaceFileInputRef.current?.click()}
                title="Chọn 1 hoặc nhiều file PDF từ máy tính để thêm vào buổi học này"
              >
                ➕ Thêm tài liệu PDF ({sessionDocuments.length} file)
              </button>
              <button
                className="btn btn-emerald"
                onClick={handleCompleteSession}
                disabled={loading}
              >
                ✓ HOÀN THÀNH PHIÊN TỰ HỌC
              </button>
            </div>
          </header>

          <div className="workspace-split">
            {/* LEFT 50% PANE: MULTI-PDF VIEWER & EXTRACTED CONTEXT */}
            <div className="workspace-pane">
              <div className="card-header" style={{ background: '#f8fafc', padding: '0.7rem 1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <button
                    className={`btn ${leftPaneTab === 'pdf' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ padding: '0.32rem 0.7rem', fontSize: '0.76rem' }}
                    onClick={() => setLeftPaneTab('pdf')}
                  >
                    📄 Xem Slide PDF (Tổng {activeDoc?.page_count || 0} trang)
                  </button>
                  <button
                    className={`btn ${leftPaneTab === 'extracted' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ padding: '0.32rem 0.7rem', fontSize: '0.76rem' }}
                    onClick={() => setLeftPaneTab('extracted')}
                  >
                    🔍 Văn bản trích xuất PyMuPDF (&lt;DOCUMENT_DATA&gt;)
                  </button>
                </div>
                <span
                  style={{
                    fontSize: '0.73rem',
                    fontWeight: 700,
                    color:
                      activeDoc?.document_status === 'loaded'
                        ? '#059669'
                        : activeDoc?.document_status === 'ocr_fallback'
                        ? '#d97706'
                        : '#dc2626',
                  }}
                >
                  Trạng thái: {activeDoc?.document_status || 'loaded'}
                </span>
              </div>

              {/* MULTI-PDF DOCUMENT TABS BAR */}
              <div
                style={{
                  background: '#eef2ff',
                  borderBottom: '1px solid #c7d2fe',
                  padding: '0.45rem 0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  overflowX: 'auto',
                  flexWrap: 'wrap',
                }}
              >
                <span style={{ fontSize: '0.73rem', fontWeight: 700, color: '#312e81' }}>
                  📚 Tài liệu buổi học ({sessionDocuments.length}):
                </span>
                {sessionDocuments.map((docItem, idx) => {
                  const isActive = selectedPdfUrl === docItem.slide_url;
                  return (
                    <div
                      key={docItem.slide_url}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        background: isActive ? '#4f46e5' : '#ffffff',
                        color: isActive ? '#ffffff' : '#312e81',
                        border: `1px solid ${isActive ? '#4338ca' : '#a5b4fc'}`,
                        borderRadius: '0.45rem',
                        padding: '0.22rem 0.55rem',
                        fontSize: '0.74rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                      onClick={() => {
                        setSelectedPdfUrl(docItem.slide_url);
                        setLeftPaneTab('pdf');
                      }}
                    >
                      <span>
                        {idx + 1}. {docItem.filename || docItem.slide_url.split('/').pop()} (
                        {docItem.page_count}tr)
                      </span>
                      {sessionDocuments.length > 1 && (
                        <button
                          type="button"
                          title="Gỡ tài liệu này khỏi buổi học"
                          style={{
                            border: 'none',
                            background: 'transparent',
                            color: isActive ? '#fecaca' : '#dc2626',
                            cursor: 'pointer',
                            fontWeight: 800,
                            fontSize: '0.74rem',
                            marginLeft: '0.15rem',
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRemovePdfFromSession(docItem.slide_url);
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  );
                })}
                <button
                  type="button"
                  className="btn btn-outline"
                  style={{ padding: '0.2rem 0.55rem', fontSize: '0.72rem' }}
                  onClick={() => workspaceFileInputRef.current?.click()}
                >
                  + Thêm PDF
                </button>
              </div>

              {leftPaneTab === 'pdf' ? (
                selectedPdfUrl ? (
                  <iframe
                    key={selectedPdfUrl}
                    title="Slide PDF Viewer"
                    className="pdf-frame"
                    src={getStaticUrl(selectedPdfUrl)}
                  />
                ) : (
                  <div style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                    Chưa có tài liệu PDF cho phiên học này. Nhấn &ldquo;+ Thêm PDF&rdquo; để tải lên!
                  </div>
                )
              ) : (
                <div
                  style={{
                    padding: '1.1rem',
                    overflowY: 'auto',
                    flex: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.8rem',
                    whiteSpace: 'pre-wrap',
                    background: '#0f172a',
                    color: '#e2e8f0',
                  }}
                >
                  {`<DOCUMENT_DATA>\n${
                    activeDoc?.extracted_text || 'Không có văn bản trích xuất.'
                  }\n</DOCUMENT_DATA>`}
                </div>
              )}
            </div>

            {/* RIGHT 50% PANE: POMODORO + SUBTASK CHECKLIST + AI TUTOR / FLASHCARDS */}
            <div className="workspace-pane">
              {/* Pomodoro 25:00 Bar */}
              <div className="pomodoro-bar">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                  <div className="pomodoro-clock">🍅 {formatTimer(pomoSeconds)}</div>
                  <div>
                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#312e81' }}>
                      Đồng hồ Tập trung Pomodoro
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#4338ca' }}>
                      Đã hoàn thành: <strong>{pomoCompletedCount}</strong> /{' '}
                      {activeTask.pomodoro_target} Pomodoro ({pomoCompletedCount * 25} phút)
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '0.45rem' }}>
                  <button
                    className={`btn ${pomoRunning ? 'btn-danger' : 'btn-primary'}`}
                    style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem' }}
                    onClick={() => setPomoRunning((r) => !r)}
                  >
                    {pomoRunning ? '⏸ Tạm dừng' : '▶ Bắt đầu'}
                  </button>
                  <button
                    className="btn btn-outline"
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.78rem' }}
                    onClick={() => {
                      setPomoRunning(false);
                      setPomoSeconds(25 * 60);
                    }}
                  >
                    ↺ Đặt lại
                  </button>
                  <button
                    className="btn btn-outline"
                    style={{ padding: '0.35rem 0.65rem', fontSize: '0.78rem' }}
                    onClick={() => setPomoCompletedCount((c) => c + 1)}
                    title="Cộng thêm 1 Pomodoro hoàn thành để test nhanh"
                  >
                    +1 🍅
                  </button>
                </div>
              </div>

              {/* Checklist Tự Học & Ghi chú */}
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  borderBottom: '1px solid #e2e8f0',
                  background: '#ffffff',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '0.45rem',
                  }}
                >
                  <strong style={{ fontSize: '0.86rem' }}>
                    ☑️ Checklist mục tiêu tự học ({activeTask.subtasks.length} mục)
                  </strong>
                  <span style={{ fontSize: '0.74rem', color: '#059669', fontWeight: 700 }}>
                    Hoàn thành:{' '}
                    {Object.values(checkedSubtasks).filter(Boolean).length}/
                    {activeTask.subtasks.length}
                  </span>
                </div>

                <div style={{ display: 'grid', gap: '0.35rem', marginBottom: '0.6rem' }}>
                  {activeTask.subtasks.map((sub) => (
                    <label
                      key={sub.sub_id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.55rem',
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        textDecoration: checkedSubtasks[sub.sub_id] ? 'line-through' : 'none',
                        color: checkedSubtasks[sub.sub_id] ? '#64748b' : '#0f172a',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={Boolean(checkedSubtasks[sub.sub_id])}
                        onChange={(e) =>
                          setCheckedSubtasks((prev) => ({
                            ...prev,
                            [sub.sub_id]: e.target.checked,
                          }))
                        }
                      />
                      {sub.content}
                    </label>
                  ))}
                </div>

                <input
                  type="text"
                  className="input-field"
                  placeholder="📝 Ghi chú cá nhân cho phiên học tiếp theo..."
                  value={personalNotes}
                  onChange={(e) => setPersonalNotes(e.target.value)}
                  style={{ fontSize: '0.78rem', padding: '0.4rem 0.65rem' }}
                />
              </div>

              {/* Sub-navigation between AI Tutor Chat and Flashcard Review */}
              <div
                style={{
                  padding: '0.5rem 1.1rem',
                  borderBottom: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '0.5rem',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', gap: '0.45rem' }}>
                  <button
                    className={`btn ${rightPaneTab === 'tutor' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ padding: '0.3rem 0.7rem', fontSize: '0.76rem' }}
                    onClick={() => setRightPaneTab('tutor')}
                  >
                    🤖 AI Trợ giảng (Gemini 3.8 Flash)
                  </button>
                  <button
                    className={`btn ${
                      rightPaneTab === 'flashcards' ? 'btn-primary' : 'btn-outline'
                    }`}
                    style={{ padding: '0.3rem 0.7rem', fontSize: '0.76rem' }}
                    onClick={() => setRightPaneTab('flashcards')}
                  >
                    🗂️ Flashcard Ôn tập ({flashcards.length})
                  </button>
                </div>

                <button
                  className="btn btn-outline"
                  style={{ padding: '0.28rem 0.6rem', fontSize: '0.73rem' }}
                  onClick={handleTriggerInactivityCheck}
                  title="Mô phỏng 10 phút không thao tác để kiểm thử Proactive Reminder & Cooldown 300s"
                >
                  ⏱️ Test 10p không thao tác
                </button>
              </div>

              {rightPaneTab === 'tutor' ? (
                <>
                  <div className="chat-messages">
                    {chatHistory.map((msg, i) => (
                      <div
                        key={i}
                        className={`chat-bubble ${msg.role} ${
                          msg.isProactive ? 'proactive' : ''
                        }`}
                      >
                        {msg.role === 'assistant' && msg.provider && (
                          <div
                            style={{
                              fontSize: '0.68rem',
                              fontWeight: 700,
                              color: msg.isProactive ? '#b45309' : '#4f46e5',
                              marginBottom: '0.35rem',
                            }}
                          >
                            ⚡ Nguồn phản hồi: {msg.provider}
                          </div>
                        )}
                        {msg.role === 'assistant'
                          ? renderFormattedMarkdown(msg.content)
                          : msg.content}
                      </div>
                    ))}
                    {tutorLoading && (
                      <div className="chat-bubble assistant">
                        ⏳ AI Trợ giảng (Gemini 3.8 Flash) đang đọc {sessionDocuments.length} tài liệu
                        PDF và phân tích câu hỏi của bạn...
                      </div>
                    )}
                  </div>

                  {/* Quick Prompt Chips & Input */}
                  <div
                    style={{
                      padding: '0.75rem 1rem',
                      borderTop: '1px solid #e2e8f0',
                      background: '#ffffff',
                      display: 'grid',
                      gap: '0.5rem',
                    }}
                  >
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ padding: '0.2rem 0.55rem', fontSize: '0.72rem' }}
                        onClick={() =>
                          handleSendTutorMessage(
                            'Cho tôi biết có dùng stack thay cho viết hàm đệ quy khi duyệt cây nhị phân được không?'
                          )
                        }
                      >
                        💡 Dùng Stack thay Đệ quy?
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ padding: '0.2rem 0.55rem', fontSize: '0.72rem' }}
                        onClick={() => {
                          setShowCodeInput(true);
                          handleSendTutorMessage(
                            'Tại sao đoạn code duyệt cây nhị phân của mình lại bị lỗi đệ quy vô tận nhỉ?'
                          );
                        }}
                      >
                        🐞 Debug code duyệt cây lỗi
                      </button>
                      <button
                        type="button"
                        className="btn btn-outline"
                        style={{ padding: '0.2rem 0.55rem', fontSize: '0.72rem' }}
                        onClick={() => setShowCodeInput((v) => !v)}
                      >
                        💻 {showCodeInput ? 'Ẩn ô dán Code' : 'Dán Code cần Debug'}
                      </button>
                    </div>

                    {showCodeInput && (
                      <textarea
                        className="input-field"
                        rows={3}
                        style={{ fontFamily: 'monospace', fontSize: '0.76rem' }}
                        placeholder="Dán đoạn code C/C++/Python cần trợ giảng tìm lỗi..."
                        value={codeSnippet}
                        onChange={(e) => setCodeSnippet(e.target.value)}
                      />
                    )}

                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        handleSendTutorMessage();
                      }}
                      style={{ display: 'flex', gap: '0.5rem' }}
                    >
                      <input
                        type="text"
                        className="input-field"
                        placeholder="Hỏi AI Trợ giảng bất kỳ câu hỏi nào..."
                        value={userMessage}
                        onChange={(e) => setUserMessage(e.target.value)}
                      />
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={tutorLoading}
                      >
                        Gửi →
                      </button>
                    </form>
                  </div>
                </>
              ) : (
                <div style={{ padding: '1rem', overflowY: 'auto', flex: 1 }}>
                  <p style={{ fontSize: '0.8rem', color: '#475569', marginBottom: '0.75rem' }}>
                    Nhấn vào từng thẻ Flashcard bên dưới để lật xem đáp án & giải thích trích xuất từ{' '}
                    {sessionDocuments.length} tài liệu PDF của buổi học:
                  </p>
                  <div style={{ display: 'grid', gap: '0.75rem' }}>
                    {flashcards.map((fc, idx) => {
                      const isFlipped = Boolean(flippedCards[fc.card_id]);
                      return (
                        <div
                          key={fc.card_id}
                          onClick={() =>
                            setFlippedCards((prev) => ({
                              ...prev,
                              [fc.card_id]: !prev[fc.card_id],
                            }))
                          }
                          style={{
                            border: '1.5px solid #c7d2fe',
                            borderRadius: '0.75rem',
                            padding: '0.9rem',
                            background: isFlipped ? '#ecfdf5' : '#eef2ff',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <div
                            style={{
                              fontSize: '0.72rem',
                              fontWeight: 700,
                              color: isFlipped ? '#047857' : '#4338ca',
                              marginBottom: '0.25rem',
                            }}
                          >
                            THẺ #{idx + 1} •{' '}
                            {isFlipped ? 'ĐÁP ÁN & GIẢI THÍCH' : 'CÂU HỎI ÔN TẬP (Nhấn để lật)'}
                          </div>
                          <div style={{ fontWeight: 700, fontSize: '0.86rem' }}>
                            {isFlipped ? fc.answer : fc.question}
                          </div>
                          {isFlipped && (
                            <div
                              style={{
                                fontSize: '0.78rem',
                                color: '#065f46',
                                marginTop: '0.35rem',
                              }}
                            >
                              💡 <em>{fc.explanation}</em>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =====================================================================
          SCREEN 04: SESSION SUMMARY CARD
         ===================================================================== */}
      {screen === 'summary' && summaryCard && (
        <div className="summary-container">
          <div className="card">
            <div
              style={{
                background: 'linear-gradient(90deg, #059669 0%, #10b981 100%)',
                color: '#ffffff',
                padding: '1.4rem 1.6rem',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: '2.2rem', marginBottom: '0.3rem' }}>🎉</div>
              <h2 style={{ fontSize: '1.35rem', fontWeight: 800 }}>
                Tổng kết Phiên Tự Học
              </h2>
              <p style={{ fontSize: '0.9rem', opacity: 0.92 }}>{summaryCard.task_title}</p>
            </div>

            <div style={{ padding: '1.5rem' }}>
              <div className="summary-stats-grid">
                <div className="stat-card">
                  <div className="stat-value">{summaryCard.total_focus_minutes} Phút</div>
                  <div className="stat-label">{summaryCard.pomodoro_result}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{summaryCard.completed_tasks_count}</div>
                  <div className="stat-label">Mục tiêu hoàn thành</div>
                </div>
                <div className="stat-card">
                  <div className="stat-value">{summaryCard.completion_rate_percent}%</div>
                  <div className="stat-label">Tỷ lệ hoàn thành</div>
                </div>
              </div>

              {summaryCard.remaining_subtasks.length > 0 && (
                <div
                  style={{
                    background: '#fffbeb',
                    border: '1px solid #fde68a',
                    borderRadius: '0.75rem',
                    padding: '0.95rem 1.1rem',
                    marginBottom: '1rem',
                  }}
                >
                  <strong style={{ fontSize: '0.86rem', color: '#92400e' }}>
                    📌 Các mục còn lại sẽ được nhắc ở buổi tiếp theo:
                  </strong>
                  <ul
                    style={{
                      marginLeft: '1.2rem',
                      marginTop: '0.35rem',
                      fontSize: '0.82rem',
                      color: '#78350f',
                    }}
                  >
                    {summaryCard.remaining_subtasks.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {personalNotes && (
                <div
                  style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: '0.75rem',
                    padding: '0.95rem 1.1rem',
                    marginBottom: '1.2rem',
                  }}
                >
                  <strong style={{ fontSize: '0.84rem', color: '#334155' }}>
                    📝 Ghi chú cá nhân đã lưu:
                  </strong>
                  <p style={{ fontSize: '0.84rem', color: '#0f172a', marginTop: '0.25rem' }}>
                    {personalNotes}
                  </p>
                </div>
              )}

              <button
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.75rem', fontSize: '0.95rem' }}
                onClick={() => setScreen('dashboard')}
              >
                ✓ LƯU TIẾN ĐỘ & VỀ TRANG CHỦ
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
