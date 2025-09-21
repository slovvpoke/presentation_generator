#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web Application for SFApps Presentation Generator
========================================================

Веб-интерфейс для автоматической генерации PowerPoint презентаций 
"Best Apps for {Industry} Available on AppExchange" на основе готового шаблона.

Функциональность:
- Ввод темы презентации (industry)
- Ввод списка ссылок на AppExchange приложения (1–10 ссылок)
- Автоматическое извлечение логотипов, названий и разработчиков
- Возможность ручного переопределения данных
- Предварительный просмотр слайдов
- Экспорт в PPTX и PDF форматы
"""

import os
import tempfile
import uuid
import base64
import mimetypes
from typing import Optional, Dict, Any

import requests
from flask import Flask, render_template, request, flash, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

# Импорт функций генератора презентаций
from sfapps_template_generator import (
    create_presentation_from_template, 
    AppMetadata
)

# Импорт улучшенного Selenium парсера (приоритетный)
try:
    from improved_selenium_parser import parse_appexchange_improved
    IMPROVED_SELENIUM_AVAILABLE = True
    print("✅ Улучшенный Selenium парсер доступен")
except ImportError:
    IMPROVED_SELENIUM_AVAILABLE = False
    print("⚠️ Улучшенный Selenium парсер недоступен")

# Импорт простого Selenium парсера (резервный)
try:
    from simple_parser import parse_appexchange_simple
    SELENIUM_PARSER_AVAILABLE = True
    print("✅ Простой Selenium парсер доступен")
except ImportError:
    SELENIUM_PARSER_AVAILABLE = False
    print("⚠️ Простой Selenium парсер недоступен")

# Импорт финального парсера (резервный)
try:
    from final_parser import parse_appexchange_app
    FINAL_PARSER_AVAILABLE = True
    print("✅ Финальный парсер доступен")
except ImportError:
    from sfapps_template_generator import fetch_app_metadata
    FINAL_PARSER_AVAILABLE = False
    print("⚠️ Финальный парсер недоступен")

app = Flask(__name__)
app.secret_key = 'sfapps-presentation-generator-secret-key-2025'

# Конфигурация
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}  # расширили
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Убедимся, что папка uploads существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- MIME helpers ----------

def sniff_mime(logo_bytes: bytes, url_hint: str = "", header_mime: str = "") -> str:
    """
    Определяем корректный MIME для data:URI и/или для передачи в генератор.
    Приоритет: header_mime → по сигнатуре → по расширению → image/png.
    """
    header_mime = (header_mime or "").lower().strip()
    if header_mime.startswith("image/"):
        return header_mime

    b = logo_bytes or b""
    h = b[:256]

    # SVG (по содержимому)
    if b and (h.lstrip().startswith(b"<?xml") or b"<svg" in h.lower()):
        return "image/svg+xml"
    # PNG
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    # JPEG
    if h.startswith(b"\xff\xd8"):
        return "image/jpeg"
    # GIF
    if h.startswith(b"GIF87a") or h.startswith(b"GIF89a"):
        return "image/gif"
    # WebP
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "image/webp"

    # По расширению URL
    if url_hint:
        guess = mimetypes.guess_type(url_hint)[0]
        if guess:
            return guess

    return "image/png"


# ---------- Вспомогательные функции ----------

def allowed_file(filename):
    """Проверка допустимых расширений файлов"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Сохранение загруженного файла и возврат пути"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return filepath
    return None


