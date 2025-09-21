"""
Flask Web Application for SFApps Presentation Generator
========================================================

Веб-интерфейс для автоматической генерации PowerPoint презентаций 
"Best Apps for {Industry} Available on AppExchange" на основе готового шаблона.

Функциональность:
- Ввод темы презентации (industry)
- Ввод списка ссылок на AppExchange приложения (5-20 ссылок)
- Автоматическое извлечение логотипов, названий и разработчиков
- Возможность ручного переопределения данных
- Предварительный просмотр слайдов
- Экспорт в PPTX и PDF форматы
"""

import os
import tempfile
import uuid
from datetime import datetime
from io import BytesIO
import base64
from typing import Optional

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
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Убедимся, что папка uploads существует
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Проверка допустимых расширений файлов"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def fetch_app_metadata_with_fallback(url: str) -> Optional[AppMetadata]:
    """Получение метаданных с приоритетом на улучшенный Selenium парсер"""
    
    # Приоритет 1: Улучшенный Selenium парсер (для динамических страниц)
    if IMPROVED_SELENIUM_AVAILABLE:
        try:
            print(f"🔄 Используем улучшенный Selenium парсер для {url}")
            result = parse_appexchange_improved(url)
            
            if result and result.get('success'):
                # Конвертируем в формат AppMetadata
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes = b''
                logo_mime = 'image/png'
                
                # Загружаем изображение если есть URL
                logo_url = result.get('logo_url')
                if logo_url:
                    try:
                        import requests
                        response = requests.get(logo_url, timeout=10)
                        if response.status_code == 200:
                            logo_bytes = response.content
                            logo_mime = response.headers.get('content-type', 'image/png')
                    except Exception as e:
                        print(f"Ошибка загрузки логотипа: {e}")
                
                metadata = AppMetadata(
                    url=url,
                    name=name,
                    developer=developer,
                    logo_bytes=logo_bytes,
                    logo_mime=logo_mime
                )
                
                print(f"✅ Улучшенный Selenium парсер: {metadata.name} by {metadata.developer}")
                return metadata
        except Exception as e:
            print(f"⚠️ Ошибка в улучшенном Selenium парсере: {e}")
    
    # Приоритет 2: Простой Selenium парсер (резервный)
    if SELENIUM_PARSER_AVAILABLE:
        try:
            print(f"🔄 Используем простой Selenium парсер для {url}")
            result = parse_appexchange_simple(url)
            
            if result and result.get('success'):
                # Конвертируем в формат AppMetadata
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes = b''
                logo_mime = 'image/png'
                
                # Загружаем изображение если есть URL
                logo_url = result.get('logo_url')
                if logo_url:
                    try:
                        import requests
                        response = requests.get(logo_url, timeout=10)
                        if response.status_code == 200:
                            logo_bytes = response.content
                            logo_mime = response.headers.get('content-type', 'image/png')
                    except Exception as e:
                        print(f"Ошибка загрузки логотипа: {e}")
                
                metadata = AppMetadata(
                    url=url,
                    name=name,
                    developer=developer,
                    logo_bytes=logo_bytes,
                    logo_mime=logo_mime
                )
                
                print(f"✅ Простой Selenium парсер: {metadata.name} by {metadata.developer}")
                return metadata
        except Exception as e:
            print(f"⚠️ Ошибка в простом Selenium парсере: {e}")
    
    # Приоритет 3: Финальный парсер (резервный)
    if FINAL_PARSER_AVAILABLE:
        try:
            print(f"🔄 Используем финальный парсер для {url}")
            result = parse_appexchange_app(url)
            
            if result and result.get('name') != 'Unknown App':
                # Конвертируем в формат AppMetadata
                name = result.get('name', 'Unknown App')
                developer = result.get('developer', 'Unknown Developer')
                logo_bytes = b''
                logo_mime = 'image/png'
                
                # Загружаем изображение если есть URL
                image_url = result.get('image_url')
                if image_url:
                    try:
                        import requests
                        response = requests.get(image_url, timeout=10)
                        if response.status_code == 200:
                            logo_bytes = response.content
                            logo_mime = response.headers.get('content-type', 'image/png')
                    except:
                        pass
                
                metadata = AppMetadata(
                    url=url,
                    name=name,
                    developer=developer,
                    logo_bytes=logo_bytes,
                    logo_mime=logo_mime
                )
                
                print(f"✅ Финальный парсер: {metadata.name} by {metadata.developer}")
                return metadata
        except Exception as e:
            print(f"⚠️ Ошибка в финальном парсере: {e}")
    
    # Приоритет 4: Оригинальный парсер (последний резерв)
    try:
        print(f"🔄 Используем оригинальный парсер для {url}")
        from sfapps_template_generator import fetch_app_metadata
        metadata = fetch_app_metadata(url)
        if metadata:
            print(f"✅ Оригинальный парсер: {metadata.name} by {metadata.developer}")
            return metadata
    except Exception as e:
        print(f"⚠️ Ошибка в оригинальном парсере: {e}")
    
    # Создаем заглушку, чтобы пользователь мог ввести данные вручную
    print(f"❌ Все парсеры не смогли обработать {url}")
    metadata = AppMetadata(
        url=url,
        name="Не удалось загрузить название",
        developer="Не удалось загрузить разработчика",
        logo_bytes=b'',
        logo_mime='image/png'
    )
    return metadata

