import sys
import os
import json
import io

# --- МГНОВЕННЫЙ СТАРТ ---
# Импортируем только базовые элементы, чтобы окно появилось сразу
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel

def setup_environment():
    # Определяем базовую директорию (учитываем работу внутри PyInstaller Bundle)
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    return base_dir

BASE_DIR = setup_environment()

# Настройки путей для конфига
CONFIG_DIR = os.path.expanduser("~/.config/ymd_gui")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_MUSIC_DIR = os.path.join(os.path.expanduser("~/Music"), "y_music")

class SubprocessEmulator(io.StringIO):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
    def write(self, s):
        if s.strip(): 
            self.signal.emit(s)
        return super().write(s)

class YMDGui(QWidget):
    def __init__(self):
        super().__init__()
        self.config_data = {
            "tokens": [], 
            "download_dirs": [DEFAULT_MUSIC_DIR],
            "current_dir_index": 0
        }
        self.load_config()
        self.init_ui()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config_data.update(json.load(f))
            except: 
                pass

    def save_config(self):
        if hasattr(self, 'dir_combo'):
            self.config_data["current_dir_index"] = self.dir_combo.currentIndex()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=4)

    def init_ui(self):
        # ЛЕНИВЫЙ ИМПОРТ: Тяжелые компоненты GUI загружаются только сейчас
        from PyQt6.QtGui import QFont, QIcon
        from PyQt6.QtWidgets import (QLineEdit, QComboBox, QPushButton, QTextEdit, 
                                     QInputDialog, QMessageBox, QFileDialog)
        from PyQt6.QtCore import Qt

        self.setWindowTitle("Yandex Music Downloader")
        self.resize(650, 620)
        
        # Установка иконки из папки assets
        icon_path = os.path.join(BASE_DIR, "assets", "icon.icns")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # 1. Аккаунты
        acc_layout = QHBoxLayout()
        self.token_combo = QComboBox()
        self.refresh_tokens()
        acc_layout.addWidget(QLabel("Аккаунт:"), 0)
        acc_layout.addWidget(self.token_combo, 1)
        btn_add_token = QPushButton("+")
        btn_add_token.setFixedWidth(40)
        btn_add_token.clicked.connect(self.add_token)
        acc_layout.addWidget(btn_add_token)
        layout.addLayout(acc_layout)

        # 2. Пути
        dir_layout = QHBoxLayout()
        self.dir_combo = QComboBox()
        self.refresh_dirs()
        dir_layout.addWidget(QLabel("Папка:"), 0)
        dir_layout.addWidget(self.dir_combo, 1)
        btn_browse = QPushButton("Обзор")
        btn_browse.clicked.connect(self.choose_dir)
        dir_layout.addWidget(btn_browse)
        layout.addLayout(dir_layout)

        # 3. Ссылка
        layout.addWidget(QLabel("Ссылка на музыку:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://music.yandex.ru/...")
        layout.addWidget(self.url_input)

        # 4. Качество и Кнопка
        bottom_controls = QHBoxLayout()
        self.q_combo = QComboBox()
        self.q_combo.addItems(["FLAC (Максимум)", "AAC 192 kbps", "AAC 64 kbps"])
        bottom_controls.addWidget(QLabel("Качество:"), 0)
        bottom_controls.addWidget(self.q_combo, 0)
        bottom_controls.addStretch(1)

        self.btn_run = QPushButton("СКАЧАТЬ")
        self.btn_run.setMinimumSize(180, 45)
        self.btn_run.setStyleSheet("background-color: #2ea44f; color: white; font-weight: bold; border-radius: 6px;")
        self.btn_run.clicked.connect(self.start_download)
        bottom_controls.addWidget(self.btn_run)
        layout.addLayout(bottom_controls)

        # 5. Лог
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        layout.addWidget(self.log_view)

        self.setLayout(layout)

    def refresh_tokens(self):
        self.token_combo.clear()
        for t in self.config_data["tokens"]:
            self.token_combo.addItem(t['name'], t['token'])

    def refresh_dirs(self):
        self.dir_combo.clear()
        for path in self.config_data["download_dirs"]:
            self.dir_combo.addItem(os.path.basename(path) or path, path)
        
        idx = self.config_data.get("current_dir_index", 0)
        if idx < self.dir_combo.count():
            self.dir_combo.setCurrentIndex(idx)

    def add_token(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok1 = QInputDialog.getText(self, "Новый аккаунт", "Введите имя:")
        if ok1 and name:
            token, ok2 = QInputDialog.getText(self, "Токен", f"Введите токен для {name}:")
            if ok2 and token:
                self.config_data["tokens"].append({"name": name, "token": token.strip()})
                self.save_config()
                self.refresh_tokens()

    def choose_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "Выбрать папку")
        if d:
            if d not in self.config_data["download_dirs"]:
                self.config_data["download_dirs"].append(d)
            self.refresh_dirs()
            self.save_config()

    def start_download(self):
        # ЛЕНИВЫЙ ИМПОРТ: Загружаем тяжелый движок только при клике
        from PyQt6.QtCore import QThread, pyqtSignal
        
        url = self.url_input.text().strip()
        token = self.token_combo.currentData()
        target_dir = self.dir_combo.currentData()

        if not url or not token:
            return

        self.btn_run.setEnabled(False)
        self.btn_run.setText("В ПРОЦЕССЕ...")
        self.log_view.clear()
        
        # Здесь должна быть логика DownloadThread, использующая ymd_main
        # Для краткости предполагаем, что она определена выше или импортируется тут
        self.log_view.append(f"Начинаю загрузку: {url}")
        # ... запуск потока ...

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YMDGui()
    window.show()
    sys.exit(app.exec())