def fetch_app_metadata_with_fallback(url: str) -> Optional[AppMetadata]:
    """Получение метаданных, приоритет — улучшенный Selenium парсер (.listing-title h1 / p / .listing-logo img)"""
    # Общие заголовки для загрузки изображений (WebP/SVG и т.п.)
    img_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://appexchange.salesforce.com/",
    }

    def _download_logo(logo_url: str):
        try:
            r = requests.get(logo_url, timeout=10, headers=img_headers)
            if r.status_code == 200:
                logo_bytes = r.content
                logo_mime = sniff_mime(logo_bytes, url_hint=logo_url, header_mime=r.headers.get("content-type", ""))
                return logo_bytes, logo_mime
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
        return b"", "image/png"

    # Приоритет 1: Улучшенный Selenium парсер
    if IMPROVED_SELENIUM_AVAILABLE:
        try:
            print(f"🔄 Используем улучшенный Selenium парсер для {url}")
            result = parse_appexchange_improved(url)
            if result and result.get('success'):
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes, logo_mime = b"", "image/png"
                logo_url = result.get('logo_url')
                if logo_url:
                    logo_bytes, logo_mime = _download_logo(logo_url)
                return AppMetadata(url=url, name=name, developer=developer, logo_bytes=logo_bytes, logo_mime=logo_mime)
        except Exception as e:
            print(f"⚠️ Ошибка в улучшенном Selenium парсере: {e}")

    # Приоритет 2: Простой Selenium парсер
    if SELENIUM_PARSER_AVAILABLE:
        try:
            print(f"🔄 Используем простой Selenium парсер для {url}")
            result = parse_appexchange_simple(url)
            if result and result.get('success'):
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes, logo_mime = b"", "image/png"
                logo_url = result.get('logo_url')
                if logo_url:
                    logo_bytes, logo_mime = _download_logo(logo_url)
                return AppMetadata(url=url, name=name, developer=developer, logo_bytes=logo_bytes, logo_mime=logo_mime)
        except Exception as e:
            print(f"⚠️ Ошибка в простом Selenium парсере: {e}")

    # Приоритет 3: Финальный парсер
    if FINAL_PARSER_AVAILABLE:
        try:
            print(f"🔄 Используем финальный парсер для {url}")
            result = parse_appexchange_app(url)
            if result and result.get('name') != 'Unknown App':
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes, logo_mime = b"", "image/png"
                image_url = result.get('image_url')
                if image_url:
                    logo_bytes, logo_mime = _download_logo(image_url)
                return AppMetadata(url=url, name=name, developer=developer, logo_bytes=logo_bytes, logo_mime=logo_mime)
        except Exception as e:
            print(f"⚠️ Ошибка в финальном парсере: {e}")

    # Приоритет 4: Оригинальный парсер
    try:
        print(f"🔄 Используем оригинальный парсер для {url}")
        from sfapps_template_generator import fetch_app_metadata
        meta = fetch_app_metadata(url)
        if meta:
            return meta
    except Exception as e:
        print(f"⚠️ Ошибка в оригинальном парсере: {e}")

    print(f"❌ Не удалось получить метаданные: {url}")
    return AppMetadata(
        url=url,
        name="Не удалось загрузить название",
        developer="Не удалось загрузить разработчика",
        logo_bytes=b'',
        logo_mime='image/png'
    )


def process_form_data(form_data, files):
    """Обработка данных формы и создание структуры для генератора"""
    industry = form_data.get('industry', '').strip()
    final_url = form_data.get('final_url', '').strip()

    # Получение списков (массивы из фронта)
    app_links = [link.strip() for link in form_data.getlist('app_links[]') if link.strip()]
    app_names = form_data.getlist('app_names[]')
    app_developers = form_data.getlist('app_developers[]')
    app_logos = files.getlist('app_logos[]')

    if len(app_links) < 1:
        raise ValueError("Необходимо минимум 1 ссылку на приложение")
    if len(app_links) > 10:
        raise ValueError("Максимальное количество ссылок: 10")

    # Только ручные переопределения пользователя
    overrides: Dict[str, Dict[str, Any]] = {}
    for i, link in enumerate(app_links):
        od: Dict[str, Any] = {}
        if i < len(app_names) and app_names[i].strip():
            od['name'] = app_names[i].strip()
        if i < len(app_developers) and app_developers[i].strip():
            od['developer'] = app_developers[i].strip()
        if i < len(app_logos) and app_logos[i].filename:
            logo_path = save_uploaded_file(app_logos[i])
            if logo_path:
                od['logo_path'] = logo_path
                od['logo_mime'] = mimetypes.guess_type(logo_path)[0] or 'image/png'
        if od:
            overrides[link] = od

    return {
        'industry': industry,
        'app_links': app_links,
        'final_url': final_url,
        'overrides': overrides
    }


