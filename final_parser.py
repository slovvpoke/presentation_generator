"""
Финальный рабочий парсер AppExchange
===================================

Оптимизированный парсер который правильно извлекает данные из AppExchange
используя OpenGraph теги и JSON данные.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_appexchange_app(url):
    """
    Парсит данные приложения с AppExchange используя OpenGraph и JSON данные
    
    Args:
        url (str): URL страницы приложения на AppExchange
    
    Returns:
        dict: Словарь с данными приложения (name, developer, image_url)
    """
    result = {
        'name': 'Unknown App',
        'developer': 'Unknown Developer', 
        'image_url': None
    }
    
    try:
        # Заголовки для имитации браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        logger.info(f"Получение данных из URL: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Извлечение из OpenGraph мета-тегов (ОСНОВНОЙ метод для AppExchange)
        result = extract_from_opengraph(soup, result)
        
        # 2. Извлечение из JSON данных в script тегах
        result = extract_from_json(soup, result)
        
        # 3. Извлечение разработчика из description если не найден
        if result['developer'] == 'Unknown Developer':
            result = extract_developer_from_description(soup, result)
        
        # 4. Финальная очистка и валидация данных
        result = clean_and_validate_data(result)
        
        logger.info(f"Результат парсинга: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при парсинге {url}: {e}")
        return result

def extract_from_opengraph(soup, result):
    """Извлекает данные из OpenGraph мета-тегов"""
    
    # Название из og:title
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title = og_title.get('content').strip()
        # Убираем часть про AppExchange из названия
        title = re.sub(r'\s*\|\s*.*AppExchange.*$', '', title, flags=re.IGNORECASE)
        if title and len(title) > 3:
            result['name'] = title
            logger.info(f"OpenGraph название: {title}")
    
    # Изображение из og:image
    og_image = soup.find('meta', property='og:image')
    if og_image and og_image.get('content'):
        image_url = og_image.get('content').strip()
        if image_url.startswith('http'):
            result['image_url'] = image_url
            logger.info(f"OpenGraph изображение: {image_url}")
    
    # Описание из og:description для поиска разработчика
    og_description = soup.find('meta', property='og:description')
    if og_description and og_description.get('content'):
        description = og_description.get('content').strip()
        developer = extract_developer_from_text(description)
        if developer:
            result['developer'] = developer
            logger.info(f"OpenGraph разработчик: {developer}")
    
    return result

def extract_from_json(soup, result):
    """Извлекает данные из JSON структур в script тегах"""
    
    scripts = soup.find_all('script', type='application/ld+json')
    
    for script in scripts:
        try:
            data = json.loads(script.string)
            
            # Поиск в структуре Organization
            if isinstance(data, dict):
                # Название приложения
                if 'name' in data and data['name'] and result['name'] == 'Unknown App':
                    name = data['name'].strip()
                    if 'AppExchange' not in name:  # Избегаем названия самого AppExchange
                        result['name'] = name
                        logger.info(f"JSON название: {name}")
                
                # Изображение
                if 'image' in data and data['image'] and not result['image_url']:
                    if isinstance(data['image'], dict) and 'url' in data['image']:
                        result['image_url'] = data['image']['url']
                    elif isinstance(data['image'], str):
                        result['image_url'] = data['image']
                    logger.info(f"JSON изображение: {result['image_url']}")
                
                # Поиск разработчика в различных полях
                developer_fields = ['publisher', 'author', 'developer', 'organization', 'creator']
                for field in developer_fields:
                    if field in data and data[field] and result['developer'] == 'Unknown Developer':
                        dev_info = data[field]
                        if isinstance(dev_info, dict) and 'name' in dev_info:
                            result['developer'] = f"By {dev_info['name']}"
                        elif isinstance(dev_info, str):
                            result['developer'] = f"By {dev_info}"
                        logger.info(f"JSON разработчик: {result['developer']}")
                        break
                        
        except json.JSONDecodeError:
            continue
    
    return result

def extract_developer_from_description(soup, result):
    """Извлекает разработчика из description тегов"""
    
    # Поиск в мета description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        description = meta_desc.get('content')
        developer = extract_developer_from_text(description)
        if developer:
            result['developer'] = developer
            logger.info(f"Meta description разработчик: {developer}")
    
    return result

def extract_developer_from_text(text):
    """Извлекает разработчика из текста используя паттерны"""
    
    if not text:
        return None
    
    # Паттерны для поиска разработчика
    patterns = [
        r'(\w+)\s+is\s+the\s+top',  # "TaskRay is the top"
        r'By\s+(\w+)',              # "By TaskRay" 
        r'from\s+(\w+)',            # "from TaskRay"
        r'developed\s+by\s+(\w+)',  # "developed by TaskRay"
        r'built\s+by\s+(\w+)',      # "built by TaskRay"
        r'(\w+)\s+helps\s+teams',   # "TaskRay helps teams"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            developer = match.group(1).strip()
            if len(developer) > 2 and developer.lower() not in ['the', 'and', 'this', 'that']:
                return f"By {developer}"
    
    return None

def clean_and_validate_data(result):
    """Очищает и валидирует извлеченные данные"""
    
    # Очистка названия
    if result['name'] != 'Unknown App':
        # Убираем лишние символы и нормализуем пробелы
        result['name'] = re.sub(r'\s+', ' ', result['name']).strip()
        
        # Убираем части про Salesforce/AppExchange из названия
        name_clean_patterns = [
            r'\s*\|\s*.*AppExchange.*$',
            r'\s*\|\s*.*Salesforce.*$',
            r'^\s*Salesforce\s*-?\s*',
        ]
        
        for pattern in name_clean_patterns:
            result['name'] = re.sub(pattern, '', result['name'], flags=re.IGNORECASE).strip()
    
    # Валидация изображения
    if result['image_url']:
        if not result['image_url'].startswith('http'):
            result['image_url'] = None
    
    # Очистка разработчика
    if result['developer'] != 'Unknown Developer':
        result['developer'] = re.sub(r'\s+', ' ', result['developer']).strip()
        # Убеждаемся что есть "By"
        if not result['developer'].lower().startswith('by '):
            result['developer'] = f"By {result['developer']}"
    
    return result

# Пример использования
if __name__ == "__main__":
    test_url = "https://appexchange.salesforce.com/appxListingDetail?listingId=a0N300000055lKwEAI&channel=featured&placement=a0d3A000007VqCzQAK"
    
    print("=== ТЕСТ ФИНАЛЬНОГО ПАРСЕРА ===")
    result = parse_appexchange_app(test_url)
    
    print(f"\nРезультат:")
    print(f"Название: {result['name']}")
    print(f"Разработчик: {result['developer']}")
    print(f"Изображение: {result['image_url']}")