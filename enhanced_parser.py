"""
Улучшенный парсер AppExchange с поддержкой динамических страниц
============================================================

Этот модуль расширяет возможности оригинального парсера, добавляя:
- Поддержку динамически загружаемого контента через Selenium
- Множественные стратегии извлечения данных
- Лучшую обработку ошибок
"""

import os
import time
from typing import Optional, Tuple
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

# Опциональный импорт Selenium
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from sfapps_template_generator import AppMetadata


class EnhancedAppExchangeParser:
    """Улучшенный парсер для AppExchange с поддержкой динамических страниц"""
    
    def __init__(self, use_selenium=False, headless=True):
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.headless = headless
        self.driver = None
        
        # Заголовки для HTTP запросов
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def __enter__(self):
        if self.use_selenium:
            self._setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()
    
    def _setup_driver(self):
        """Настройка Selenium WebDriver"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium не установлен. Установите: pip install selenium webdriver-manager")
        
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.headers["User-Agent"]}')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            
        except Exception as e:
            print(f"Ошибка настройки WebDriver: {e}")
            self.driver = None
            self.use_selenium = False
    
    def fetch_page_content(self, url: str, timeout: int = 20) -> Optional[str]:
        """Получение содержимого страницы"""
        
        if self.use_selenium and self.driver:
            try:
                print(f"Использование Selenium для загрузки: {url}")
                self.driver.get(url)
                
                # Ожидание загрузки контента
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Дополнительная пауза для загрузки динамического контента
                time.sleep(3)
                
                return self.driver.page_source
                
            except Exception as e:
                print(f"Ошибка Selenium: {e}, переключение на requests")
        
        # Fallback на обычный HTTP запрос
        try:
            print(f"Использование requests для загрузки: {url}")
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Ошибка HTTP запроса: {e}")
            return None
    
    def extract_app_metadata(self, html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечение метаданных приложения из HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        name = None
        developer = None
        logo_url = None
        
        # Стратегия 1: CSS селекторы (приоритетная стратегия)
        name, developer, logo_url = self._extract_from_css_selectors(soup)
        print(f"CSS селекторы: name='{name}', developer='{developer}', logo_url='{logo_url}'")
        
        # Стратегия 2: Поиск в JSON данных (если CSS не сработал)
        if not all([name, developer, logo_url]):
            name2, developer2, logo_url2 = self._extract_from_json(soup)
            name = name or name2
            developer = developer or developer2
            logo_url = logo_url or logo_url2
        
        # Стратегия 3: OpenGraph метаданные (финальный fallback)
        if not all([name, developer, logo_url]):
            name3, developer3, logo_url3 = self._extract_from_meta_tags(soup)
            name = name or name3
            developer = developer or developer3
            logo_url = logo_url or logo_url3
        
        return name, developer, logo_url
    
    def _extract_from_json(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечение данных из JSON скриптов"""
        import json
        import re
        
        name = None
        developer = None
        logo_url = None
        
        # Поиск в script тегах с application/json
        script_tags = soup.find_all('script', type='application/json')
        for script in script_tags:
            try:
                data = json.loads(script.get_text())
                name, developer, logo_url = self._search_json_data(data)
                if name and developer:
                    break
            except:
                continue
        
        # Поиск в обычных script тегах с JSON данными
        if not name:
            script_tags = soup.find_all('script')
            for script in script_tags:
                text = script.get_text()
                # Поиск паттернов JSON в JavaScript
                json_patterns = [
                    r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                    r'window\.__APP_DATA__\s*=\s*({.+?});',
                    r'__NEXT_DATA__\s*=\s*({.+?})',
                    r'window\.pageData\s*=\s*({.+?});'
                ]
                
                for pattern in json_patterns:
                    match = re.search(pattern, text, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            name, developer, logo_url = self._search_json_data(data)
                            if name and developer:
                                break
                        except:
                            continue
                if name and developer:
                    break
        
        return name, developer, logo_url
    
    def _search_json_data(self, data, depth=0, max_depth=5):
        """Рекурсивный поиск данных приложения в JSON структуре"""
        if depth > max_depth or not isinstance(data, (dict, list)):
            return None, None, None
        
        if isinstance(data, dict):
            # Поиск прямых совпадений
            if 'name' in data and 'publisher' in data:
                return data.get('name'), data.get('publisher'), data.get('logoUrl') or data.get('logo')
            
            if 'title' in data and 'developer' in data:
                return data.get('title'), data.get('developer'), data.get('imageUrl') or data.get('image')
            
            # Поиск в подобъектах
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    name, dev, logo = self._search_json_data(value, depth + 1, max_depth)
                    if name and dev:
                        return name, dev, logo
        
        elif isinstance(data, list):
            for item in data:
                name, dev, logo = self._search_json_data(item, depth + 1, max_depth)
                if name and dev:
                    return name, dev, logo
        
        return None, None, None
    
    def _extract_from_css_selectors(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечение данных через CSS селекторы"""
        name = None
        developer = None
        logo_url = None
        
        # Расширенные селекторы для названия
        name_selectors = [
            '.listing-title h1',
            'h1[data-test-id="listing-title"]',
            'h1.listing-header__title',
            '[data-testid="listing-title"]',
            '.app-title',
            '.listing-name',
            '.page-header h1',
            '.solution-title',
            '[data-cy="listing-title"]'
        ]
        
        for selector in name_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text().strip()
                if text:  # Убеждаемся что текст не пустой
                    name = text
                    print(f"Найдено название через селектор '{selector}': {name}")
                    break
        
        # Расширенные селекторы для разработчика
        dev_selectors = [
            '.listing-title p',
            '[data-test-id="listing-publisher"]',
            '.listing-header__publisher',
            '[data-testid="listing-publisher"]',
            '.app-publisher',
            '.listing-publisher',
            '.publisher-name',
            '.solution-publisher',
            '[data-cy="listing-publisher"]'
        ]
        
        for selector in dev_selectors:
            element = soup.select_one(selector)
            if element:
                dev_text = element.get_text().strip()
                if dev_text:  # Убеждаемся что текст не пустой
                    if dev_text.lower().startswith('by '):
                        developer = dev_text[3:].strip()
                    else:
                        developer = dev_text
                    print(f"Найден разработчик через селектор '{selector}': {developer}")
                    break
        
        # Расширенные селекторы для логотипа
        logo_selectors = [
            '.summary .listing-logo .ads-image',
            '[data-test-id="listing-logo"] img',
            '.listing-header__logo img',
            '[data-testid="listing-logo"] img',
            '.app-logo img',
            '.listing-logo img',
            '.solution-logo img',
            '.publisher-logo img',
            '[data-cy="listing-logo"] img'
        ]
        
        for selector in logo_selectors:
            element = soup.select_one(selector)
            if element:
                logo_url = (element.get('src') or 
                           element.get('data-src') or 
                           element.get('data-original') or 
                           element.get('data-lazy') or
                           element.get('data-srcset', '').split(',')[0].strip().split(' ')[0])
                if logo_url:
                    print(f"Найден логотип через селектор '{selector}': {logo_url}")
                    break
        
        return name, developer, logo_url
    
    def _extract_from_meta_tags(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Извлечение данных из мета-тегов"""
        name = None
        developer = None
        logo_url = None
        
        # OpenGraph заголовок
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title_content = og_title['content']
            if '|' in title_content:
                name = title_content.split('|')[0].strip()
            else:
                name = title_content.strip()
        
        # OpenGraph изображение
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            logo_url = og_image['content']
        
        # Twitter метаданные для разработчика
        twitter_data1 = soup.find('meta', attrs={'name': 'twitter:data1'})
        if twitter_data1 and twitter_data1.get('content'):
            developer = twitter_data1['content'].strip()
        
        # Поиск в описании страницы
        if not developer:
            description = soup.find('meta', attrs={'name': 'description'})
            if description and description.get('content'):
                desc_text = description['content']
                # Поиск паттерна "By Company Name"
                import re
                by_match = re.search(r'By\s+([^,\.\|]+)', desc_text, re.IGNORECASE)
                if by_match:
                    developer = by_match.group(1).strip()
        
        return name, developer, logo_url
    
    def fetch_app_metadata(self, url: str, timeout: int = 20) -> Optional[AppMetadata]:
        """Получение полных метаданных приложения"""
        try:
            # Получение HTML контента
            html = self.fetch_page_content(url, timeout)
            if not html:
                return None
            
            # Извлечение данных
            name, developer, logo_url = self.extract_app_metadata(html)
            
            if not name:
                print(f"Не удалось извлечь название приложения")
                return None
            
            # Загрузка логотипа
            logo_bytes = b''
            logo_mime = 'image/png'
            
            if logo_url:
                try:
                    # Обработка относительных URL
                    if logo_url.startswith('//'):
                        logo_url = 'https:' + logo_url
                    elif logo_url.startswith('/'):
                        from urllib.parse import urljoin, urlparse
                        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                        logo_url = urljoin(base_url, logo_url)
                    
                    print(f"Загрузка логотипа: {logo_url}")
                    logo_response = requests.get(logo_url, headers=self.headers, timeout=10)
                    logo_response.raise_for_status()
                    
                    logo_bytes = logo_response.content
                    logo_mime = logo_response.headers.get('Content-Type', 'image/png')
                    
                    # Валидация изображения
                    try:
                        with Image.open(BytesIO(logo_bytes)) as img:
                            # Проверка размера (избегаем слишком маленькие изображения)
                            if img.width < 10 or img.height < 10:
                                print(f"Логотип слишком маленький: {img.width}x{img.height}")
                                logo_bytes = b''
                    except Exception as e:
                        print(f"Ошибка валидации изображения: {e}")
                        logo_bytes = b''
                        
                except Exception as e:
                    print(f"Ошибка загрузки логотипа: {e}")
            
            return AppMetadata(
                url=url,
                name=name or 'Unknown App',
                developer=developer or 'Unknown Developer',
                logo_bytes=logo_bytes,
                logo_mime=logo_mime
            )
            
        except Exception as e:
            print(f"Ошибка получения метаданных: {e}")
            return None


# Обновленная функция для замены оригинальной
def enhanced_fetch_app_metadata(url: str, timeout: int = 20, use_selenium: bool = False) -> Optional[AppMetadata]:
    """
    Улучшенная версия fetch_app_metadata с поддержкой динамических страниц
    
    Parameters
    ----------
    url: str
        URL AppExchange страницы
    timeout: int
        Таймаут для запросов
    use_selenium: bool
        Использовать ли Selenium для динамических страниц
    
    Returns
    -------
    AppMetadata or None
    """
    with EnhancedAppExchangeParser(use_selenium=use_selenium) as parser:
        return parser.fetch_app_metadata(url, timeout)


if __name__ == '__main__':
    # Тестирование улучшенного парсера
    test_urls = [
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ',
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD'
    ]
    
    print("🧪 Тестирование улучшенного парсера")
    print("=" * 50)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n📋 Тест {i}: {url}")
        
        # Сначала пробуем без Selenium
        print("\n🔄 Тест без Selenium:")
        metadata = enhanced_fetch_app_metadata(url, use_selenium=False)
        if metadata:
            print(f"✅ Название: {metadata.name}")
            print(f"✅ Разработчик: {metadata.developer}")
            print(f"✅ Логотип: {len(metadata.logo_bytes)} байт")
        else:
            print("❌ Не удалось извлечь данные")
        
        # Затем пробуем с Selenium (если доступен)
        if SELENIUM_AVAILABLE:
            print("\n🤖 Тест с Selenium:")
            metadata = enhanced_fetch_app_metadata(url, use_selenium=True)
            if metadata:
                print(f"✅ Название: {metadata.name}")
                print(f"✅ Разработчик: {metadata.developer}")
                print(f"✅ Логотип: {len(metadata.logo_bytes)} байт")
            else:
                print("❌ Не удалось извлечь данные")
        else:
            print("\n⚠️ Selenium недоступен")