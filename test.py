import sys
import os
import time
import datetime
import threading
import json
import queue
import subprocess
import requests
import keyboard
import pyperclip
import io
import ollama
import pyttsx3
import glob
import base64
import atexit

from PyQt6.QtWidgets import (
    QApplication, QLabel, QVBoxLayout, QWidget, QHBoxLayout, 
    QPushButton, QSystemTrayIcon, QMenu, QFrame,
    QGraphicsDropShadowEffect, QTextBrowser, QTextEdit, QStackedWidget,
    QSizeGrip, QScrollArea, QFileDialog, QDialog, QInputDialog, 
    QLineEdit, QFormLayout, QCheckBox, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QPoint, pyqtSignal, QTimer, QThread, QPropertyAnimation, 
    QSize, QObject, QRect, QStandardPaths
)
from PyQt6.QtGui import (
    QFont, QIcon, QPixmap, QPainter, QColor, QAction, 
    QTextCursor, QWheelEvent, QMouseEvent
)
from PIL import Image, ImageGrab

# ==============================================================================
# 1. 全局配置 & 样式
# ==============================================================================

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
SAVE_DIR = os.path.join(BASE_DIR, "saved_translations")

class ConfigManager:
    DEFAULT = {
        "hotkey": "ctrl+alt+f",
        "use_online": False,
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "online_model": "gpt-4o",
        "local_model": "qwen3-vl:8b"
    }

    @classmethod
    def load(cls):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                    return {**cls.DEFAULT, **json.load(f)}
            except: pass
        return cls.DEFAULT.copy()

    @staticmethod
    def save(config):
        try:
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except: pass

STYLESHEET = """
    QFrame#MainContainer { background-color: #202020; border: 1px solid #3e3e3e; border-radius: 12px; }
    QLabel#Title { color: #aaaaaa; font-weight: bold; font-size: 11px; }
    QPushButton#WinBtn { background: transparent; color: #888; border: none; font-size: 14px; border-radius: 4px; }
    QPushButton#WinBtn:hover { background: #c42b1c; color: white; }
    QLabel#ImagePreview { background-color: #000; border: 1px solid #333; border-radius: 8px; }
    QLabel#ImagePreview:hover { border: 1px solid #0078d4; }
    QTextBrowser { background: transparent; border: none; padding: 5px; }
    QTextBrowser#TransBrowser { color: #ffffff; font-size: 15px; line-height: 1.6; }
    QTextBrowser#RawBrowser { color: #999999; font-size: 13px; font-style: italic; }
    QFrame#Section { background: #2b2b2b; border-radius: 8px; border: 1px solid #383838; }
    QPushButton.ToolBtn { background: transparent; color: #cccccc; border: 1px solid transparent; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 13px; }
    QPushButton.ToolBtn:hover { background-color: #3e3e42; border: 1px solid #555; color: white; }
    QPushButton#FavBtn:checked { color: #ffd700; border-color: #ffd700; background-color: rgba(255, 215, 0, 0.1); }
    QPushButton#ChatBtn { color: #5dade2; }
    QPushButton#ChatBtn:hover { color: white; background-color: #0078d4; }
    QTextEdit#ChatInput { background: #2d2d2d; border: 1px solid #3e3e42; border-radius: 18px; color: white; padding: 5px 10px; }
    QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 0px; }
    QScrollBar::handle:vertical { background: #444; min-height: 20px; border-radius: 3px; }
    QScrollBar::handle:vertical:hover { background: #555; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QDialog { background-color: #2b2b2b; color: white; }
    QLabel { color: #ccc; }
    QLineEdit { background: #1e1e1e; border: 1px solid #444; color: white; padding: 5px; border-radius: 4px; }
"""

# ==============================================================================
# 2. 核心服务
# ==============================================================================