def save_uploaded_file(file):
    """Сохранение загруженного файла и возврат пути"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Добавляем уникальный префикс для избежания конфликтов
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return filepath
    return None

def process_form_data(form_data, files):
    """Обработка данных формы и создание структуры для генератора"""
    industry = form_data.get('industry', '').strip()
    final_url = form_data.get('final_url', '').strip()
    
    # Получение списка ссылок
    app_links = form_data.getlist('app_links[]')
    app_names = form_data.getlist('app_names[]')
    app_developers = form_data.getlist('app_developers[]')
    app_logos = files.getlist('app_logos[]')
    
    # Фильтрация пустых ссылок
    app_links = [link.strip() for link in app_links if link.strip()]
    
    if len(app_links) < 1:
        raise ValueError("Необходимо минимум 1 ссылку на приложение")
    
    if len(app_links) > 10:
        raise ValueError("Максимальное количество ссылок: 10")
    
    # Создание словаря переопределений
    overrides = {}
    for i, link in enumerate(app_links):
        override_data = {}
        
        # Имя приложения
        if i < len(app_names) and app_names[i].strip():
            override_data['name'] = app_names[i].strip()
        
        # Разработчик
        if i < len(app_developers) and app_developers[i].strip():
            override_data['developer'] = app_developers[i].strip()
        
        # Логотип
        if i < len(app_logos) and app_logos[i].filename:
            logo_path = save_uploaded_file(app_logos[i])
            if logo_path:
                override_data['logo_path'] = logo_path
        
        if override_data:
            overrides[link] = override_data
    
    return {
        'industry': industry,
        'app_links': app_links,
        'final_url': final_url,
        'overrides': overrides
    }

def create_preview_data(industry, app_links, final_url, overrides):
    """Создание данных для предварительного просмотра"""
    preview_slides = []
    
    # Титульный слайд
    preview_slides.append({
        'title': 'Титульный слайд',
        'content': f'<h4>Best Apps for {industry} Available on AppExchange</h4><p>Extreme Dynamic Forms<br>By Salesforce Labs</p>',
        'image': None
    })
    
    # Слайды с приложениями
    for i, link in enumerate(app_links):
        slide_num = i + 1
        
        # Получение метаданных
        if link in overrides:
            override = overrides[link]
            name = override.get('name', 'Loading...')
            developer = override.get('developer', 'Loading...')
            logo_path = override.get('logo_path')
            
            # Преобразование логотипа в base64 для отображения
            logo_data = None
            if logo_path and os.path.exists(logo_path):
                try:
                    with open(logo_path, 'rb') as f:
                        logo_bytes = f.read()
                        logo_base64 = base64.b64encode(logo_bytes).decode()
                        logo_data = f"data:image/png;base64,{logo_base64}"
                except Exception:
                    pass
        else:
            # Попытка получить данные автоматически
            metadata = fetch_app_metadata_with_fallback(link)
            if metadata and metadata.name != "Не удалось загрузить название":
                name = metadata.name
                developer = metadata.developer
                # Преобразование логотипа в base64
                if metadata.logo_bytes:
                    logo_base64 = base64.b64encode(metadata.logo_bytes).decode()
                    logo_data = f"data:image/png;base64,{logo_base64}"
                else:
                    logo_data = None
            else:
                name = '⚠️ Требуется ручной ввод'
                developer = '⚠️ Требуется ручной ввод'
                logo_data = None
        
        preview_slides.append({
            'title': f'Приложение #{slide_num}',
            'content': f'<h5>{name}</h5><p>{developer}</p><small class="text-muted">{link}</small>',
            'image': logo_data
        })
    
    # Финальный слайд
    preview_slides.append({
        'title': 'Финальный слайд',
        'content': f'<h4>View Full List of Best Salesforce Apps for {industry}</h4><p>Ссылка: <a href="{final_url}" target="_blank">{final_url}</a></p>',
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
        # Обработка данных формы
        data = process_form_data(request.form, request.files)
        industry = data['industry']
        app_links = data['app_links']
        final_url = data['final_url']
        overrides = data['overrides']
        
        # Проверка на предварительный просмотр
        if request.form.get('preview') == 'true':
            preview_data = create_preview_data(industry, app_links, final_url, overrides)
            return jsonify({'success': True, 'preview': preview_data})
        
        # Определение формата выходного файла
        output_format = request.form.get('format', 'pptx')
        
        # Путь к шаблону
        template_path = 'Copy of SFApps.info Best Apps Presentation Template.pptx'
        if not os.path.exists(template_path):
            flash('Шаблон презентации не найден', 'error')
            return redirect(url_for('index'))
        
        # Создание временных файлов для выходных документов
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as tmp_pptx:
            output_pptx = tmp_pptx.name
        
        output_pdf = None
        if output_format == 'pdf':
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                output_pdf = tmp_pdf.name
        
        try:
            # Генерация презентации
            create_presentation_from_template(
                topic=industry,
                links=app_links,
                final_url=final_url,
                template_path=template_path,
                output_pptx=output_pptx,
                output_pdf=output_pdf,
                app_overrides=overrides
            )
            
            # Выбор файла для отправки
            if output_format == 'pdf' and output_pdf and os.path.exists(output_pdf):
                send_file_path = output_pdf
                mimetype = 'application/pdf'
                filename = f'Best_Apps_for_{industry}.pdf'
            else:
                send_file_path = output_pptx
                mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                filename = f'Best_Apps_for_{industry}.pptx'
            
            # Отправка файла
            return send_file(
                send_file_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )
            
        finally:
            # Очистка временных файлов
            try:
                if os.path.exists(output_pptx):
                    os.unlink(output_pptx)
                if output_pdf and os.path.exists(output_pdf):
                    os.unlink(output_pdf)
            except Exception:
                pass
            
            # Очистка загруженных файлов логотипов
            for override in overrides.values():
                logo_path = override.get('logo_path')
                if logo_path and os.path.exists(logo_path):
                    try:
                        os.unlink(logo_path)
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