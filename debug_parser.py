#!/usr/bin/env python3
"""
Отладочный скрипт для анализа структуры HTML страницы AppExchange
"""

import requests
from bs4 import BeautifulSoup
import re

def analyze_page_structure(url):
    """Анализ структуры HTML страницы"""
    print(f"🔍 Анализ структуры страницы: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print(f"✅ Страница загружена (размер: {len(response.text):,} символов)")
        
        # Поиск заголовков
        print("\n🔍 Поиск заголовков (h1, h2, h3):")
        for tag in ['h1', 'h2', 'h3']:
            elements = soup.find_all(tag)
            for i, elem in enumerate(elements[:5]):  # Показываем первые 5
                text = elem.get_text().strip()[:100]
                print(f"   {tag.upper()} #{i+1}: {text}")
        
        # Поиск элементов с классами, содержащими 'title'
        print("\n🔍 Элементы с классами содержащими 'title':")
        title_elements = soup.find_all(attrs={'class': re.compile(r'title', re.I)})
        for i, elem in enumerate(title_elements[:10]):
            classes = ' '.join(elem.get('class', []))
            text = elem.get_text().strip()[:100]
            print(f"   #{i+1} .{classes}: {text}")
        
        # Поиск элементов с классами, содержащими 'listing'
        print("\n🔍 Элементы с классами содержащими 'listing':")
        listing_elements = soup.find_all(attrs={'class': re.compile(r'listing', re.I)})
        for i, elem in enumerate(listing_elements[:10]):
            classes = ' '.join(elem.get('class', []))
            text = elem.get_text().strip()[:100]
            print(f"   #{i+1} .{classes}: {text}")
        
        # Поиск изображений
        print("\n🔍 Поиск изображений:")
        images = soup.find_all('img')
        for i, img in enumerate(images[:10]):
            classes = ' '.join(img.get('class', []))
            src = img.get('src', '')[:100]
            alt = img.get('alt', '')[:50]
            print(f"   IMG #{i+1}: class='{classes}' src='{src}' alt='{alt}'")
        
        # Поиск элементов с 'By' в тексте
        print("\n🔍 Элементы содержащие 'By' в тексте:")
        by_elements = soup.find_all(string=re.compile(r'By\s+', re.I))
        for i, text in enumerate(by_elements[:5]):
            parent = text.parent
            classes = ' '.join(parent.get('class', [])) if parent.get('class') else 'no-class'
            print(f"   #{i+1} .{classes}: {text.strip()}")
        
        # OpenGraph метаданные
        print("\n🔍 OpenGraph метаданные:")
        og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
        for tag in og_tags:
            property_name = tag.get('property')
            content = tag.get('content', '')[:100]
            print(f"   {property_name}: {content}")
        
        # Поиск скриптов с JSON данными
        print("\n🔍 Поиск JSON данных в скриптах:")
        scripts = soup.find_all('script', type='application/json')
        for i, script in enumerate(scripts[:3]):
            content = script.get_text()[:200]
            print(f"   JSON #{i+1}: {content}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        return False

def main():
    """Главная функция анализа"""
    print("=" * 80)
    print("🕵️ Отладка парсера AppExchange - Анализ структуры HTML")
    print("=" * 80)
    
    # Тестовый URL
    test_url = 'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ'
    
    analyze_page_structure(test_url)

if __name__ == '__main__':
    main()