class OllamaService:
    _process = None
    _owned = False

    @classmethod
    def check_and_start(cls):
        if cls.is_running(): return
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cls._process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            cls._owned = True
        except: pass

    @classmethod
    def stop(cls):
        if cls._owned and cls._process:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(cls._process.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except: pass

    @staticmethod
    def is_running():
        try: return requests.get("http://127.0.0.1:11434", timeout=0.2).status_code == 200
        except: return False

atexit.register(OllamaService.stop)

class ScreenshotCleaner:
    @staticmethod
    def clean():
        try:
            pp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
            dirs = [os.path.join(pp, "Screenshots"), os.path.join(pp, "屏幕截图")]
            td = next((d for d in dirs if os.path.exists(d)), None)
            if td:
                files = glob.glob(os.path.join(td, '*'))
                if files:
                    latest = max(files, key=os.path.getmtime)
                    if time.time() - os.path.getmtime(latest) < 15: os.remove(latest)
        except: pass

class TTSManager(QObject):
    def __init__(self):
        super().__init__()
        self.queue = queue.Queue()
        self.running = True
        threading.Thread(target=self._worker, daemon=True).start()

    def speak(self, text):
        if text:
            with self.queue.mutex: self.queue.queue.clear()
            self.queue.put(text)

    def _worker(self):
        while self.running:
            try:
                text = self.queue.get(timeout=0.5)
                engine = pyttsx3.init()
                engine.setProperty('rate', 160)
                engine.say(text)
                engine.runAndWait()
                del engine
            except: continue
    def stop(self): self.running = False

class ClipboardPoller(QObject):
    sig_image_found = pyqtSignal(bytes)
    def __init__(self):
        super().__init__()
        self.old_hash = 0
        self.running = False

    def start(self):
        try:
            # 初始快照，避免误触发
            self._get_current_hash()
        except: pass
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _get_current_hash(self):
        """获取当前剪贴板内容的哈希（兼容图片和文件列表）"""
        try:
            content = ImageGrab.grabclipboard()
            if content is None:
                return 0
            if isinstance(content, list): # 文件列表
                return hash(tuple(content)) # 对文件名列表做哈希
            if isinstance(content, Image.Image): # 图片对象
                return hash(content.tobytes())
            return 0
        except: return 0

    def _loop(self):
        t0 = time.time()
        # 轮询 60秒，足够用户操作截图
        while self.running and (time.time() - t0 < 60):
            try:
                content = ImageGrab.grabclipboard()
                
                # 情况1：剪贴板里是图片对象
                if isinstance(content, Image.Image):
                    curr_hash = hash(content.tobytes())
                    if curr_hash != self.old_hash:
                        self.old_hash = curr_hash
                        b = io.BytesIO()
                        content.save(b, "PNG")
                        self.sig_image_found.emit(b.getvalue())
                        ScreenshotCleaner.clean()
                        self.running = False
                        return

                # 情况2：剪贴板里是文件路径（Windows 截图自动保存模式）
                elif isinstance(content, list) and content:
                    curr_hash = hash(tuple(content))
                    if curr_hash != self.old_hash:
                        # 尝试读取第一个文件是否为图片
                        if os.path.isfile(content[0]):
                            try:
                                with Image.open(content[0]) as img:
                                    self.old_hash = curr_hash
                                    b = io.BytesIO()
                                    img.save(b, "PNG")
                                    self.sig_image_found.emit(b.getvalue())
                                    # 注意：这里不自动清理文件，因为它是用户可能手动复制的文件
                                    # 但如果是截图工具生成的，ScreenshotCleaner 会根据时间戳在后台处理
                                    ScreenshotCleaner.clean() 
                                    self.running = False
                                    return
                            except: pass # 不是图片文件，忽略
            except: pass
            time.sleep(0.2)

class OnlineClient:
    @staticmethod
    def chat(config, messages, stream=False):
        headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
        processed = []
        for msg in messages:
            content = msg['content']
            if 'images' in msg and msg['images']:
                b64 = base64.b64encode(msg['images'][0]).decode('utf-8')
                processed.append({"role": msg['role'], "content": [{"type": "text", "text": content}, {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]})
            else:
                processed.append({"role": msg['role'], "content": content})
        
        data = {"model": config['online_model'], "messages": processed, "stream": stream}
        url = f"{config['base_url'].rstrip('/')}/chat/completions"
        return requests.post(url, headers=headers, json=data, stream=stream, timeout=30)

# ==============================================================================
# 3. AI 线程 (Hybrid)
# ==============================================================================

class AIWorker(QThread):
    sig_result = pyqtSignal(str, str)
    sig_model_used = pyqtSignal(str)

    def __init__(self, img_bytes):
        super().__init__()
        self.img_bytes = img_bytes
        self.config = ConfigManager.load()

    def run(self):
        prompt = """
        [INSTRUCTION]
        Mode: FAST / NO THINKING.
        Format Strict:
        【Original】
        <text>
        【Translation】
        <text>
        """
        
        # 1. Try Online
        if self.config['use_online'] and self.config['api_key']:
            try:
                self.sig_model_used.emit(f"Online: {self.config['online_model']}")
                resp = OnlineClient.chat(self.config, [{'role':'user', 'content':prompt, 'images':[self.img_bytes]}], False)
                if resp.status_code == 200:
                    self.parse_emit(resp.json()['choices'][0]['message']['content'])
                    return
            except: pass

        # 2. Try Local
        try:
            local = self.config.get('local_model', 'qwen3-vl:8b')
            self.sig_model_used.emit(f"Local: {local}")
            resp = ollama.chat(model=local, messages=[{'role':'user', 'content':prompt, 'images':[self.img_bytes]}])
            self.parse_emit(resp['message']['content'])
        except Exception as e:
            self.sig_result.emit(f"Error: {e}", "All engines failed.")

    def parse_emit(self, content):
        raw, trans = "...", content
        if "【Translation】" in content:
            parts = content.split("【Translation】")
            trans = parts[1].strip()
            if "【Original】" in parts[0]: raw = parts[0].replace("【Original】", "").strip()
        self.sig_result.emit(raw, trans)

class ChatWorker(QThread):
    sig_chunk = pyqtSignal(str)
    sig_done = pyqtSignal()
    
    def __init__(self, history):
        super().__init__()
        self.history = history
        self.config = ConfigManager.load()

    def run(self):
        if self.config['use_online'] and self.config['api_key']:
            try:
                resp = OnlineClient.chat(self.config, self.history, True)
                if resp.status_code == 200:
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode('utf-8').replace('data: ', '')
                            if decoded != '[DONE]':
                                try:
                                    chunk = json.loads(decoded)['choices'][0]['delta'].get('content', '')
                                    if chunk: self.sig_chunk.emit(chunk)
                                except: pass
                    self.sig_done.emit()
                    return
            except: pass

        try:
            local = self.config.get('local_model', 'qwen3-vl:8b')
            stream = ollama.chat(model=local, messages=self.history, stream=True)
            for chunk in stream:
                c = chunk['message']['content']
                if c: self.sig_chunk.emit(c)
            self.sig_done.emit()
        except: self.sig_done.emit()

# ==============================================================================
# 4. UI 组件
# ==============================================================================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ API Settings")
        self.setFixedSize(400, 300)
        self.layout = QFormLayout(self)
        self.config = ConfigManager.load()
        
        self.chk_online = QCheckBox("Enable Online API (Priority)")
        self.chk_online.setChecked(self.config.get('use_online', False))
        
        self.inp_key = QLineEdit(self.config.get('api_key', ''))
        self.inp_key.setPlaceholderText("sk-...")
        self.inp_key.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.inp_url = QLineEdit(self.config.get('base_url', 'https://api.openai.com/v1'))
        self.inp_model = QLineEdit(self.config.get('online_model', 'gpt-4o'))
        self.inp_local = QLineEdit(self.config.get('local_model', 'qwen3-vl:8b'))
        
        btn = QPushButton("Save Config")
        btn.clicked.connect(self.save)
        btn.setStyleSheet("background:#0078d4;color:white;padding:5px;")
        
        self.layout.addRow(self.chk_online)
        self.layout.addRow("Online Key:", self.inp_key)
        self.layout.addRow("Online URL:", self.inp_url)
        self.layout.addRow("Online Model:", self.inp_model)
        self.layout.addRow("-----", QLabel("-----"))
        self.layout.addRow("Local Model:", self.inp_local)
        self.layout.addRow(btn)

    def save(self):
        self.config.update({
            'use_online': self.chk_online.isChecked(),
            'api_key': self.inp_key.text().strip(),
            'base_url': self.inp_url.text().strip(),
            'online_model': self.inp_model.text().strip(),
            'local_model': self.inp_local.text().strip()
        })
        ConfigManager.save(self.config)
        self.accept()

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.clicked.emit()
        super().mousePressEvent(e)

class ImageLightbox(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: rgba(0,0,0,0.9);")
        
        self.pixmap = pixmap
        self.scale = 1.0
        self.pos_off = QPoint(0,0)
        self.dragging = False
        self.drag_start = QPoint()
        
        self.hint = QLabel("🖱️ 滚轮缩放 | 拖拽 | 双击关闭", self)
        self.hint.setStyleSheet("color:#aaa; font-size:14px; background:transparent;")
        self.hint.move(20,20)
        self.hint.adjustSize()
        self.showMaximized()

    def paintEvent(self, e):
        p = QPainter(self)
        w, h = int(self.pixmap.width()*self.scale), int(self.pixmap.height()*self.scale)
        cx = self.width()//2 + self.pos_off.x() - w//2
        cy = self.height()//2 + self.pos_off.y() - h//2
        p.drawPixmap(cx, cy, w, h, self.pixmap)

    def wheelEvent(self, e):
        self.scale *= 1.1 if e.angleDelta().y() > 0 else 0.9
        self.scale = max(0.1, min(5.0, self.scale))
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start = e.pos()
        else: self.close()

    def mouseMoveEvent(self, e):
        if self.dragging:
            self.pos_off += e.pos() - self.drag_start
            self.drag_start = e.pos()
            self.update()

    def mouseReleaseEvent(self, e): self.dragging = False
    def mouseDoubleClickEvent(self, e): self.close()

class AutoResizingTextEdit(QTextBrowser):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none; color: white; font-size: 13px;")
        self.setHtml(text.replace("\n", "<br>"))
        self.document().contentsChanged.connect(self.adjust_height)
    def adjust_height(self):
        doc_h = self.document().size().height()
        self.setFixedHeight(int(doc_h + 10))

class MessageBubble(QWidget):
    def __init__(self, text, is_user=True, img_bytes=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5,5,5,5)
        
        self.bubble = QFrame()
        bl = QVBoxLayout(self.bubble)
        bl.setContentsMargins(12,10,12,10)
        bl.setSpacing(5)
        
        bg = "#0078d4" if is_user else "#333333"
        self.bubble.setStyleSheet(f"background-color: {bg}; border-radius: 12px;")
        
        if img_bytes:
            l = QLabel()
            p = QPixmap()
            p.loadFromData(img_bytes)
            l.setPixmap(p.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            bl.addWidget(l)
        
        self.text_view = AutoResizingTextEdit(text or "")
        bl.addWidget(self.text_view)
        
        if is_user:
            layout.addStretch()
            layout.addWidget(self.bubble)
        else:
            layout.addWidget(self.bubble)
            layout.addStretch()
        self.bubble.setMaximumWidth(320)

    def update_text(self, text):
        self.text_view.setHtml(text.replace("\n", "<br>"))

class ChatView(QWidget):
    sig_back = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.img_cache = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        top = QWidget()
        top.setFixedHeight(40)
        top.setStyleSheet("border-bottom: 1px solid #333; background: #252526;")
        th = QHBoxLayout(top)
        btn_back = QPushButton("⬅ 返回")
        btn_back.setStyleSheet("color:#aaa; border:none; font-weight:bold;")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.clicked.connect(self.sig_back.emit)
        th.addWidget(btn_back)
        th.addStretch()
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background:transparent; border:none;")
        self.content = QWidget()
        self.chat_layout = QVBoxLayout(self.content)
        self.chat_layout.addStretch()
        self.scroll.setWidget(self.content)
        
        bot = QWidget()
        bh = QHBoxLayout(bot)
        bh.setContentsMargins(10,5,10,10)
        
        self.btn_img = QPushButton("📎")
        self.btn_img.setFixedSize(36,36)
        self.btn_img.setStyleSheet("background:transparent; color:#aaa; border:1px solid #555; border-radius:18px;")
        self.btn_img.clicked.connect(self.pick_img)
        
        self.preview = QLabel()
        self.preview.setFixedSize(36,36)
        self.preview.setVisible(False)
        self.preview.setScaledContents(True)
        self.preview.setStyleSheet("border:1px solid #0078d4; border-radius:4px;")
        
        self.input = QTextEdit()
        self.input.setObjectName("ChatInput")
        self.input.setFixedHeight(36)
        self.input.setPlaceholderText("提问...")
        self.input.installEventFilter(self)
        
        self.btn_send = QPushButton("⬆")
        self.btn_send.setFixedSize(36,36)
        self.btn_send.setStyleSheet("background:#0078d4; color:white; border-radius:18px;")
        self.btn_send.clicked.connect(self.on_send)
        
        bh.addWidget(self.btn_img)
        bh.addWidget(self.preview)
        bh.addWidget(self.input)
        bh.addWidget(self.btn_send)
        
        layout.addWidget(top)
        layout.addWidget(self.scroll)
        layout.addWidget(bot)

    def eventFilter(self, o, e):
        if o==self.input and e.type()==e.Type.KeyPress and e.key()==Qt.Key.Key_Return and not e.modifiers():
            self.btn_send.click()
            return True
        return super().eventFilter(o,e)

    def pick_img(self):
        p, _ = QFileDialog.getOpenFileName(self, "图", "", "Img (*.png *.jpg)")
        if p:
            with open(p,'rb') as f: self.img_cache = f.read()
            self.preview.setPixmap(QPixmap(p))
            self.preview.setVisible(True)

    def add_msg(self, txt, is_user, img=None):
        bubble = MessageBubble(txt, is_user, img)
        self.chat_layout.addWidget(bubble)
        self.scroll_down()
        return bubble

    def scroll_down(self):
        QTimer.singleShot(50, lambda: self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum()))
        
    def on_send(self): pass

class ResultView(QWidget):
    sig_open_lightbox = pyqtSignal(QPixmap)
    
    def __init__(self, tts_manager):
        super().__init__()
        self.tts = tts_manager
        self.current_pixmap = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(8)

        self.lbl_image = ClickableLabel()
        self.lbl_image.setObjectName("ImagePreview")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setFixedHeight(120)
        self.lbl_image.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_image.clicked.connect(lambda: self.sig_open_lightbox.emit(self.current_pixmap) if self.current_pixmap else None)
        
        self.trans_container = QFrame()
        self.trans_container.setObjectName("Section")
        tc_layout = QVBoxLayout(self.trans_container)
        tc_layout.setContentsMargins(5,5,5,5)
        
        top_bar = QHBoxLayout()
        self.btn_play_t = self.create_btn("🔊", "朗读译文")
        self.btn_copy_t = self.create_btn("📋", "复制译文")
        self.btn_fav = self.create_btn("⭐", "收藏到本地")
        self.btn_fav.setObjectName("FavBtn")
        self.btn_fav.setCheckable(True)
        self.btn_chat = self.create_btn("💬 追问 AI", "进入对话模式")
        self.btn_chat.setObjectName("ChatBtn")
        
        top_bar.addWidget(QLabel("<b>TRANSLATION</b>", styleSheet="color:#0078d4;"))
        top_bar.addStretch()
        top_bar.addWidget(self.btn_play_t)
        top_bar.addWidget(self.btn_copy_t)
        top_bar.addWidget(self.btn_fav)
        top_bar.addWidget(self.btn_chat)
        
        self.trans_browser = QTextBrowser()
        self.trans_browser.setObjectName("TransBrowser")
        
        tc_layout.addLayout(top_bar)
        tc_layout.addWidget(self.trans_browser)
        
        self.raw_container = QFrame()
        self.raw_container.setObjectName("Section")
        rc_layout = QVBoxLayout(self.raw_container)
        rc_layout.setContentsMargins(5,5,5,5)
        
        raw_bar = QHBoxLayout()
        self.btn_play_r = self.create_btn("🔊", "朗读原文")
        self.btn_copy_r = self.create_btn("📋", "复制原文")
        
        raw_bar.addWidget(QLabel("<b>ORIGINAL</b>", styleSheet="color:#888;"))
        raw_bar.addStretch()
        raw_bar.addWidget(self.btn_play_r)
        raw_bar.addWidget(self.btn_copy_r)
        
        self.raw_browser = QTextBrowser()
        self.raw_browser.setObjectName("RawBrowser")
        self.raw_browser.setMinimumHeight(60)
        
        rc_layout.addLayout(raw_bar)
        rc_layout.addWidget(self.raw_browser)

        layout.addWidget(self.lbl_image)
        layout.addWidget(self.trans_container, stretch=2)
        layout.addWidget(self.raw_container, stretch=1)

    def create_btn(self, text, tip):
        b = QPushButton(text)
        b.setProperty("class", "ToolBtn")
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def set_content(self, raw, trans, img_bytes):
        self.raw_browser.setPlainText(raw)
        self.trans_browser.setHtml(trans.replace("\n", "<br>"))
        pix = QPixmap()
        pix.loadFromData(img_bytes)
        self.current_pixmap = pix
        if not pix.isNull():
            self.lbl_image.setPixmap(pix.scaled(QSize(400, 120), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def set_loading(self, img_bytes):
        self.set_content("...", "<div style='color:#aaa'>⚡ 正在分析...</div>", img_bytes)
        self.btn_chat.setEnabled(False)

# ==============================================================================
# 5. 弹窗控制器
# ==============================================================================

class FancyBubble(QWidget):
    def __init__(self, img_bytes, tts_manager, raw=None, trans=None, app_ref=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.tts = tts_manager
        self.img_bytes = img_bytes
        self.raw_txt = raw
        self.trans_txt = trans
        self.app_ref = app_ref
        self.history = []
        self.drag_pos = QPoint()
        self.ai_bubble = None

        self.init_ui()
        self.show_animated()

        if raw is None:
            self.res_view.set_loading(img_bytes)
            self.worker = AIWorker(img_bytes)
            self.worker.sig_result.connect(self.on_ai_done)
            self.worker.sig_model_used.connect(lambda m: self.lbl_title.setText(f"AI VISION • {m}"))
            self.worker.start()
        else:
            self.res_view.set_content(raw, trans, img_bytes)
            self.res_view.btn_chat.setEnabled(True)
            self.adjust_size()

    def init_ui(self):
        self.main = QVBoxLayout(self)
        self.main.setContentsMargins(10,10,10,10)
        self.container = QFrame()
        self.container.setObjectName("MainContainer")
        self.container.setStyleSheet(STYLESHEET)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0,0,0,150))
        self.container.setGraphicsEffect(shadow)
        
        v = QVBoxLayout(self.container)
        v.setContentsMargins(0,0,0,0)
        
        title = QWidget()
        title.setFixedHeight(30)
        tl = QHBoxLayout(title)
        tl.setContentsMargins(10,0,5,0)
        self.lbl_title = QLabel(f"AI VISION")
        self.lbl_title.setObjectName("Title")
        btn_close = QPushButton("✕")
        btn_close.setObjectName("WinBtn")
        btn_close.setFixedSize(24,24)
        btn_close.clicked.connect(self.close)
        tl.addWidget(self.lbl_title)
        tl.addStretch()
        tl.addWidget(btn_close)
        
        self.stack = QStackedWidget()
        self.res_view = ResultView(self.tts)
        self.chat_view = ChatView()
        self.stack.addWidget(self.res_view)
        self.stack.addWidget(self.chat_view)
        
        v.addWidget(title)
        v.addWidget(self.stack)
        self.main.addWidget(self.container)
        
        self.grip = QSizeGrip(self)
        self.grip.setStyleSheet("background:transparent;")

        self.res_view.btn_play_t.clicked.connect(lambda: self.tts.speak(self.trans_txt))
        self.res_view.btn_copy_t.clicked.connect(lambda: pyperclip.copy(self.trans_txt))
        self.res_view.btn_play_r.clicked.connect(lambda: self.tts.speak(self.raw_txt))
        self.res_view.btn_copy_r.clicked.connect(lambda: pyperclip.copy(self.raw_txt))
        self.res_view.btn_fav.clicked.connect(self.do_fav)
        self.res_view.btn_chat.clicked.connect(self.go_chat)
        self.res_view.sig_open_lightbox.connect(lambda p: ImageLightbox(p, self).exec())
        
        self.chat_view.sig_back.connect(lambda: self.stack.setCurrentIndex(0))
        self.chat_view.btn_send.clicked.connect(self.send_chat)

    def show_animated(self):
        self.resize(450, 500)
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width()-450)//2
        y = (screen.height()-500)//2
        self.move(x, y)
        self.setWindowOpacity(0)
        self.show()
        self.ani = QPropertyAnimation(self, b"windowOpacity")
        self.ani.setDuration(250)
        self.ani.setStartValue(0)
        self.ani.setEndValue(1)
        self.ani.start()

    def on_ai_done(self, r, t):
        self.raw_txt = r
        self.trans_txt = t
        self.res_view.set_content(r, t, self.img_bytes)
        self.res_view.btn_chat.setEnabled(True)
        self.adjust_size()
        if self.app_ref: self.app_ref.record_history(r, t, self.img_bytes)

    def adjust_size(self):
        txt_len = len(self.trans_txt or "") + len(self.raw_txt or "")
        h = max(400, min(800, 300 + int(txt_len * 0.8)))
        self.resize(self.width(), h)

    def do_fav(self):
        if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SAVE_DIR, ts)
        os.makedirs(path)
        with open(os.path.join(path,"capture.png"),"wb") as f: f.write(self.img_bytes)
        with open(os.path.join(path,"content.json"),"w",encoding='utf-8') as f:
            json.dump({"time":ts,"raw":self.raw_txt,"trans":self.trans_txt}, f)
        self.res_view.btn_fav.setText("✔ 已保存")
        self.res_view.btn_fav.setEnabled(False)

    def go_chat(self):
        self.stack.setCurrentIndex(1)
        if not self.history:
            self.history = [
                {"role":"system","content":"[ENABLE_THINKING] You are a deep visual analysis expert."},
                {"role":"user","content":f"Context: {self.raw_txt}","images":[self.img_bytes]}
            ]
            self.chat_view.add_msg("深度模式已开启。", False)

    def send_chat(self):
        t = self.chat_view.input.toPlainText().strip()
        img = self.chat_view.img_cache
        if not t and not img: return
        self.chat_view.add_msg(t, True, img)
        self.chat_view.input.clear()
        self.chat_view.img_cache = None
        self.chat_view.preview.setVisible(False)
        self.chat_view.input.setPlaceholderText("提问...")
        
        p = {"role":"user", "content":t}
        if img: p["images"] = [img]
        self.history.append(p)
        
        self.ai_bubble = self.chat_view.add_msg("...", False)
        self.ai_accum = ""
        self.cw = ChatWorker(self.history)
        self.cw.sig_chunk.connect(self.on_chunk)
        self.cw.sig_done.connect(lambda: self.history.append({"role":"assistant","content":self.ai_accum}))
        self.cw.start()

    def on_chunk(self, c):
        self.ai_accum += c
        if self.ai_bubble: self.ai_bubble.update_text(self.ai_accum)
        self.chat_view.scroll_down()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull(): self.move(e.globalPosition().toPoint() - self.drag_pos)
    def resizeEvent(self, e): 
        self.grip.move(self.rect().right()-20, self.rect().bottom()-20)
        super().resizeEvent(e)

# ==============================================================================
# 6. APP 控制器
# ==============================================================================

class OCRApp(QWidget):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager.load()
        OllamaService.check_and_start()
        self.tts_manager = TTSManager()
        self.history = []
        self.poller = ClipboardPoller()
        self.poller.sig_image_found.connect(self.on_snip_done)
        self.setup_tray()
        self.register_hotkey()
        print(f"Ready. Hotkey: {self.config['hotkey']}")

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)
        pix = QPixmap(64,64)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setBrush(QColor(0,120,212))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0,0,64,64,12,12)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Arial", 36, 700))
        p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
        p.end()
        self.tray.setIcon(QIcon(pix))
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.update_menu)
        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def register_hotkey(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.config['hotkey'], self.start_snip)
        except: print("Hotkey Error")

    def start_snip(self):
        if os.name == 'nt': os.startfile("ms-screenclip:")
        self.poller.start()

    def on_snip_done(self, img_bytes):
        self.bubble = FancyBubble(img_bytes, self.tts_manager, app_ref=self)
        self.bubble.show()

    def record_history(self, r, t, b):
        self.history.insert(0, {"time": datetime.datetime.now().strftime("%H:%M"), "raw":r, "trans":t, "img":b})

    def open_bubble(self, d):
        self.bubble = FancyBubble(d['img'], self.tts_manager, d['raw'], d['trans'], self)
        self.bubble.show()

    def change_hotkey(self):
        k, ok = QInputDialog.getText(None, "设置", "快捷键:", text=self.config['hotkey'])
        if ok and k:
            self.config['hotkey'] = k
            ConfigManager.save(self.config)
            self.register_hotkey()

    def open_settings(self):
        SettingsDialog(None).exec()

    def update_menu(self):
        self.menu.clear()
        self.menu.addAction("⚙️ API 设置").triggered.connect(self.open_settings)
        self.menu.addAction("⌨️ 快捷键").triggered.connect(self.change_hotkey)
        self.menu.addSeparator()
        hm = self.menu.addMenu(f"🕒 历史 ({len(self.history)})")
        if self.history:
            for i in self.history:
                act = QAction(f"{i['time']} - {i['trans'][:10]}...", self)
                act.triggered.connect(lambda _, d=i: self.open_bubble(d))
                hm.addAction(act)
        else: hm.addAction("空").setEnabled(False)
        
        fm = self.menu.addMenu("⭐ 收藏")
        if os.path.exists(SAVE_DIR):
            for fd in sorted(os.listdir(SAVE_DIR), reverse=True):
                path = os.path.join(SAVE_DIR, fd)
                try:
                    with open(os.path.join(path,"content.json"),'r',encoding='utf-8') as f: d=json.load(f)
                    with open(os.path.join(path,"capture.png"),'rb') as f: b=f.read()
                    act = QAction(f"{d['trans'][:10]}...", self)
                    act.triggered.connect(lambda _, ib=b,r=d['raw'],t=d['trans']: self.open_bubble({'img':ib,'raw':r,'trans':t}))
                    fm.addAction(act)
                except: pass
        self.menu.addSeparator()
        self.menu.addAction("退出").triggered.connect(self.quit_app)

    def quit_app(self):
        self.tts_manager.stop()
        OllamaService.stop()
        QApplication.quit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    core = OCRApp()
    sys.exit(app.exec())
