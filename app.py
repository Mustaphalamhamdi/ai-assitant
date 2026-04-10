#!/usr/bin/env python3
"""Aria — animated overlay voice assistant."""
import sys, os, time, math, random

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Qt plugin path fix for Anaconda ──────────────────────────────────────────
try:
    import PyQt6 as _q
    _d = os.path.join(os.path.dirname(_q.__file__), "Qt6")
    os.environ.setdefault("QT_PLUGIN_PATH",              os.path.join(_d, "plugins"))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", os.path.join(_d, "plugins", "platforms"))
    del _q, _d
except ImportError:
    pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QSystemTrayIcon, QMenu, QFrame,
    QTabWidget, QListWidget, QListWidgetItem, QLineEdit, QFormLayout,
    QDialog, QDialogButtonBox, QComboBox, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QSpinBox, QMessageBox,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QTimer, QSize,
    QPropertyAnimation, QPoint, QPointF, QEasingCurve, QRectF,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QTextCursor,
    QBrush, QPen, QPolygonF, QPainterPath,
)

from user_config import get_config

# ═══════════════════════════════════════════════════════════════════════════════
#  SIGNALS
# ═══════════════════════════════════════════════════════════════════════════════
class _Sig(QObject):
    log          = pyqtSignal(str, str)   # (message, role)
    status       = pyqtSignal(str)        # sleeping|listening|thinking|speaking
    show_overlay = pyqtSignal()
    hide_overlay = pyqtSignal()

signals = _Sig()

# ═══════════════════════════════════════════════════════════════════════════════
#  PATCH TTS → emit Qt signals on main thread
# ═══════════════════════════════════════════════════════════════════════════════
import speaker.tts as _tts
_orig_speak      = _tts.speak
_orig_speak_male = _tts.speak_male

def _speak(text, online=True):
    signals.log.emit(text, "aria"); _orig_speak(text, online)
def _speak_male(text):
    signals.log.emit(text, "aria"); _orig_speak_male(text)

_tts.speak      = _speak
_tts.speak_male = _speak_male

# ═══════════════════════════════════════════════════════════════════════════════
#  BACKEND
# ═══════════════════════════════════════════════════════════════════════════════
from brain.gemini_agent       import ask_gemini, reset_conversation
from listener.wake_detector   import listen_for_wake_word
from listener.session_manager import SessionManager
from tools.app_control        import open_app, close_app, start_global_allow_watcher
from tools.dev_tools          import open_project, run_terminal
from tools.design_tools       import create_design_project, open_design_folder, move_exports_to_desktop
from tools.web_tools          import open_url, search_web
from tools.browser_tools      import play_youtube, play_spotify, read_screen, close_tab
from tools.productivity_tools import (take_screenshot, read_clipboard,
                                       control_volume, start_focus_timer, remind_me)
from tools.voice_tools        import switch_voice
from tools.control_tools      import type_text, press_key, wait_seconds

TOOL_MAP = {
    "open_app": open_app, "close_app": close_app,
    "open_project": open_project, "run_terminal": run_terminal,
    "create_design_project": create_design_project,
    "open_design_folder": open_design_folder,
    "move_exports_to_desktop": move_exports_to_desktop,
    "search_web": search_web, "open_url": open_url,
    "play_youtube": play_youtube, "play_spotify": play_spotify, "read_screen": read_screen,
    "close_tab": close_tab,
    "take_screenshot": take_screenshot, "read_clipboard": read_clipboard,
    "control_volume": control_volume, "start_focus_timer": start_focus_timer,
    "remind_me": remind_me,
    "switch_voice": switch_voice,
    "type_text": type_text,
    "press_key": press_key,
    "wait_seconds": wait_seconds,
}

ACTION_SCHEMA: dict = {
    "open_app":              [("name",    "App",              "app_list")],
    "close_app":             [("name",    "App",              "app_list")],
    "open_url":              [("url",     "URL",              "text")],
    "search_web":            [("query",   "Search query",     "text")],
    "run_terminal":          [("command", "Shell command",    "text")],
    "open_project":          [("name",    "Project",          "project_list")],
    "control_volume":        [("action",  "Direction",        "choice:up:down:mute")],
    "start_focus_timer":     [("minutes", "Minutes",          "number")],
    "remind_me":             [("minutes", "Minutes",          "number"),
                              ("message", "Reminder message", "text")],
    "create_design_project": [("name",    "Project name",     "text")],
    "take_screenshot":       [],
    "read_clipboard":        [],
    "open_design_folder":    [],
    "move_exports_to_desktop": [],
    "switch_voice":          [("language", "Language",        "text")],
}

DISMISS_PHRASES = [
    "go for now", "goodbye", "bye for now", "go to sleep",
    "that's all", "sleep now", "dismiss", "good night", "hide",
]


def _app_list() -> list:
    from config import APP_PATHS
    keys = set(APP_PATHS.keys())
    for app in get_config().custom_apps:
        for k in app["triggers"].split(","):
            k = k.strip()
            if k:
                keys.add(k)
    return sorted(keys)


