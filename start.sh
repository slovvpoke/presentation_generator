#!/bin/bash

# SFApps Presentation Generator - Скрипт запуска
# ===============================================

echo "🚀 SFApps Presentation Generator"
echo "================================="

# Проверка виртуального окружения
if [ ! -d ".venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv .venv
fi

# Активация виртуального окружения
echo "⚡ Активация виртуального окружения..."
source .venv/bin/activate

# Установка зависимостей
echo "📥 Установка зависимостей..."
pip install -q -r requirements.txt

# Проверка наличия шаблона
if [ ! -f "Copy of SFApps.info Best Apps Presentation Template.pptx" ]; then
    echo "❌ Ошибка: Шаблон презентации не найден!"
    echo "   Убедитесь что файл 'Copy of SFApps.info Best Apps Presentation Template.pptx' находится в текущей директории"
    exit 1
fi

echo "✅ Все готово к запуску!"
echo ""
echo "🌐 Запуск веб-сервера..."
echo "   URL: http://127.0.0.1:5000"
echo ""
echo "❓ Для остановки сервера нажмите Ctrl+C"
echo ""

# Запуск приложения
python app.py