def resolve_app_data(link: str, overrides: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Единая точка истины: собирает данные для одного приложения.
    1) Берёт ручные overrides (name/developer/logo_path);
    2) Если чего-то нет — дотягивает через Selenium-парсер (fetch_app_metadata_with_fallback);
    3) Возвращает словарь, пригодный и для превью, и для генератора.
    """
    data: Dict[str, Any] = {}

    # 1) ручные overrides
    if link in overrides:
        data.update(overrides[link])

    # 2) автопарсинг, если чего-то не хватает
    need_logo = ('logo_path' not in data and 'logo_bytes' not in data)
    if 'name' not in data or 'developer' not in data or need_logo:
        meta = fetch_app_metadata_with_fallback(link)
        if meta:
            if 'name' not in data and meta.name:
                data['name'] = meta.name
            if 'developer' not in data and meta.developer:
                data['developer'] = meta.developer
            if need_logo and getattr(meta, 'logo_bytes', b''):
                data['logo_bytes'] = meta.logo_bytes
                data['logo_mime'] = getattr(meta, 'logo_mime', None) or sniff_mime(meta.logo_bytes, url_hint=link)

    # Если пользователь загрузил файл, но не указали mime — определим по расширению
    if 'logo_path' in data and 'logo_mime' not in data:
        data['logo_mime'] = mimetypes.guess_type(data['logo_path'])[0] or 'image/png'

    # Гарантируем наличие базовых полей
    data.setdefault('name', '⚠️ Требуется ручной ввод')
    data.setdefault('developer', '⚠️ Требуется ручной ввод')

    return data


def create_preview_data(industry, app_links, final_url, overrides):
    """Создание данных для предварительного просмотра (использует resolve_app_data => как в итоговых слайдах)"""
    preview_slides = []

    # Титульный слайд — чистый заголовок
    preview_slides.append({
        'title': 'Титульный слайд',
        'content': f'<h4>Best Apps for {industry} Available on AppExchange</h4>',
        'image': None
    })

    # Слайды с приложениями
    for i, link in enumerate(app_links):
        slide_num = i + 1
        resolved = resolve_app_data(link, overrides)

        # Готовим лого для превью (base64) с корректным MIME
        logo_data = None
        if 'logo_path' in resolved and os.path.exists(resolved['logo_path']):
            try:
                with open(resolved['logo_path'], 'rb') as f:
                    logo_bytes = f.read()
                mime = resolved.get('logo_mime') or mimetypes.guess_type(resolved['logo_path'])[0] or 'image/png'
                logo_data = f"data:{mime};base64,{base64.b64encode(logo_bytes).decode()}"
            except Exception:
                pass
        elif 'logo_bytes' in resolved and resolved['logo_bytes']:
            try:
                mime = resolved.get('logo_mime') or sniff_mime(resolved['logo_bytes'], url_hint=link)
                logo_data = f"data:{mime};base64,{base64.b64encode(resolved['logo_bytes']).decode()}"
            except Exception:
                pass

        preview_slides.append({
            'title': f'Приложение #{slide_num}',
            'content': (
                f'<h5>{resolved["name"]}</h5>'
                f'<p>{resolved["developer"]}</p>'
                f'<small class="text-muted">{link}</small>'
            ),
            'image': logo_data
        })

    # Финальный слайд — тема и ссылка
    preview_slides.append({
        'title': 'Финальный слайд',
        'content': (
            f'<h4>Best Apps for {industry} Available on AppExchange</h4>'
            f'<p>Ссылка: <a href="{final_url}" target="_blank">{final_url}</a></p>'
        ),
        'image': None
    })

    return {'slides': preview_slides}


@app.route('/')
def index():
    """Главная страница с формой"""
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_presentation():
    """Генерация презентации или предварительного просмотра"""
    try:
        data = process_form_data(request.form, request.files)
        industry = data['industry']
        app_links = data['app_links']
        final_url = data['final_url']
        overrides = data['overrides']

        # Превью?
        if request.form.get('preview') == 'true':
            preview_data = create_preview_data(industry, app_links, final_url, overrides)
            return jsonify({'success': True, 'preview': preview_data})

        # Готовим окончательные overrides для генератора (такие же, как в превью)
        resolved_overrides: Dict[str, Dict[str, Any]] = {}
        for link in app_links:
            resolved = resolve_app_data(link, overrides)
            ro: Dict[str, Any] = {
                'name': resolved['name'],
                'developer': resolved['developer']
            }
            if 'logo_path' in resolved:
                ro['logo_path'] = resolved['logo_path']
            if 'logo_bytes' in resolved:
                ro['logo_bytes'] = resolved['logo_bytes']
            if 'logo_mime' in resolved:
                ro['logo_mime'] = resolved['logo_mime']
            resolved_overrides[link] = ro

        # Формат выхода
        output_format = request.form.get('format', 'pptx')

        # Шаблон
        template_path = 'Copy of SFApps.info Best Apps Presentation Template.pptx'
        if not os.path.exists(template_path):
            flash('Шаблон презентации не найден', 'error')
            return redirect(url_for('index'))

        # Временные файлы
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as tmp_pptx:
            output_pptx = tmp_pptx.name
        output_pdf = None
        if output_format == 'pdf':
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                output_pdf = tmp_pdf.name

        try:
            # Генерация: прокидываем уже РАЗРЕШЁННЫЕ данные
            create_presentation_from_template(
                topic=industry,
                links=app_links,
                final_url=final_url,
                template_path=template_path,
                output_pptx=output_pptx,
                output_pdf=output_pdf,
                app_overrides=resolved_overrides
            )

            # Что отдаём пользователю
            if output_format == 'pdf' and output_pdf and os.path.exists(output_pdf):
                send_file_path = output_pdf
                mimetype = 'application/pdf'
                filename = f'Best_Apps_for_{industry}.pdf'
            else:
                send_file_path = output_pptx
                mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                filename = f'Best_Apps_for_{industry}.pptx'

            return send_file(
                send_file_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )

        finally:
            # Удаляем временные файлы
            try:
                if os.path.exists(output_pptx):
                    os.unlink(output_pptx)
                if output_pdf and os.path.exists(output_pdf):
                    os.unlink(output_pdf)
            except Exception:
                pass
            # Удаляем загруженные лого пользователя (если не нужны дальше)
            for od in overrides.values():
                lp = od.get('logo_path')
                # Если хочешь сохранять их — убери удаление ниже
                if lp and os.path.exists(lp):
                    try:
                        os.unlink(lp)
                    except Exception:
                        pass

    except ValueError as e:
        if request.form.get('preview') == 'true':
            return jsonify({'success': False, 'error': str(e)})
        flash(str(e), 'error')
        return redirect(url_for('index'))

    except Exception as e:
        if request.form.get('preview') == 'true':
            return jsonify({'success': False, 'error': f'Ошибка генерации: {str(e)}'})
        flash(f'Ошибка при генерации презентации: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.errorhandler(413)
def too_large(e):
    """Обработка ошибки размера файла"""
    flash('Файл слишком большой. Максимальный размер: 16MB', 'error')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    """Обработка 404 ошибки"""
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Обработка внутренних ошибок сервера"""
    flash('Внутренняя ошибка сервера. Попробуйте еще раз.', 'error')
    return render_template('index.html'), 500


if __name__ == '__main__':
    print("Запуск SFApps Presentation Generator...")
    print("📁 Рабочая директория:", os.getcwd())
    print("📄 Шаблон:", "Copy of SFApps.info Best Apps Presentation Template.pptx")
    print("🌐 Открыть в браузере: http://localhost:5001")
    print("-" * 50)
    app.run(debug=True, host='0.0.0.0', port=5001)