def _project_list() -> list:
    from tools.dev_tools import list_projects
    return list_projects()


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKER THREAD
# ═══════════════════════════════════════════════════════════════════════════════
class AriaWorker(QThread):
    def __init__(self):
        super().__init__()
        self._running = True

    def _tool_executor(self, action: str, params: dict) -> str:
        fn = TOOL_MAP.get(action)
        if fn is None:
            return f"No tool named '{action}'."
        try:
            return fn(**params)
        except Exception as e:
            return f"Tool error: {e}"

    def _on_command(self, text: str):
        if not text.strip():
            return True

        # Dismiss
        text_lower = text.lower()
        if any(phrase in text_lower for phrase in DISMISS_PHRASES):
            signals.status.emit("sleeping")
            signals.hide_overlay.emit()
            _speak("See you later.")
            return False   # signals session_manager to end loop

        signals.log.emit(text, "user")
        signals.status.emit("thinking")

        # User workflows first
        cfg = get_config()
        wf = cfg.find_matching_workflow(text)
        if wf:
            signals.log.emit(f"Running workflow: {wf['name']}", "system")
            _speak(f"Running {wf['name']}.")
            for step in wf["steps"]:
                result = self._tool_executor(step["action"], step.get("params", {}))
                signals.status.emit("speaking")
                _speak(result)
            signals.status.emit("listening")
            return True

        # Agentic loop — brain handles multi-step reasoning internally
        final_text = ask_gemini(text, self._tool_executor, speak_fn=_speak)
        signals.status.emit("speaking")
        _speak(final_text)
        signals.status.emit("listening")
        return True

    def _on_wake(self) -> None:
        reset_conversation()   # fresh context each session
        signals.status.emit("listening")
        signals.log.emit("Aria activated", "system")
        signals.show_overlay.emit()
        _speak_male("Hey Sir, what can I do for you?")
        SessionManager(self._on_command).start()
        signals.hide_overlay.emit()   # no-op if dismissed manually
        signals.status.emit("sleeping")

    def run(self) -> None:
        signals.status.emit("sleeping")
        time.sleep(2)   # let startup noise settle before listening
        while self._running:
            try:
                listen_for_wake_word()
                if self._running:
                    self._on_wake()
            except Exception as e:
                if self._running:
                    signals.log.emit(f"Error: {e}. Restarting…", "system")
                    time.sleep(1)

    def stop(self) -> None:
        self._running = False
        self.terminate()
        self.wait(2000)


# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE WAVE WIDGET
# ═══════════════════════════════════════════════════════════════════════════════
class VoiceWaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self._n = 30
        self._bars = [0.04] * self._n
        self._active = False
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(45)

    def set_active(self, active: bool):
        self._active = active

    def _tick(self):
        mid = self._n / 2
        if self._active:
            for i in range(self._n):
                center = 1.0 - abs(i - mid) / mid * 0.45
                self._bars[i] = random.uniform(0.12, 1.0) * center
        else:
            self._bars = [max(0.03, b * 0.72) for b in self._bars]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        w, h = self.width(), self.height()
        step = w / self._n
        bar_w = step * 0.56
        for i, ratio in enumerate(self._bars):
            bh = max(3, ratio * h * 0.92)
            x  = i * step + (step - bar_w) / 2
            y  = (h - bh) / 2
            a  = int(60 + ratio * 195)
            r  = int(110 + ratio * 50)
            g  = int(40  + ratio * 15)
            b  = int(210 + ratio * 45)
            p.setBrush(QBrush(QColor(r, g, b, a)))
            p.drawRoundedRect(QRectF(x, y, bar_w, bh), 2, 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  DIGITAL FACE WIDGET
# ═══════════════════════════════════════════════════════════════════════════════
class DigitalFaceWidget(QWidget):
    _STATE_COLORS = {
        "sleeping": QColor(80, 60, 140),
        "listening": QColor(16, 185, 129),
        "thinking":  QColor(245, 158, 11),
        "speaking":  QColor(139, 92, 246),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self._state      = "sleeping"
        self._frame      = 0
        self._blink      = False
        self._mouth_h    = 0.0
        self._mouth_dir  = 1
        self._scan_angle = 0.0
        self._think_phase = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(40)

    def set_state(self, state: str):
        self._state = state

    def _tick(self):
        self._frame += 1
        if self._state == "speaking":
            self._mouth_h = min(1.0, self._mouth_h + 0.14 * self._mouth_dir)
            if self._mouth_h >= 1.0: self._mouth_dir = -1
            elif self._mouth_h <= 0.0: self._mouth_dir = 1
        else:
            self._mouth_h = max(0.0, self._mouth_h - 0.07)

        if self._state == "thinking":
            self._scan_angle = (self._scan_angle + 5) % 360
            self._think_phase = (self._think_phase + 0.08) % (2 * math.pi)

        self._blink = (self._state != "sleeping") and (self._frame % 75 < 4)
        self.update()

    @staticmethod
    def _hex_pts(cx, cy, r):
        return [QPointF(cx + r * math.cos(math.radians(-90 + 60*i)),
                        cy + r * math.sin(math.radians(-90 + 60*i)))
                for i in range(6)]

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 12
        ac = self._STATE_COLORS.get(self._state, QColor(139, 92, 246))

        # Outer glow
        glow = QColor(ac); glow.setAlpha(22)
        p.setBrush(QBrush(glow)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF(self._hex_pts(cx, cy, r + 11)))

        # Hex face
        p.setBrush(QBrush(QColor(10, 10, 20)))
        p.setPen(QPen(ac, 2))
        p.drawPolygon(QPolygonF(self._hex_pts(cx, cy, r)))

        # Hex vertex dots
        dot_c = QColor(ac); dot_c.setAlpha(100)
        p.setBrush(QBrush(dot_c)); p.setPen(Qt.PenStyle.NoPen)
        for pt in self._hex_pts(cx, cy, r):
            p.drawEllipse(QRectF(pt.x()-2, pt.y()-2, 4, 4))

        # Thinking arc
        if self._state == "thinking":
            pen = QPen(QColor(245, 158, 11, 200), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            ar = r - 7
            rect = QRectF(cx-ar, cy-ar, ar*2, ar*2)
            p.drawArc(rect, int(self._scan_angle*16), 100*16)
            p.drawArc(rect, int((self._scan_angle+180)*16), 100*16)

        # Eyes
        ey   = cy - r * 0.18
        ex_o = r * 0.32
        ew   = r * 0.22
        eh   = r * 0.20

        def eye(ex, ratio):
            h_ = max(2, eh * ratio)
            p.setBrush(QBrush(ac)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(ex - ew/2, ey - h_/2, ew, h_), 3, 3)

        if self._state == "sleeping":
            eye(cx - ex_o, 0.12); eye(cx + ex_o, 0.12)
        elif self._blink:
            eye(cx - ex_o, 0.10); eye(cx + ex_o, 0.10)
        elif self._state == "thinking":
            off = math.sin(self._think_phase) * 3
            eye(cx - ex_o + off, 0.65); eye(cx + ex_o + off, 0.65)
        else:
            eye(cx - ex_o, 1.0); eye(cx + ex_o, 1.0)

        # Mouth
        my    = cy + r * 0.30
        mw    = r * 0.50
        if self._state == "speaking":
            mh = max(3, self._mouth_h * r * 0.24)
            p.setBrush(QBrush(ac)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(cx - mw/2, my - mh/2, mw, mh), 3, 3)
        elif self._state == "sleeping":
            pen = QPen(ac, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawLine(QPointF(cx - mw/2, my), QPointF(cx + mw/2, my))
        else:
            path = QPainterPath()
            path.moveTo(cx - mw/2, my)
            path.quadTo(cx, my + r*0.11, cx + mw/2, my)
            pen = QPen(ac, 2); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)


# ═══════════════════════════════════════════════════════════════════════════════
#  ARIA OVERLAY  — slides in from top of screen
# ═══════════════════════════════════════════════════════════════════════════════
class AriaOverlay(QWidget):
    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self._ow, self._oh = 430, 490
        self._sx = (screen.width() - self._ow) // 2
        self._sy_shown  = 0
        self._sy_hidden = -self._oh
        self._shown = False
        self.setFixedSize(self._ow, self._oh)
        self.move(self._sx, self._sy_hidden)
        # Show once so Qt considers the window active — it stays above the screen
        # until slide_in animates it down. Never call hide() to avoid race conditions.
        self.show()

        self._anim = QPropertyAnimation(self, b"pos")
        self._anim.setDuration(430)

        self._build_ui()
        signals.log.connect(self._append)
        signals.status.connect(self._on_status)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        panel = QFrame(self)
        panel.setFixedSize(self._ow, self._oh)
        panel.setObjectName("overlay_panel")
        panel.setStyleSheet("""
            QFrame#overlay_panel {
                background: rgba(10, 10, 20, 248);
                border: 1px solid rgba(139, 92, 246, 0.55);
                border-top: none;
                border-bottom-left-radius: 24px;
                border-bottom-right-radius: 24px;
            }
        """)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(18, 10, 18, 16)
        lay.setSpacing(6)

        # Status label (top center)
        self._status_lbl = QLabel("SLEEPING")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "color:#6B7280; font-size:10px; font-weight:700; letter-spacing:3px;"
        )
        lay.addWidget(self._status_lbl)

        # Face
        face_row = QHBoxLayout()
        face_row.addStretch()
        self._face = DigitalFaceWidget()
        face_row.addWidget(self._face)
        face_row.addStretch()
        lay.addLayout(face_row)

        # Voice waves
        self._waves = VoiceWaveWidget()
        lay.addWidget(self._waves)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:rgba(139,92,246,0.25);max-height:1px;border:none;")
        lay.addWidget(div)

        # Chat log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #D1D5DB;
                font-size: 12px;
                padding: 2px 4px;
            }
            QScrollBar:vertical { width:4px; background:transparent; }
            QScrollBar::handle:vertical { background:rgba(139,92,246,0.4); border-radius:2px; }
        """)
        lay.addWidget(self._log, 1)

        # Hint
        hint = QLabel("Say  \"go for now\"  to hide")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color:#374151; font-size:10px;")
        lay.addWidget(hint)

        outer.addWidget(panel)

    def _append(self, message: str, role: str):
        cfg = {"user": ("#60A5FA","You"), "aria": ("#A78BFA","Aria"), "system": ("#374151","·")}
        color, label = cfg.get(role, ("#9CA3AF","?"))
        self._log.insertHtml(
            f'<p style="margin:2px 0">'
            f'<span style="color:{color};font-weight:600">{label}:</span> '
            f'<span style="color:#D1D5DB">{message}</span></p>'
        )
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_status(self, s: str):
        labels = {"sleeping":"SLEEPING","listening":"LISTENING",
                  "thinking":"THINKING","speaking":"SPEAKING"}
        colors = {"sleeping":"#4B5563","listening":"#10B981",
                  "thinking":"#F59E0B","speaking":"#A78BFA"}
        self._status_lbl.setText(labels.get(s, s.upper()))
        self._status_lbl.setStyleSheet(
            f"color:{colors.get(s,'#9CA3AF')}; font-size:10px; font-weight:700; letter-spacing:3px;"
        )
        self._face.set_state(s)
        self._waves.set_active(s == "speaking")

    def slide_in(self):
        if self._shown:
            return
        self._shown = True
        self._anim.stop()
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.setStartValue(QPoint(self._sx, self._sy_hidden))
        self._anim.setEndValue(QPoint(self._sx, self._sy_shown))
        self._anim.start()

    def slide_out(self):
        if not self._shown:
            return
        self._shown = False
        self._anim.stop()
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.setStartValue(QPoint(self._sx, self._sy_shown))
        self._anim.setEndValue(QPoint(self._sx, self._sy_hidden))
        self._anim.start()  # slides back above screen — no hide() needed


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS WINDOW — workflows, apps, settings
# ═══════════════════════════════════════════════════════════════════════════════
_STATUS_LABEL = {"sleeping":"Sleeping","listening":"Listening…",
                 "thinking":"Thinking…","speaking":"Speaking…"}

STYLE = """
QMainWindow,QWidget#root{background:#0D0D12}
QWidget{font-family:"SF Pro Display",Arial,sans-serif;color:#E5E5EA}
QTabWidget::pane{border:1px solid #28283A;border-radius:10px;background:#0D0D12}
QTabBar::tab{background:#16161F;color:#6B7280;padding:8px 20px;border-radius:6px 6px 0 0;margin-right:2px;font-size:13px}
QTabBar::tab:selected{background:#7C3AED;color:#FFF;font-weight:600}
QTabBar::tab:hover{background:#28283A;color:#E5E5EA}
QTextEdit{background:#16161F;border:1px solid #28283A;border-radius:10px;color:#E5E5EA;padding:10px;font-size:13px}
QLineEdit,QSpinBox,QComboBox{background:#16161F;border:1px solid #28283A;border-radius:6px;color:#E5E5EA;padding:6px 10px;font-size:13px}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus{border-color:#7C3AED}
QListWidget{background:#16161F;border:1px solid #28283A;border-radius:8px;color:#E5E5EA;font-size:13px}
QListWidget::item{padding:10px 12px;border-radius:6px}
QListWidget::item:selected{background:#7C3AED;color:#FFF}
QListWidget::item:hover{background:#28283A}
QTableWidget{background:#16161F;border:1px solid #28283A;border-radius:8px;gridline-color:#28283A;color:#E5E5EA;font-size:13px}
QTableWidget::item{padding:8px}
QTableWidget::item:selected{background:#7C3AED}
QHeaderView::section{background:#1E1E2A;color:#6B7280;padding:8px;border:none;font-size:12px;font-weight:600}
QPushButton{background:#7C3AED;color:#FFF;border:none;border-radius:7px;padding:8px 16px;font-size:13px;font-weight:600}
QPushButton:hover{background:#6D28D9}
QPushButton:pressed{background:#5B21B6}
QPushButton#secondary{background:transparent;border:1px solid #28283A;color:#9CA3AF}
QPushButton#secondary:hover{background:#1E1E2A;color:#E5E5EA}
QPushButton#danger{background:#DC2626}
QPushButton#danger:hover{background:#B91C1C}
QFrame#divider{background:#28283A;max-height:1px;border:none}
QLabel#sectionTitle{color:#FFF;font-size:15px;font-weight:700}
QLabel#hint{color:#4B4B6A;font-size:12px}
QDialog{background:#0D0D12}
QScrollArea{border:none;background:transparent}
"""


class StepDialog(QDialog):
    def __init__(self, parent=None, step: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Step"); self.setMinimumWidth(400); self.setStyleSheet(STYLE)
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(20,20,20,20)
        form = QFormLayout(); form.setSpacing(8)
        self._action = QComboBox(); self._action.addItems(sorted(ACTION_SCHEMA.keys()))
        form.addRow("Action:", self._action); lay.addLayout(form)
        self._params_area = QWidget()
        self._params_lay  = QFormLayout(self._params_area); self._params_lay.setSpacing(8)
        lay.addWidget(self._params_area)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); lay.addWidget(btns)
        self._action.currentTextChanged.connect(self._rebuild)
        if step:
            idx = self._action.findText(step["action"])
            if idx >= 0: self._action.setCurrentIndex(idx)
            self._rebuild(step["action"], prefill=step.get("params", {}))
        else:
            self._rebuild(self._action.currentText())

    def _rebuild(self, action: str, prefill: dict = None):
        while self._params_lay.rowCount(): self._params_lay.removeRow(0)
        self._widgets: dict = {}
        for key, label, kind in ACTION_SCHEMA.get(action, []):
            if kind == "number":
                w = QSpinBox(); w.setRange(1, 9999)
                if prefill and key in prefill: w.setValue(int(prefill[key]))
            elif kind.startswith("choice:"):
                w = QComboBox(); w.addItems(kind.split(":")[1:])
                if prefill and key in prefill:
                    idx = w.findText(prefill[key])
                    if idx >= 0: w.setCurrentIndex(idx)
            elif kind == "app_list":
                w = QComboBox(); w.setEditable(True); w.addItems(_app_list())
                if prefill and key in prefill:
                    idx = w.findText(prefill[key])
                    w.setCurrentIndex(idx) if idx >= 0 else w.setCurrentText(prefill[key])
            elif kind == "project_list":
                w = QComboBox(); w.setEditable(True); w.addItems(_project_list())
                if prefill and key in prefill:
                    idx = w.findText(prefill[key])
                    w.setCurrentIndex(idx) if idx >= 0 else w.setCurrentText(prefill[key])
            else:
                w = QLineEdit()
                if prefill and key in prefill: w.setText(str(prefill[key]))
            self._params_lay.addRow(label + ":", w)
            self._widgets[key] = w

    def get_step(self) -> dict:
        params = {}
        for key, w in self._widgets.items():
            if isinstance(w, QSpinBox): params[key] = w.value()
            elif isinstance(w, QComboBox): params[key] = w.currentText().strip()
            else: params[key] = w.text().strip()
        return {"action": self._action.currentText(), "params": params}


class WorkflowsTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QHBoxLayout(self); root.setContentsMargins(16,16,16,16); root.setSpacing(12)
        left = QVBoxLayout(); left.setSpacing(8)
        lbl = QLabel("Workflows"); lbl.setObjectName("sectionTitle"); left.addWidget(lbl)
        hint = QLabel("Say the trigger phrase to run it"); hint.setObjectName("hint"); left.addWidget(hint)
        self._list = QListWidget(); self._list.setFixedWidth(200)
        self._list.currentItemChanged.connect(self._on_select); left.addWidget(self._list)
        add_btn = QPushButton("+ New Workflow"); add_btn.clicked.connect(self._new_workflow)
        left.addWidget(add_btn); root.addLayout(left)
        div = QFrame(); div.setObjectName("divider"); div.setFrameShape(QFrame.Shape.VLine)
        div.setStyleSheet("background:#28283A;max-width:1px;border:none"); root.addWidget(div)
        right = QVBoxLayout(); right.setSpacing(10)
        self._right = QWidget(); right_inner = QVBoxLayout(self._right)
        right_inner.setSpacing(10); right_inner.setContentsMargins(0,0,0,0)
        form = QFormLayout(); form.setSpacing(8)
        self._name_edit = QLineEdit(); self._name_edit.setPlaceholderText("e.g. Prepare Design Work")
        self._trig_edit = QLineEdit(); self._trig_edit.setPlaceholderText("e.g. prepare design work")
        form.addRow("Name:", self._name_edit); form.addRow("Trigger:", self._trig_edit)
        right_inner.addLayout(form)
        hint2 = QLabel("Steps — executed in order when trigger is spoken")
        hint2.setObjectName("hint"); right_inner.addWidget(hint2)
        self._steps_list = QListWidget(); self._steps_list.setMinimumHeight(150); right_inner.addWidget(self._steps_list)
        sbar = QHBoxLayout(); sbar.setSpacing(8)
        as_ = QPushButton("+ Add Step"); as_.clicked.connect(self._add_step)
        es_ = QPushButton("Edit"); es_.setObjectName("secondary"); es_.clicked.connect(self._edit_step)
        ds_ = QPushButton("Remove"); ds_.setObjectName("secondary"); ds_.clicked.connect(self._del_step)
        sbar.addWidget(as_); sbar.addWidget(es_); sbar.addWidget(ds_); sbar.addStretch()
        right_inner.addLayout(sbar)
        abar = QHBoxLayout(); abar.setSpacing(8)
        save_btn = QPushButton("Save Workflow"); save_btn.clicked.connect(self._save)
        del_btn  = QPushButton("Delete"); del_btn.setObjectName("danger"); del_btn.clicked.connect(self._delete)
        abar.addStretch(); abar.addWidget(save_btn); abar.addWidget(del_btn)
        right_inner.addLayout(abar)
        right.addWidget(self._right); right.addStretch(); root.addLayout(right)
        self._cur_id: str | None = None; self._steps: list = []
        self._refresh_list(); self._right.setEnabled(False)

    def _refresh_list(self):
        self._list.clear()
        for wf in get_config().workflows:
            item = QListWidgetItem(wf["name"])
            item.setData(Qt.ItemDataRole.UserRole, wf["id"]); self._list.addItem(item)

    def _on_select(self, item):
        if item is None: self._right.setEnabled(False); return
        wf = next((w for w in get_config().workflows if w["id"] == item.data(Qt.ItemDataRole.UserRole)), None)
        if not wf: return
        self._cur_id = wf["id"]; self._name_edit.setText(wf["name"]); self._trig_edit.setText(wf["trigger"])
        self._steps = list(wf["steps"]); self._refresh_steps(); self._right.setEnabled(True)

    def _refresh_steps(self):
        self._steps_list.clear()
        for i, s in enumerate(self._steps, 1):
            params = ", ".join(f"{k}={v}" for k,v in s.get("params",{}).items())
            self._steps_list.addItem(f"{i}. {s['action']}" + (f"  →  {params}" if params else ""))

    def _new_workflow(self):
        self._cur_id = None; self._name_edit.setText(""); self._trig_edit.setText("")
        self._steps = []; self._refresh_steps(); self._right.setEnabled(True); self._name_edit.setFocus()

    def _add_step(self):
        d = StepDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted: self._steps.append(d.get_step()); self._refresh_steps()

    def _edit_step(self):
        row = self._steps_list.currentRow()
        if row < 0: return
        d = StepDialog(self, step=self._steps[row])
        if d.exec() == QDialog.DialogCode.Accepted: self._steps[row] = d.get_step(); self._refresh_steps()

    def _del_step(self):
        row = self._steps_list.currentRow()
        if row >= 0: self._steps.pop(row); self._refresh_steps()

    def _save(self):
        name = self._name_edit.text().strip(); trig = self._trig_edit.text().strip()
        if not name or not trig: QMessageBox.warning(self,"Missing","Name and trigger are required."); return
        cfg = get_config()
        if self._cur_id: cfg.update_workflow(self._cur_id, name, trig, self._steps)
        else: wf = cfg.add_workflow(name, trig, self._steps); self._cur_id = wf["id"]
        self._refresh_list()
        for i in range(self._list.count()):
            if self._list.item(i).data(Qt.ItemDataRole.UserRole) == self._cur_id:
                self._list.setCurrentRow(i); break

    def _delete(self):
        if not self._cur_id: return
        if QMessageBox.question(self,"Delete","Delete this workflow?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        get_config().delete_workflow(self._cur_id); self._cur_id = None; self._steps = []
        self._right.setEnabled(False); self._refresh_list()


class AppDialog(QDialog):
    def __init__(self, parent=None, app: dict = None):
        super().__init__(parent)
        self.setWindowTitle("App"); self.setMinimumWidth(440); self.setStyleSheet(STYLE)
        lay = QVBoxLayout(self); lay.setSpacing(12); lay.setContentsMargins(20,20,20,20)
        form = QFormLayout(); form.setSpacing(8)
        self._name = QLineEdit(); self._name.setPlaceholderText("Spotify")
        self._keys = QLineEdit(); self._keys.setPlaceholderText("spotify, music player")
        self._path = QLineEdit(); self._path.setPlaceholderText("/Applications/Spotify.app")
        browse = QPushButton("Browse…"); browse.setObjectName("secondary"); browse.clicked.connect(self._browse)
        prow = QHBoxLayout(); prow.addWidget(self._path); prow.addWidget(browse)
        form.addRow("Display name:", self._name)
        form.addRow("Voice triggers\n(comma separated):", self._keys)
        form.addRow("App path:", prow)
        lay.addLayout(form)
        lay.addWidget(QLabel("Tip: voice triggers are the words you say to open this app."))
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject); lay.addWidget(btns)
        if app: self._name.setText(app["name"]); self._keys.setText(app["triggers"]); self._path.setText(app["path"])

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self,"Select app","/Applications","Apps (*.app *.exe);;All (*)")
        if path: self._path.setText(path)

    def values(self): return self._name.text().strip(), self._keys.text().strip(), self._path.text().strip()


class AppsTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        lbl = QLabel("Custom Apps"); lbl.setObjectName("sectionTitle"); lay.addWidget(lbl)
        hint = QLabel("Add apps not in the default list — Aria opens them by voice trigger.")
        hint.setObjectName("hint"); hint.setWordWrap(True); lay.addWidget(hint)
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Display Name","Voice Triggers","Path"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._table)
        bar = QHBoxLayout(); bar.setSpacing(8)
        add_btn = QPushButton("+ Add App"); add_btn.clicked.connect(self._add)
        edt_btn = QPushButton("Edit"); edt_btn.setObjectName("secondary"); edt_btn.clicked.connect(self._edit)
        del_btn = QPushButton("Delete"); del_btn.setObjectName("danger"); del_btn.clicked.connect(self._delete)
        bar.addWidget(add_btn); bar.addWidget(edt_btn); bar.addWidget(del_btn); bar.addStretch()
        lay.addLayout(bar); self._refresh()

    def _refresh(self):
        self._table.setRowCount(0)
        for app in get_config().custom_apps:
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r,0,QTableWidgetItem(app["name"]))
            self._table.setItem(r,1,QTableWidgetItem(app["triggers"]))
            self._table.setItem(r,2,QTableWidgetItem(app["path"]))
            self._table.item(r,0).setData(Qt.ItemDataRole.UserRole, app["id"])

    def _add(self):
        d = AppDialog(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            n, k, p = d.values()
            if n and k and p: get_config().add_app(n, k, p); self._refresh()

    def _edit(self):
        row = self._table.currentRow()
        if row < 0: return
        aid = self._table.item(row,0).data(Qt.ItemDataRole.UserRole)
        app = next((a for a in get_config().custom_apps if a["id"] == aid), None)
        if not app: return
        d = AppDialog(self, app=app)
        if d.exec() == QDialog.DialogCode.Accepted:
            n, k, p = d.values()
            if n and k and p: get_config().update_app(aid, n, k, p); self._refresh()

    def _delete(self):
        row = self._table.currentRow()
        if row < 0: return
        if QMessageBox.question(self,"Delete","Delete this app?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        get_config().delete_app(self._table.item(row,0).data(Qt.ItemDataRole.UserRole)); self._refresh()


class SettingsTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        lbl = QLabel("Settings"); lbl.setObjectName("sectionTitle"); lay.addWidget(lbl)
        form = QFormLayout(); form.setSpacing(12)
        from config import GROQ_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, ELEVENLABS_ARABIC_VOICE_ID
        self._groq    = QLineEdit(GROQ_API_KEY);          self._groq.setEchoMode(QLineEdit.EchoMode.Password)
        self._el      = QLineEdit(ELEVENLABS_API_KEY);     self._el.setEchoMode(QLineEdit.EchoMode.Password)
        self._voice   = QLineEdit(ELEVENLABS_VOICE_ID)
        self._ar_voice= QLineEdit(ELEVENLABS_ARABIC_VOICE_ID)
        self._ar_voice.setPlaceholderText("Leave empty to use Edge TTS (free Moroccan voice)")
        form.addRow("Groq API Key:",              self._groq)
        form.addRow("ElevenLabs API Key:",        self._el)
        form.addRow("ElevenLabs Voice (English):", self._voice)
        form.addRow("ElevenLabs Voice (Arabic):",  self._ar_voice)
        lay.addLayout(form)
        hint = QLabel("Changes take effect after restarting Aria.")
        hint.setObjectName("hint"); lay.addWidget(hint)
        save = QPushButton("Save Settings"); save.clicked.connect(self._save)
        save.setFixedWidth(140); lay.addWidget(save)
        lay.addStretch()
        self._lbl = QLabel(""); self._lbl.setObjectName("hint"); lay.addWidget(self._lbl)

    def _save(self):
        import re
        path = os.path.join(ROOT, "config.py")
        with open(path) as f: src = f.read()
        def rep(s, key, val):
            return re.sub(rf'({key}\s*=\s*[^.]*?\(\w+,\s*")[^"]*(")', rf'\g<1>{val}\2', s)
        src = rep(src, "GROQ_API_KEY",       self._groq.text().strip())
        src = rep(src, "ELEVENLABS_API_KEY", self._el.text().strip())
        src = re.sub(r'(ELEVENLABS_VOICE_ID\s*=\s*")[^"]*(")',
                     rf'\g<1>{self._voice.text().strip()}\2', src)
        src = re.sub(r'(ELEVENLABS_ARABIC_VOICE_ID\s*=\s*")[^"]*(")',
                     rf'\g<1>{self._ar_voice.text().strip()}\2', src)
        with open(path, "w") as f: f.write(src)
        self._lbl.setText("Saved — restart Aria to apply.")


class ChatHistoryTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,12); lay.setSpacing(10)
        self._log = QTextEdit(); self._log.setReadOnly(True); lay.addWidget(self._log)
        bar = QHBoxLayout()
        clr = QPushButton("Clear"); clr.setObjectName("secondary"); clr.setFixedWidth(80)
        clr.clicked.connect(self._log.clear)
        bar.addStretch(); bar.addWidget(clr); lay.addLayout(bar)
        signals.log.connect(self._append)

    def _append(self, message: str, role: str):
        cfg = {"user":("#60A5FA","You"),"aria":("#A78BFA","Aria"),"system":("#4B4B6A","·")}
        color, label = cfg.get(role, ("#9CA3AF","?"))
        self._log.insertHtml(
            f'<p style="margin:4px 0"><span style="color:{color};font-weight:600">{label}:</span>'
            f'&nbsp;<span style="color:#E5E5EA">{message}</span></p>')
        sb = self._log.verticalScrollBar(); sb.setValue(sb.maximum())


def _make_icon(size=64, bg="#7C3AED", letter="A") -> QIcon:
    px = QPixmap(size, size); px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(bg))); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size-4, size-4)
    p.setPen(QPen(QColor("#FFF")))
    f = QFont("Arial", size//3, QFont.Weight.Bold); p.setFont(f)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, letter); p.end()
    return QIcon(px)


class SpotifyTab(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(16,16,16,16); lay.setSpacing(10)
        lbl = QLabel("Spotify Playlists"); lbl.setObjectName("sectionTitle"); lay.addWidget(lbl)
        hint = QLabel(
            "Save playlists or tracks so Aria can play them by voice.\n"
            "Get the URI: right-click a playlist/track in Spotify → Share → Copy Spotify URI\n"
            "You can also paste the open.spotify.com link directly — Aria converts it automatically."
        )
        hint.setObjectName("hint"); hint.setWordWrap(True); lay.addWidget(hint)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Playlist Name", "Spotify URI"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self._table)
        bar = QHBoxLayout(); bar.setSpacing(8)
        add_btn = QPushButton("+ Add Playlist"); add_btn.clicked.connect(self._add)
        del_btn = QPushButton("Delete"); del_btn.setObjectName("danger"); del_btn.clicked.connect(self._delete)
        bar.addWidget(add_btn); bar.addWidget(del_btn); bar.addStretch()
        lay.addLayout(bar); self._refresh()

    def _refresh(self):
        self._table.setRowCount(0)
        for p in get_config().spotify_playlists:
            r = self._table.rowCount(); self._table.insertRow(r)
            self._table.setItem(r, 0, QTableWidgetItem(p["name"]))
            self._table.setItem(r, 1, QTableWidgetItem(p["uri"]))
            self._table.item(r, 0).setData(Qt.ItemDataRole.UserRole, p["id"])

    def _add(self):
        d = QDialog(self); d.setWindowTitle("Add Spotify Playlist")
        d.setMinimumWidth(440)
        form = QFormLayout(d); form.setSpacing(10); form.setContentsMargins(16,16,16,16)
        name_edit = QLineEdit(); name_edit.setPlaceholderText("e.g. favourites, chill, workout")
        uri_edit  = QLineEdit(); uri_edit.setPlaceholderText("spotify:playlist:37i9dQZF1DX...")
        form.addRow("Playlist Name:", name_edit)
        form.addRow("Spotify URI:",   uri_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(d.accept); btns.rejected.connect(d.reject)
        form.addRow(btns)
        if d.exec() == QDialog.DialogCode.Accepted:
            n, u = name_edit.text().strip(), uri_edit.text().strip()
            if n and u: get_config().add_spotify_playlist(n, u); self._refresh()

    def _delete(self):
        row = self._table.currentRow()
        if row < 0: return
        if QMessageBox.question(self, "Delete", "Remove this playlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        get_config().delete_spotify_playlist(self._table.item(row, 0).data(Qt.ItemDataRole.UserRole))
        self._refresh()


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aria Settings"); self.setMinimumSize(620, 600)
        self.resize(680, 650); self.setWindowIcon(_make_icon(64))
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        lay = QVBoxLayout(root); lay.setContentsMargins(16,16,16,16); lay.setSpacing(12)
        tabs = QTabWidget()
        tabs.addTab(ChatHistoryTab(), "Chat History")
        tabs.addTab(WorkflowsTab(),   "Workflows")
        tabs.addTab(AppsTab(),        "Apps")
        tabs.addTab(SpotifyTab(),     "Spotify")
        tabs.addTab(SettingsTab(),    "Settings")
        lay.addWidget(tabs)

    def closeEvent(self, e): e.ignore(); self.hide()


# ═══════════════════════════════════════════════════════════════════════════════
#  SYSTEM TRAY
# ═══════════════════════════════════════════════════════════════════════════════
class AriaTray(QSystemTrayIcon):
    def __init__(self, settings: SettingsWindow, app: QApplication):
        super().__init__(_make_icon(64), app)
        self._win = settings; self._app = app
        self.setToolTip("Aria — AI Assistant")
        menu = QMenu()
        menu.addAction("Settings").triggered.connect(self._show)
        menu.addSeparator()
        menu.addAction("Quit Aria").triggered.connect(self._quit)
        self.setContextMenu(menu)
        self.activated.connect(lambda r: self._show() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        signals.status.connect(lambda s: self.setToolTip(f"Aria — {_STATUS_LABEL.get(s,s)}"))

    def _show(self):
        self._win.show(); self._win.raise_(); self._win.activateWindow()

    def _quit(self):
        self.showMessage("Aria","Shutting down…",QSystemTrayIcon.MessageIcon.Information,1000)
        QTimer.singleShot(400, self._do_quit)

    def _do_quit(self):
        if hasattr(self, "_worker"): self._worker.stop()
        self._app.quit()


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Aria")
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(STYLE)

    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except ImportError:
            pass

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available."); sys.exit(1)

    overlay = AriaOverlay()
    signals.show_overlay.connect(overlay.slide_in)
    signals.hide_overlay.connect(overlay.slide_out)

    settings = SettingsWindow()
    tray = AriaTray(settings, app)
    tray.show()
    tray.showMessage("Aria is running",
                     "Say the wake word or clap twice to activate.",
                     QSystemTrayIcon.MessageIcon.NoIcon, 3000)

    if sys.platform == "darwin":
        start_global_allow_watcher()   # auto-clicks Allow on all macOS permission popups

    worker = AriaWorker()
    tray._worker = worker
    worker.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
