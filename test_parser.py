#!/usr/bin/env python3
"""
Тестирование нового парсера AppExchange с обновленными CSS селекторами
"""

import requests
from sfapps_template_generator import _extract_from_html, fetch_app_metadata

def test_extraction_with_url(url):
    """Тест извлечения данных с конкретного URL"""
    print(f"🔍 Тестирование URL: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Получение HTML
        print("📥 Загрузка страницы...")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        print(f"✅ Страница загружена (размер: {len(response.text):,} символов)")
        
        # Извлечение данных
        name, developer, logo_url = _extract_from_html(response.text)
        
        print("\n📊 Результаты извлечения:")
        print(f"   📱 Название: {name or '❌ Не найдено'}")
        print(f"   👥 Разработчик: {developer or '❌ Не найдено'}")
        print(f"   🖼️  Логотип URL: {logo_url or '❌ Не найдено'}")
        
        # Тест полного метода fetch_app_metadata
        print("\n🔄 Тестирование fetch_app_metadata...")
        metadata = fetch_app_metadata(url)
        
        if metadata:
            print("✅ Метаданные получены:")
            print(f"   📱 Название: {metadata.name}")
            print(f"   👥 Разработчик: {metadata.developer}")
            print(f"   🖼️  Логотип: {len(metadata.logo_bytes):,} байт")
            print(f"   📄 MIME: {metadata.logo_mime}")
            return True
        else:
            print("❌ Не удалось получить метаданные")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        return False

def main():
    """Главная функция тестирования"""
    print("=" * 70)
    print("🧪 Тестирование обновленного парсера AppExchange")
    print("=" * 70)
    
    # Тестовые URL
    test_urls = [
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ',  # DocuSign
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD',  # Conga Composer
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3A00000EFpq5UAD',  # LoanBeam
    ]
    
    successful_tests = 0
    total_tests = len(test_urls)
    
    for i, url in enumerate(test_urls, 1):
        print(f"\n{'='*50}")
        print(f"📋 Тест {i}/{total_tests}")
        print(f"{'='*50}")
        
        if test_extraction_with_url(url):
            successful_tests += 1
        
        print("\n" + "-" * 50)
    
    # Итоги
    print(f"\n{'='*70}")
    print(f"📊 Результаты тестирования: {successful_tests}/{total_tests} успешно")
    
    if successful_tests == total_tests:
        print("🎉 Все тесты пройдены! Парсер работает корректно.")
    elif successful_tests > 0:
        print("⚠️  Частично работает. Возможны проблемы с некоторыми страницами.")
    else:
        print("❌ Парсер не работает. Проверьте селекторы и сетевое соединение.")
    
    return successful_tests == total_tests

if __name__ == '__main__':
    main()