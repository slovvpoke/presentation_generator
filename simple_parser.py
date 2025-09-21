#!/usr/bin/env python3
"""
Простой и надежный парсер AppExchange
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import requests
from PIL import Image
from io import BytesIO

def parse_appexchange_simple(url):
    """
    Простая функция парсинга - ждем загрузки и берем данные
    """
    print(f"🔍 Парсинг: {url}")
    
    # Настройки Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')
    
    driver = None
    try:
        # Запускаем браузер
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Открываем страницу
        driver.get(url)
        
        # Ждем загрузки (увеличиваем время ожидания)
        print("⏳ Ждем загрузки страницы...")
        time.sleep(8)  # Даем время на загрузку JavaScript
        
        # Ищем название приложения по разным селекторам
        app_name = None
        name_selectors = [
            'h1[data-aura-rendered-by]',  # Основной селектор для заголовка
            'h1.appName',
            '.appName h1',
            'h1',
            '.listing-header h1',
            '.app-title',
            '[data-testid="app-name"]'
        ]
        
        for selector in name_selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    app_name = element.text.strip()
                    print(f"✅ Название найдено: {app_name}")
                    break
            except:
                continue
        
        # Ищем разработчика
        developer = None
        dev_selectors = [
            '.appPublisher',
            '.publisher-name',
            '.developer-name',
            '[data-testid="publisher"]',
            'a[href*="publisher"]'
        ]
        
        for selector in dev_selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element and element.text.strip():
                    developer = element.text.strip()
                    print(f"✅ Разработчик найден: {developer}")
                    break
            except:
                continue
        
        # Ищем логотип
        logo_url = None
        logo_selectors = [
            '.appIcon img',
            '.app-logo img',
            '.listing-icon img',
            'img[alt*="logo"]',
            'img[alt*="icon"]'
        ]
        
        for selector in logo_selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                src = element.get_attribute('src')
                if src and ('http' in src or src.startswith('//')):
                    logo_url = src
                    if src.startswith('//'):
                        logo_url = 'https:' + src
                    print(f"✅ Логотип найден: {logo_url}")
                    break
            except:
                continue
        
        # Если название не найдено, берем из title страницы
        if not app_name:
            try:
                title = driver.title
                if title and 'AppExchange' in title:
                    # Убираем "- AppExchange" из конца
                    app_name = title.replace(' - AppExchange', '').strip()
                    print(f"✅ Название из title: {app_name}")
            except:
                pass
        
        # Если разработчик не найден, пытаемся найти в тексте
        if not developer:
            try:
                # Ищем текст типа "by Company Name"
                page_text = driver.page_source
                import re
                match = re.search(r'by\s+([A-Za-z0-9\s,\.]+?)(?:\s|<|$)', page_text, re.IGNORECASE)
                if match:
                    developer = match.group(1).strip()
                    print(f"✅ Разработчик из текста: {developer}")
            except:
                pass
        
        return {
            'name': app_name or 'Unknown App',
            'developer': developer or 'Unknown Developer', 
            'logo_url': logo_url,
            'success': bool(app_name)
        }
        
    except Exception as e:
        print(f"❌ Ошибка парсинга: {e}")
        return {
            'name': 'Parsing Error',
            'developer': 'Unknown',
            'logo_url': None,
            'success': False,
            'error': str(e)
        }
    finally:
        if driver:
            driver.quit()

def download_logo(logo_url, target_size=(100, 100)):
    """
    Скачивает и обрабатывает логотип
    """
    if not logo_url:
        return None
        
    try:
        response = requests.get(logo_url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        }, timeout=10)
        
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            
            # Конвертируем в RGB если нужно
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Изменяем размер
            image.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # Сохраняем в BytesIO
            output = BytesIO()
            image.save(output, format='PNG')
            output.seek(0)
            return output
            
    except Exception as e:
        print(f"❌ Ошибка загрузки логотипа {logo_url}: {e}")
        return None

# Тест
if __name__ == "__main__":
    test_url = "https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3A00000B5XxXUAV"
    result = parse_appexchange_simple(test_url)
    print(f"\n📊 Результат: {result}")