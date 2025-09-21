#!/usr/bin/env python3
"""
Быстрый тест обновленного парсера
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from enhanced_parser import enhanced_fetch_app_metadata
    
    # Тестовый URL AppExchange
    test_url = "https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ"
    
    print("🧪 Тестирование обновленного парсера")
    print("=" * 50)
    print(f"URL: {test_url}")
    print()
    
    print("🔄 Тестирование без Selenium:")
    metadata = enhanced_fetch_app_metadata(test_url, use_selenium=False)
    
    if metadata:
        print(f"✅ Название: {metadata.name}")
        print(f"✅ Разработчик: {metadata.developer}")
        print(f"✅ Логотип: {len(metadata.logo_bytes)} байт")
        print(f"✅ MIME логотипа: {metadata.logo_mime}")
        
        if metadata.name and metadata.name != "Не удалось загрузить название":
            print("\n🎉 УСПЕХ! Данные извлечены корректно!")
        else:
            print("\n❌ Данные не извлечены")
    else:
        print("❌ Метаданные не получены")
        
except Exception as e:
    print(f"❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()