import sys
import os
import json
import io
from urllib.parse import urlparse
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QComboBox, QPushButton, QTextEdit, 
                             QInputDialog, QMessageBox, QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QIcon

# --- НАСТРОЙКА ОКРУЖЕНИЯ ---
def setup_environment():
    # Определяем базовую директорию (учитываем работу внутри PyInstaller Bundle)
    if hasattr(sys, '_MEIPASS'):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
        
    # Путь к venv для разработки
    venv_site = os.path.join(base_dir, ".venv", "lib", "python3.13", "site-packages")
    if os.path.exists(venv_site) and venv_site not in sys.path:
        sys.path.insert(0, venv_site)
    
    return base_dir

BASE_DIR = setup_environment()

try:
    from ymd.cli import main as ymd_main
except ImportError:
    try:
        from yandex_music_downloader.cli import main as ymd_main
    except ImportError:
        def ymd_main():
            raise RuntimeError("Движок скачивания (ymd) не найден. Убедитесь, что зависимости установлены.")

# --- ПУТИ К ФАЙЛАМ ---
CONFIG_DIR = os.path.expanduser("~/.config/ymd_gui")
os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Дефолтный путь для музыки
DEFAULT_MUSIC_DIR = os.path.join(os.path.expanduser("~/Music"), "y_music")

class SubprocessEmulator(io.StringIO):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
    def write(self, s):
        if s.strip(): 
            self.signal.emit(s)
        return super().write(s)

class DownloadThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, url, quality, token, download_dir):
        super().__init__()
        self.url = url
        self.quality = quality
        self.token = token
        self.download_dir = download_dir

    def run(self):
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir, exist_ok=True)
            
        sys.argv = [
            "ymd", 
            "--token", self.token,
            "--quality", self.quality,
            "--dir", self.download_dir,
            "--url", self.url
        ]
        
        old_out, old_err = sys.stdout, sys.stderr
        stream = SubprocessEmulator(self.log_signal)
        sys.stdout = sys.stderr = stream

        try:
            ymd_main()
            self.finished_signal.emit(0)
        except SystemExit as e:
            self.finished_signal.emit(e.code if e.code is not None else 0)
        except Exception as e:
            self.log_signal.emit(f"\n❌ ОШИБКА: {str(e)}\n")
            self.finished_signal.emit(-1)
        finally:
            sys.stdout, sys.stderr = old_out, old_err

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
                    saved = json.load(f)
                    if "download_dir" in saved and "download_dirs" not in saved:
                        saved["download_dirs"] = [saved["download_dir"]]
                    self.config_data.update(saved)
            except: 
                pass
        
        if not self.config_data["download_dirs"]:
            self.config_data["download_dirs"] = [DEFAULT_MUSIC_DIR]
        self.save_config()

    def save_config(self):
        if hasattr(self, 'dir_combo'):
            self.config_data["current_dir_index"] = self.dir_combo.currentIndex()
            
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, ensure_ascii=False, indent=4)

    def init_ui(self):
        self.setWindowTitle("Yandex Music Downloader")
        self.resize(650, 620)
        
        # Установка иконки окна
        icon_path = os.path.join(BASE_DIR, "assets", "icon.icns")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

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
        main_layout.addLayout(acc_layout)

        # 2. Пути
        dir_layout = QHBoxLayout()
        self.dir_combo = QComboBox()
        self.refresh_dirs()
        dir_layout.addWidget(QLabel("Папка:"), 0)
        dir_layout.addWidget(self.dir_combo, 1)
        btn_browse = QPushButton("Обзор")
        btn_browse.clicked.connect(self.choose_dir)
        dir_layout.addWidget(btn_browse)
        main_layout.addLayout(dir_layout)

        # 3. Ссылка
        main_layout.addWidget(QLabel("Ссылка на музыку (трек, альбом, плейлист):"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://music.yandex.ru/...")
        main_layout.addWidget(self.url_input)

        # 4. Качество и Кнопка
        bottom_controls = QHBoxLayout()
        self.q_combo = QComboBox()
        self.q_combo.addItems(["FLAC (Максимум)", "AAC 192 kbps", "AAC 64 kbps"])
        bottom_controls.addWidget(QLabel("Качество:"), 0)
        bottom_controls.addWidget(self.q_combo, 0)
        bottom_controls.addStretch(1)

        self.btn_run = QPushButton("СКАЧАТЬ")
        self.btn_run.setMinimumSize(180, 45)
        self.btn_run.setStyleSheet("""
            QPushButton { background-color: #2ea44f; color: white; font-weight: bold; border-radius: 6px; font-size: 13px; }
            QPushButton:hover { background-color: #2c974b; }
            QPushButton:disabled { background-color: #94d3a2; }
        """)
        self.btn_run.clicked.connect(self.start_download)
        bottom_controls.addWidget(self.btn_run)
        main_layout.addLayout(bottom_controls)

        # 5. Лог
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Menlo", 12))
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #00ff00;")
        main_layout.addWidget(self.log_view)

        self.setLayout(main_layout)

    def refresh_tokens(self):
        self.token_combo.clear()
        for t in self.config_data["tokens"]:
            self.token_combo.addItem(t['name'], t['token'])

    def refresh_dirs(self):
        self.dir_combo.clear()
        for path in self.config_data["download_dirs"]:
            short_name = os.path.basename(path) if os.path.basename(path) else path
            self.dir_combo.addItem(short_name, path)
            self.dir_combo.setItemData(self.dir_combo.count()-1, path, Qt.ItemDataRole.ToolTipRole)
        
        idx = self.config_data.get("current_dir_index", 0)
        if idx < self.dir_combo.count():
            self.dir_combo.setCurrentIndex(idx)

    def add_token(self):
        name, ok1 = QInputDialog.getText(self, "Новый аккаунт", "Введите имя:")
        if not ok1 or not name: return
        token, ok2 = QInputDialog.getText(self, "Токен", f"Введите токен для {name}:")
        if not ok2 or not token: return
        self.config_data["tokens"].append({"name": name, "token": token.strip()})
        self.save_config(); self.refresh_tokens()
        self.token_combo.setCurrentIndex(self.token_combo.count() - 1)

    def choose_dir(self):
        current_path = self.dir_combo.currentData() or os.path.expanduser("~/Music")
        d = QFileDialog.getExistingDirectory(self, "Выбрать папку", current_path)
        if d:
            if d not in self.config_data["download_dirs"]:
                self.config_data["download_dirs"].append(d)
            self.refresh_dirs()
            idx = self.config_data["download_dirs"].index(d)
            self.dir_combo.setCurrentIndex(idx)
            self.save_config()

    def start_download(self):
        url = self.url_input.text().strip().split("?")[0]
        token = self.token_combo.currentData()
        target_dir = self.dir_combo.currentData()
        
        if not url.startswith("http") or not token or not target_dir:
            QMessageBox.warning(self, "Внимание", "Проверьте ссылку, аккаунт и папку скачивания.")
            return
            
        self.btn_run.setEnabled(False)
        self.btn_run.setText("В ПРОЦЕССЕ...")
        self.log_view.clear()
        self.save_config()
        
        q_map = {"FLAC (Максимум)": "2", "AAC 192 kbps": "1", "AAC 64 kbps": "0"}
        self.thread = DownloadThread(url, q_map[self.q_combo.currentText()], token, target_dir)
        self.thread.log_signal.connect(self.log_view.insertPlainText)
        self.thread.finished_signal.connect(self.on_finished)
        self.thread.start()

    def on_finished(self, code):
        self.btn_run.setEnabled(True)
        self.btn_run.setText("СКАЧАТЬ")
        if code == 0: 
            self.log_view.append("\n✅ ЗАГРУЗКА ЗАВЕРШЕНА!")
        else: 
            self.log_view.append(f"\n❌ ОШИБКА (Код: {code})")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YMDGui()
    window.show()
    sys.exit(app.exec())