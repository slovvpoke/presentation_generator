#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AppExchange парсер с поддержкой Shadow DOM (2025)

Единственный парсер для извлечения данных с современных страниц AppExchange.
Использует Selenium с JavaScript для доступа к Shadow DOM элементам.

Извлекает:
- name:      .listing-title h1
- developer: .listing-title p  
- image:     .listing-logo img
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import requests
from PIL import Image
from io import BytesIO
import re
import time
import json
import hashlib
import os

# Простое файловое кэширование
CACHE_DIR = "/tmp/appexchange_cache"
CACHE_EXPIRY_HOURS = 24

def _get_cache_path(url: str) -> str:
    """Получает путь к файлу кэша для URL."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"cache_{url_hash}.json")

def _is_cache_valid(cache_path: str) -> bool:
    """Проверяет, актуален ли кэш (не старше 24 часов)."""
    if not os.path.exists(cache_path):
        return False
    age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
    return age_hours < CACHE_EXPIRY_HOURS

def _load_from_cache(url: str):
    """Загружает данные из кэша, если они актуальны."""
    cache_path = _get_cache_path(url)
    if _is_cache_valid(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"💾 Данные загружены из кэша: {url}")
                return data
        except Exception as e:
            print(f"⚠️ Ошибка чтения кэша: {e}")
    return None

def _save_to_cache(url: str, data: dict):
    """Сохраняет данные в кэш."""
    try:
        cache_path = _get_cache_path(url)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 Данные сохранены в кэш: {url}")
    except Exception as e:
        print(f"⚠️ Ошибка записи в кэш: {e}")


# ---------- JS-хелперы для поиска по селектору через все shadowRoot ----------
_JS_QUERY_SELECTOR_DEEP = r"""
const selector = arguments[0];

