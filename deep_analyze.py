#!/usr/bin/env python3
"""
Анализ реальной структуры AppExchange страниц для создания надежного парсера
"""

import requests
import time
import json
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def analyze_with_selenium(url):
    """Глубокий анализ страницы с помощью Selenium"""
    print(f"🔍 Анализ с Selenium: {url}")
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        driver.get(url)
        
        # Ждем загрузки контента
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Дополнительное ожидание для загрузки динамического контента
        time.sleep(5)
        
        # Получаем финальный HTML
        html = driver.page_source
        driver.quit()
        
        return html
        
    except Exception as e:
        print(f"❌ Ошибка Selenium: {e}")
        if 'driver' in locals():
            driver.quit()
        return None

def extract_all_possible_data(html):
    """Извлечение всех возможных данных из HTML"""
    soup = BeautifulSoup(html, 'html.parser')
    
    print("\n🔍 ПОИСК НАЗВАНИЯ ПРИЛОЖЕНИЯ:")
    
    # Поиск в title тегах
    title = soup.find('title')
    if title:
        print(f"   <title>: {title.get_text()[:100]}")
    
    # Поиск во всех h1 тегах
    h1_tags = soup.find_all('h1')
    for i, h1 in enumerate(h1_tags):
        text = h1.get_text().strip()
        if text and len(text) > 3:
            print(f"   H1 #{i+1}: {text[:100]}")
    
    # Поиск во всех h2 тегах
    h2_tags = soup.find_all('h2')
    for i, h2 in enumerate(h2_tags[:5]):  # Первые 5
        text = h2.get_text().strip()
        if text and len(text) > 3:
            print(f"   H2 #{i+1}: {text[:100]}")
    
    print("\n🔍 ПОИСК РАЗРАБОТЧИКА:")
    
    # Поиск всех элементов содержащих "By"
    by_elements = soup.find_all(string=re.compile(r'By\s+', re.IGNORECASE))
    for i, element in enumerate(by_elements[:10]):
        text = element.strip()
        if text and len(text) > 3:
            print(f"   By #{i+1}: {text[:100]}")
    
    # Поиск в параграфах
    p_tags = soup.find_all('p')
    for i, p in enumerate(p_tags[:10]):
        text = p.get_text().strip()
        if 'by' in text.lower() and len(text) < 100:
            print(f"   P #{i+1}: {text}")
    
    print("\n🔍 ПОИСК ЛОГОТИПОВ:")
    
    # Поиск всех изображений
    img_tags = soup.find_all('img')
    for i, img in enumerate(img_tags[:15]):
        src = img.get('src', '')
        alt = img.get('alt', '')
        classes = ' '.join(img.get('class', []))
        if src and ('logo' in src.lower() or 'logo' in alt.lower() or 'logo' in classes.lower()):
            print(f"   IMG #{i+1}: src='{src[:100]}' alt='{alt}' class='{classes}'")
    
    print("\n🔍 ПОИСК В JSON ДАННЫХ:")
    
    # Поиск JSON данных в script тегах
    script_tags = soup.find_all('script')
    for i, script in enumerate(script_tags):
        text = script.get_text()
        if 'name' in text and 'publisher' in text and len(text) > 50:
            print(f"   SCRIPT #{i+1}: {text[:200]}...")
            
            # Попытка извлечь JSON
            json_patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
                r'window\.__APP_DATA__\s*=\s*({.+?});',
                r'__NEXT_DATA__\s*=\s*({.+?})',
                r'window\.pageData\s*=\s*({.+?});',
                r'"name"\s*:\s*"([^"]+)"',
                r'"publisher"\s*:\s*"([^"]+)"'
            ]
            
            for pattern in json_patterns:
                matches = re.findall(pattern, text, re.DOTALL)
                if matches:
                    print(f"      Найден паттерн: {pattern[:50]}... -> {str(matches[:2])}")

def analyze_meta_tags(html):
    """Анализ всех мета-тегов"""
    soup = BeautifulSoup(html, 'html.parser')
    
    print("\n🔍 АНАЛИЗ МЕТА-ТЕГОВ:")
    
    # OpenGraph теги
    og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
    for tag in og_tags:
        prop = tag.get('property')
        content = tag.get('content', '')[:100]
        print(f"   {prop}: {content}")
    
    # Twitter теги
    twitter_tags = soup.find_all('meta', name=re.compile(r'^twitter:'))
    for tag in twitter_tags:
        name = tag.get('name')
        content = tag.get('content', '')[:100]
        print(f"   {name}: {content}")
    
    # Другие важные теги
    important_tags = ['description', 'keywords', 'application-name']
    for tag_name in important_tags:
        tag = soup.find('meta', name=tag_name)
        if tag:
            content = tag.get('content', '')[:100]
            print(f"   {tag_name}: {content}")

def main():
    """Главная функция анализа"""
    test_url = 'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ'
    
    print("=" * 80)
    print("🕵️ ГЛУБОКИЙ АНАЛИЗ СТРУКТУРЫ APPEXCHANGE СТРАНИЦЫ")
    print("=" * 80)
    
    # Анализ с Selenium
    html = analyze_with_selenium(test_url)
    
    if html:
        print(f"\n✅ HTML получен, размер: {len(html):,} символов")
        
        # Сохраним HTML для ручного анализа
        with open('appexchange_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("💾 HTML сохранен в appexchange_page.html")
        
        # Анализируем структуру
        extract_all_possible_data(html)
        analyze_meta_tags(html)
        
    else:
        print("❌ Не удалось получить HTML")

if __name__ == '__main__':
    main()