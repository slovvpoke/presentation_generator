# 🎯 Краткое руководство по использованию

## Быстрый старт

### 1. Запуск приложения
```bash
./start.sh
# или
python app.py
```

### 2. Открытие в браузере
Перейдите по адресу: **http://127.0.0.1:5000**

### 3. Заполнение формы

#### Тема презентации
Введите индустрию, например:
- `Healthcare`
- `Finance` 
- `Retail`
- `Manufacturing`

#### Ссылки на приложения
Добавьте 5-20 ссылок на AppExchange приложения:
```
https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ
https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD
```

#### Финальная ссылка
URL для кликабельной кнопки на последнем слайде:
```
https://sfapps.info/healthcare
```

### 4. Предварительный просмотр
Нажмите "**Предварительный просмотр**" для проверки данных.

⚠️ **Если видите "Требуется ручной ввод":**
1. Нажмите "**Переопределить**" рядом с проблемной ссылкой
2. Введите данные вручную:
   - Название приложения
   - Разработчик  
   - Загрузите логотип

### 5. Скачивание
- **PPTX** - для редактирования в PowerPoint
- **PDF** - готовая презентация

## 🔧 Возможные проблемы

### Автоматическое извлечение не работает
Приложение использует несколько методов:
1. JSON данные (для динамических страниц)
2. CSS селекторы 
3. Мета-теги

**Решение:** Используйте ручной ввод данных

### PDF не генерируется
**Требуется LibreOffice:**
```bash
# macOS
brew install libreoffice

# Ubuntu/Debian  
sudo apt-get install libreoffice
```

### Шаблон не найден
Убедитесь что файл `Copy of SFApps.info Best Apps Presentation Template.pptx` находится в папке проекта.

## 📋 Пример заполнения

```
Тема: Healthcare

Ссылки:
1. https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4cKBEAZ
2. https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSfukEAD
3. https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3A00000EFpq5UAD
4. https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3u00000MSftAEAT
5. https://appexchange.salesforce.com/appxListingDetail?listingId=a0N3000000B4p8DEAR

Финальная ссылка: https://sfapps.info/healthcare
```

## 🎉 Результат

Получите готовую презентацию:
- **Титульный слайд** с темой
- **Слайды приложений** с логотипами и описаниями
- **Финальный слайд** с кликабельной ссылкой

---

**Поддержка:** При возникновении проблем проверьте логи в консоли приложения.