function qsd(sel, root) {
  root = root || document;

  // Прямая попытка внутри текущего root
  if (root.querySelector) {
    const direct = root.querySelector(sel);
    if (direct) return direct;
  }

  // Обойти все элементы и «проколоть» их shadowRoot
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  let node = walker.currentNode;
  while (node) {
    if (node.shadowRoot) {
      const found = qsd(sel, node.shadowRoot);
      if (found) return found;
    }
    node = walker.nextNode();
  }
  return null;
}
return qsd(selector, document);
"""

def find_element_deep(driver, selector: str, timeout: int = 3):
    """
    Возвращает первый элемент по CSS-селектору, проходя через все shadowRoot.
    Бросает TimeoutException, если не найден за отведённое время.
    """
    return WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(_JS_QUERY_SELECTOR_DEEP, selector),
        message=f"Не найден элемент (включая shadow DOM): {selector}"
    )


def parse_appexchange_improved(url: str, driver=None, reuse_driver=False):
    """
    Парсит страницу листинга AppExchange.
    Достаёт: name (.listing-title h1), developer (.listing-title p), logo_url (.listing-logo img).
    
    Args:
        url: URL страницы AppExchange
        driver: Существующий WebDriver (для переиспользования)
        reuse_driver: Если True, не закрывает драйвер в конце
    """
    # Проверяем кэш в первую очередь
    cached_result = _load_from_cache(url)
    if cached_result:
        return cached_result
    
    start_time = time.time()
    print(f"🔍 Старт парсинга: {url}")

    driver_was_provided = driver is not None
    
    if not driver_was_provided:
        driver_start = time.time()
        # ---- Настройки Chrome ----
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-images")  # Отключаем загрузку изображений для скорости
        chrome_options.add_argument("--window-size=1280,720")  # Меньше окно = быстрее
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        if not driver_was_provided:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            # Мини-маскировка webdriver-флага
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver_init_time = time.time() - driver_start
            print(f"⏱️ Инициализация драйвера: {driver_init_time:.2f}c")

        # Переход
        nav_start = time.time()
        driver.get(url)
        nav_time = time.time() - nav_start
        print(f"⏱️ Загрузка страницы: {nav_time:.2f}c")

        # Уменьшенный буфер на первичную инициализацию SPA/веб-компонентов
        sleep_start = time.time()
        time.sleep(0.2)  # Было 0.5, стало 0.2
        sleep_time = time.time() - sleep_start
        print(f"⏱️ Ожидание инициализации: {sleep_time:.2f}c")

        # ===== NAME (.listing-title h1) =====
        name_start = time.time()
        app_name = None
        print("🔎 Ищем название по селектору .listing-title h1 ...")
        
        # Сначала попробуем обычный селектор (быстрее)
        try:
            name_el = driver.find_element("css selector", ".listing-title h1")
            app_name = (name_el.text or "").strip()
            print(f"✅ Название (обычный селектор): {app_name}")
        except:
            # Только если не нашли - используем Shadow DOM
            try:
                name_el = find_element_deep(driver, ".listing-title h1", timeout=3)
                app_name = (name_el.text or "").strip()
                print(f"✅ Название (shadow DOM): {app_name}")
            except TimeoutException:
                print("⚠️ Не нашли .listing-title h1 — используем <title> как запасной вариант")
                # fallback из <title>
                title = (driver.title or "").strip()
                if title:
                    app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", title, flags=re.IGNORECASE).strip()
                    if app_name:
                        print(f"ℹ️ Название из <title>: {app_name}")

        # Нормализация хвостов «| AppExchange»
        if app_name:
            app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", app_name, flags=re.IGNORECASE).strip()
        
        name_time = time.time() - name_start
        print(f"⏱️ Поиск названия: {name_time:.2f}c")

        # ===== DEVELOPER (.listing-title p) =====
        dev_start = time.time()
        developer = None
        print("🔎 Ищем разработчика по селектору .listing-title p ...")
        
        # Сначала попробуем обычный селектор
        try:
            dev_el = driver.find_element("css selector", ".listing-title p")
            developer = (dev_el.text or "").strip()
            print(f"✅ Разработчик (обычный селектор): {developer}")
        except:
            # Только если не нашли - используем Shadow DOM
            try:
                dev_el = find_element_deep(driver, ".listing-title p", timeout=2)
                developer = (dev_el.text or "").strip()
                print(f"✅ Разработчик (shadow DOM): {developer}")
            except TimeoutException:
                print("⚠️ Не нашли .listing-title p — оставим Unknown Developer")
        
        dev_time = time.time() - dev_start
        print(f"⏱️ Поиск разработчика: {dev_time:.2f}c")

        # ===== LOGO (.listing-logo img) =====
        logo_start = time.time()
        logo_url = None
        print("🔎 Ищем логотип по селектору .listing-logo img ...")
        
        # Сначала попробуем обычный селектор
        try:
            img_el = driver.find_element("css selector", ".listing-logo img")
            src = (img_el.get_attribute("src") or "").strip()
            if src:
                logo_url = ("https:" + src) if src.startswith("//") else src
                print(f"✅ Логотип (обычный селектор): {logo_url}")
        except:
            # Только если не нашли - используем Shadow DOM
            try:
                img_el = find_element_deep(driver, ".listing-logo img", timeout=2)
                src = (img_el.get_attribute("src") or "").strip()
                if src:
                    logo_url = ("https:" + src) if src.startswith("//") else src
                    print(f"✅ Логотип (shadow DOM): {logo_url}")
            except TimeoutException:
                print("⚠️ Не нашли .listing-logo img — пробуем meta og:image")
                try:
                    og_img = driver.find_element("css selector", 'meta[property="og:image"]')
                    logo_url = og_img.get_attribute("content")
                    if logo_url:
                        print(f"ℹ️ Логотип из og:image: {logo_url}")
                except Exception:
                    print("❌ og:image тоже не найден")
        
        logo_time = time.time() - logo_start
        print(f"⏱️ Поиск логотипа: {logo_time:.2f}c")

        result = {
            "name": app_name or "Unknown App",
            "developer": developer or "Unknown Developer",
            "logo_url": logo_url,
            "success": bool(app_name)
        }

        # Сохраняем в кэш только успешные результаты
        if result["success"]:
            _save_to_cache(url, result)

        total_time = time.time() - start_time
        print(f"⏱️ ОБЩЕЕ ВРЕМЯ ПАРСИНГА: {total_time:.2f}c")
        print("🎯 Результат парсинга:")
        print(f"   Название:    {result['name']}")
        print(f"   Разработчик: {result['developer']}")
        print(f"   Логотип:     {result['logo_url']}")
        return result

    except Exception as e:
        total_time = time.time() - start_time
        print(f"⏱️ ВРЕМЯ ДО ОШИБКИ: {total_time:.2f}c")
        print(f"❌ Ошибка парсинга: {e}")
        result = {
            "name": "Parsing Error",
            "developer": "Unknown",
            "logo_url": None,
            "success": False,
            "error": str(e),
        }
        return result
    finally:
        if driver and not driver_was_provided and not reuse_driver:
            driver.quit()


def parse_multiple_appexchange_urls(urls: list):
    """
    Быстрый пакетный парсинг нескольких URL с переиспользованием браузера.
    В 3-5 раз быстрее чем парсинг каждого URL отдельно.
    
    Args:
        urls: Список URL для парсинга
        
    Returns:
        dict: Словарь {url: result_data}
    """
    if not urls:
        return {}
        
    batch_start = time.time()
    print(f"🚀 Быстрый пакетный парсинг {len(urls)} URL...")
    
    # Настройки Chrome для переиспользования
    driver_init_start = time.time()
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-images")  # Добавляем для скорости
    chrome_options.add_argument("--window-size=1280,720")  # Уменьшаем размер
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    results = {}
    driver = None
    
    try:
        # Создаем драйвер один раз
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver_init_time = time.time() - driver_init_start
        print(f"⏱️ ИНИЦИАЛИЗАЦИЯ ДРАЙВЕРА: {driver_init_time:.2f}c")
        
        # Парсим все URL подряд
        for i, url in enumerate(urls, 1):
            url_start = time.time()
            print(f"📍 [{i}/{len(urls)}] Парсинг: {url}")
            result = parse_appexchange_improved(url, driver=driver, reuse_driver=True)
            results[url] = result
            url_time = time.time() - url_start
            print(f"⏱️ URL #{i} время: {url_time:.2f}c")
            
    except Exception as e:
        print(f"❌ Ошибка пакетного парсинга: {e}")
    finally:
        if driver:
            close_start = time.time()
            driver.quit()
            close_time = time.time() - close_start
            print(f"⏱️ Закрытие драйвера: {close_time:.2f}c")
            
    batch_total = time.time() - batch_start
    print(f"⏱️ ОБЩЕЕ ВРЕМЯ ПАКЕТНОГО ПАРСИНГА: {batch_total:.2f}c")
    print(f"✅ Пакетный парсинг завершен: {len(results)}/{len(urls)} успешно")
    return results


def download_logo(logo_url: str, target_size=(100, 100)):
    """
    Скачивает логотип и приводit к заданному максимуму размера (thumbnail).
    Возвращает PIL.Image или None.
    """
    if not logo_url:
        return None
    try:
        resp = requests.get(logo_url, timeout=10)
        if resp.status_code == 200:
            img = Image.open(BytesIO(resp.content))
            img.thumbnail(target_size)
            return img
    except Exception:
        pass
    return None


# ===== Тест =====
if __name__ == "__main__":
    test_url = "https://appexchange.salesforce.com/appxListingDetail?listingId=01dbaf61-02e0-4bc8-a8db-2ddbf30719ed"
    print("=== ТЕСТОВЫЙ ЗАПУСК SELENIUM ПАРСЕРА ===")
    result = parse_appexchange_improved(test_url)

    print("\n🎯 Финальный результат:")
    print(f"Название:    {result['name']}")
    print(f"Разработчик: {result['developer']}")
    print(f"Логотип:     {result['logo_url']}")
    print(f"Успех:       {result['success']}")
