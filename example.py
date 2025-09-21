#!/usr/bin/env python3
"""
Пример использования генератора презентаций из командной строки
"""

from sfapps_template_generator import create_presentation_from_template

# Пример данных для Healthcare индустрии
example_data = {
    'topic': 'Healthcare',
    'links': [
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ',
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD',
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3A00000EFpq5UAD',
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSftAEAT',
        'https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4p8DEAR'
    ],
    'final_url': 'https://sfapps.info/healthcare',
    'template_path': 'Copy of SFApps.info Best Apps Presentation Template.pptx',
    'output_pptx': 'Healthcare_Apps_Presentation.pptx'
}

print("🏥 Генерация презентации для Healthcare индустрии...")
print(f"📊 Количество приложений: {len(example_data['links'])}")

try:
    result = create_presentation_from_template(
        topic=example_data['topic'],
        links=example_data['links'],
        final_url=example_data['final_url'],
        template_path=example_data['template_path'],
        output_pptx=example_data['output_pptx']
    )
    
    print(f"✅ Презентация создана: {result}")
    print("🎉 Готово! Можете открыть файл в PowerPoint.")
    
except Exception as e:
    print(f"❌ Ошибка: {str(e)}")