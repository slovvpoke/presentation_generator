#!/usr/bin/env python3
"""
Тестовый скрипт для детального анализа страницы AppExchange
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time

def debug_page():
    """Детальный анализ страницы"""
    url = "https://appexchange.salesforce.com/appxListingDetail?listingId=01dbaf61-02e0-4bc8-a8db-2ddbf30719ed"
    
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get(url)
        time.sleep(15)  # Ждем еще дольше
        
        print("=== АНАЛИЗ СТРАНИЦЫ ===")
        print(f"Title: {driver.title}")
        print()
        
        # Ищем все элементы с текстом "By"
        print("=== ЭЛЕМЕНТЫ С 'BY' ===")
        by_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'By')]")
        for i, elem in enumerate(by_elements[:10]):  # Только первые 10
            print(f"{i+1}. '{elem.text}' (tag: {elem.tag_name})")
        
        print()
        
        # Ищем все элементы с "Certinia"
        print("=== ЭЛЕМЕНТЫ С 'CERTINIA' ===")
        certinia_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Certinia')]")
        for i, elem in enumerate(certinia_elements[:10]):
            print(f"{i+1}. '{elem.text}' (tag: {elem.tag_name})")
        
        print()
        
        # Ищем в исходном коде
        print("=== ПОИСК В ИСХОДНОМ КОДЕ ===")
        source = driver.page_source
        
        # Ищем "By" в контексте
        import re
        by_contexts = []
        for match in re.finditer(r'.{0,30}By\s+[^<>]{3,30}.{0,30}', source, re.IGNORECASE):
            context = match.group(0)
            if 'certinia' in context.lower():
                by_contexts.append(context.strip())
        
        print("Контексты с 'By' и 'Certinia':")
        for ctx in by_contexts[:5]:
            print(f"  - {ctx}")
        
        # Все вхождения Certinia
        certinia_contexts = []
        for match in re.finditer(r'.{0,50}Certinia.{0,50}', source, re.IGNORECASE):
            context = match.group(0)
            certinia_contexts.append(context.strip())
        
        print("\nВсе контексты с 'Certinia':")
        for ctx in certinia_contexts[:10]:
            print(f"  - {ctx}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_page()