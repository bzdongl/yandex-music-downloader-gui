#!/bin/bash

# 1. Сборка приложения
# Объединяем в одну длинную строку, чтобы Bash точно не ошибся
echo "🔨 Собираю .app..."
./.venv/bin/pyinstaller --noconfirm --onedir --windowed --icon="assets/icon.icns" --add-data "assets:assets" --collect-all ymd --name "YandexMusicDownloader" gui.py

# 2. Удаление старого DMG
rm YandexMusicDownloader.dmg 2>/dev/null

# 3. Создание нового DMG
echo "📦 Упаковываю в .dmg..."
# Здесь переносы важны для читаемости, убедись, что после \ нет пробелов
create-dmg \
  --volname "Yandex Music Downloader" \
  --volicon "assets/icon.icns" \
  --background "assets/dmg_bg.png" \
  --window-pos 200 120 \
  --window-size 600 450 \
  --icon-size 100 \
  --icon "YandexMusicDownloader.app" 175 250 \
  --hide-extension "YandexMusicDownloader.app" \
  --app-drop-link 425 250 \
  "YandexMusicDownloader.dmg" \
  "dist/YandexMusicDownloader.app"

# 4. Установка иконки на файл через AppleScript (нативно для macOS)
echo "🎨 Устанавливаю иконку на файл..."
osascript -e "
    set iconPath to POSIX file \"$(pwd)/assets/icon.icns\"
    set filePath to POSIX file \"$(pwd)/YandexMusicDownloader.dmg\"
    tell application \"Finder\"
        set theIcon to (read iconPath as icon family)
        set custom icon of file filePath to theIcon
    end tell
"

echo "✅ Готово! Сборка завершена."