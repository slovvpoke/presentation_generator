#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности генератора презентаций
"""

import os
import sys
from sfapps_template_generator import create_presentation_from_template

def test_basic_generation():
    """Базовый тест генерации презентации"""
    print("🧪 Тестирование базовой генерации презентации...")
    
    # Проверка наличия шаблона
    template_path = 'Copy of SFApps.info Best Apps Presentation Template.pptx'
    if not os.path.exists(template_path):
        print("❌ Ошибка: Шаблон презентации не найден!")
        return False
    
    # Тестовые данные
    test_data = {
        'topic': 'Healthcare',
        'links': [
            'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ',
            'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD',
            'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3A00000EFpq5UAD',
            'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSftAEAT',
            'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4p8DEAR'
        ],
        'final_url': 'https://sfapps.info/healthcare',
        'output_pptx': 'test_output.pptx'
    }
    
    try:
        # Генерация презентации
        result = create_presentation_from_template(
            topic=test_data['topic'],
            links=test_data['links'],
            final_url=test_data['final_url'],
            template_path=template_path,
            output_pptx=test_data['output_pptx']
        )
        
        # Проверка результата
        if os.path.exists(test_data['output_pptx']):
            file_size = os.path.getsize(test_data['output_pptx'])
            print(f"✅ Презентация успешно создана: {test_data['output_pptx']}")
            print(f"📊 Размер файла: {file_size:,} байт")
            
            # Очистка тестового файла
            os.remove(test_data['output_pptx'])
            print("🧹 Тестовый файл удален")
            return True
        else:
            print("❌ Файл презентации не создан")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при генерации: {str(e)}")
        return False

def test_app_metadata_extraction():
    """Тест извлечения метаданных приложений"""
    print("\n🧪 Тестирование извлечения метаданных...")
    
    from sfapps_template_generator import fetch_app_metadata
    
    # Тестовая ссылка
    test_url = 'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ'
    
    try:
        metadata = fetch_app_metadata(test_url, timeout=10)
        
        if metadata:
            print(f"✅ Метаданные извлечены:")
            print(f"   📱 Название: {metadata.name}")
            print(f"   👥 Разработчик: {metadata.developer}")
            print(f"   🖼️  Логотип: {len(metadata.logo_bytes):,} байт")
            return True
        else:
            print("⚠️  Не удалось извлечь метаданные (возможно, проблемы с сетью)")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при извлечении метаданных: {str(e)}")
        return False

def main():
    """Главная функция тестирования"""
    print("=" * 60)
    print("🚀 SFApps Presentation Generator - Тестирование")
    print("=" * 60)
    
    # Проверка рабочей директории
    print(f"📁 Рабочая директория: {os.getcwd()}")
    
    # Список файлов
    required_files = [
        'Copy of SFApps.info Best Apps Presentation Template.pptx',
        'sfapps_template_generator.py',
        'app.py',
        'templates/index.html',
        'static/app.js'
    ]
    
    print("\n📋 Проверка наличия файлов:")
    all_files_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path}")
            all_files_exist = False
    
    if not all_files_exist:
        print("\n❌ Некоторые необходимые файлы отсутствуют!")
        return False
    
    # Выполнение тестов
    tests_passed = 0
    total_tests = 2
    
    if test_app_metadata_extraction():
        tests_passed += 1
    
    if test_basic_generation():
        tests_passed += 1
    
    # Результаты
    print("\n" + "=" * 60)
    print(f"📊 Результаты тестирования: {tests_passed}/{total_tests} тестов пройдено")
    
    if tests_passed == total_tests:
        print("🎉 Все тесты успешно пройдены!")
        print("🌐 Веб-интерфейс готов к использованию: http://127.0.0.1:5000")
        return True
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройки.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)