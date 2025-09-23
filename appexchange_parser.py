#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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

CACHE_DIR = "/tmp/appexchange_cache"
CACHE_EXPIRY_HOURS = 24

def _get_cache_path(url: str) -> str:
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    url_hash = hashlib.md5(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"cache_{url_hash}.json")

def _is_cache_valid(cache_path: str) -> bool:
    if not os.path.exists(cache_path):
        return False
    age_hours = (time.time() - os.path.getmtime(cache_path)) / 3600
    return age_hours < CACHE_EXPIRY_HOURS

def _load_from_cache(url: str):
    cache_path = _get_cache_path(url)
    if _is_cache_valid(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f" {e}")
    return None

def _save_to_cache(url: str, data: dict):
    try:
        cache_path = _get_cache_path(url)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{e}")


_JS_QUERY_SELECTOR_DEEP = r"""
const selector = arguments[0];

function qsd(sel, root) {
  root = root || document;

  if (root.querySelector) {
    const direct = root.querySelector(sel);
    if (direct) return direct;
  }

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

    return WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(_JS_QUERY_SELECTOR_DEEP, selector),
        message=f" {selector}"
    )


def parse_appexchange_simple(url: str):
    """Simple HTTP-based parser as fallback when Selenium fails"""
    print("🔄 Using simple HTTP parser as fallback...")
    
    try:
        # Headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html = response.text
        
        # Try to extract name from title tag
        name_match = re.search(r'<title[^>]*>([^|]+)', html, re.IGNORECASE)
        name = name_match.group(1).strip() if name_match else "Manual input required"
        
        # Also try to extract from JSON data if available
        json_match = re.search(r'"name"\s*:\s*"([^"]+)"', html)
        if json_match and json_match.group(1) != name:
            name = json_match.group(1).strip()
        
        # Try to extract from meta description or page content
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else "Manual input required"
        
        # Also try from JSON data
        json_desc = re.search(r'"description"\s*:\s*"([^"]+)"', html)
        if json_desc:
            description = json_desc.group(1).strip()
        
        # Try to find developer/company info
        # Look for publisher/company in JSON data first
        company_patterns = [
            r'"publisher"\s*:\s*"[^"]*"[^}]*"name"\s*:\s*"([^"]+)"',
            r'"company"\s*:\s*"([^"]+)"',
            r'"developer"\s*:\s*"([^"]+)"',
            r'"publisher"\s*:\s*"([^"]+)"',
            r'by\s+([^<>\n]+)',
            r'Company[:\s]+([^<>\n]+)',
            r'Developer[:\s]+([^<>\n]+)',
        ]
        
        company = "Manual input required"
        for pattern in company_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Clean up common suffixes
                if len(company) > 5:  # Only use if reasonable length
                    break
        
        # Try to find logo from JSON data
        logo_patterns = [
            r'"Logo"\s*:\s*"([^"]+)"',
            r'"logo_url"\s*:\s*"([^"]+)"',
            r'"Big Logo"\s*:\s*"([^"]+)"',
            r'<img[^>]*src=["\']([^"\']*logo[^"\']*)["\']',
            r'<img[^>]*src=["\']([^"\']*icon[^"\']*)["\']',
        ]
        
        logo_url = None
        for pattern in logo_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                logo_url = match.group(1)
                if logo_url and not logo_url.startswith('http'):
                    logo_url = f"https://appexchange.salesforce.com{logo_url}"
                break
        
        return {
            'name': name,
            'developer': company,
            'description': description,
            'logo_url': logo_url,
            'success': True,
            'parsed_with': 'simple_http'
        }
        
    except Exception as e:
        print(f"❌ Simple parser failed: {e}")
        return {
            'name': 'Manual input required',
            'developer': 'Manual input required', 
            'description': 'Manual input required',
            'logo_url': None,
            'success': False,
            'parsed_with': 'simple_http_failed'
        }


def parse_appexchange_improved(url: str, driver=None, reuse_driver=False):

    cached_result = _load_from_cache(url)
    if cached_result:
        return cached_result
    
    start_time = time.time()

    driver_was_provided = driver is not None
    
    if not driver_was_provided:
        driver_start = time.time()
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-images") 
        chrome_options.add_argument("--window-size=1280,720")  
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

    try:
        if not driver_was_provided:
            try:
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                driver_init_time = time.time() - driver_start
            except Exception as chrome_error:
                print(f"❌ ChromeDriver failed: {chrome_error}")
                print("🔄 Trying simple HTTP parser as fallback...")
                return parse_appexchange_simple(url)

        nav_start = time.time()
        driver.get(url)
        nav_time = time.time() - nav_start

        sleep_start = time.time()
        time.sleep(0.2) 
        sleep_time = time.time() - sleep_start

        # ===== NAME (.listing-title h1) =====
        name_start = time.time()
        app_name = None
        
        try:
            name_el = driver.find_element("css selector", ".listing-title h1")
            app_name = (name_el.text or "").strip()
        except:
            try:
                name_el = find_element_deep(driver, ".listing-title h1", timeout=3)
                app_name = (name_el.text or "").strip()
            except TimeoutException:
                # fallback from <title>
                title = (driver.title or "").strip()
                if title:
                    app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", title, flags=re.IGNORECASE).strip()

        if app_name:
            app_name = re.sub(r"\s*\|\s*(Salesforce\s+)?AppExchange.*$", "", app_name, flags=re.IGNORECASE).strip()
        
        name_time = time.time() - name_start

        # ===== DEVELOPER (.listing-title p) =====
        dev_start = time.time()
        developer = None
        
        try:
            dev_el = driver.find_element("css selector", ".listing-title p")
            developer = (dev_el.text or "").strip()
        except:
            try:
                dev_el = find_element_deep(driver, ".listing-title p", timeout=2)
                developer = (dev_el.text or "").strip()
            except TimeoutException:
                pass  # No developer found
        
        dev_time = time.time() - dev_start

        # ===== LOGO (.listing-logo img) =====
        logo_start = time.time()
        logo_url = None
        
        try:
            img_el = driver.find_element("css selector", ".listing-logo img")
            src = (img_el.get_attribute("src") or "").strip()
            if src:
                logo_url = ("https:" + src) if src.startswith("//") else src
        except:
            try:
                img_el = find_element_deep(driver, ".listing-logo img", timeout=2)
                src = (img_el.get_attribute("src") or "").strip()
                if src:
                    logo_url = ("https:" + src) if src.startswith("//") else src
            except TimeoutException:
                try:
                    og_img = driver.find_element("css selector", 'meta[property="og:image"]')
                    logo_url = og_img.get_attribute("content")
                    if logo_url:
                        logo_url = logo_url.strip()
                except Exception:
                    print("❌ Could not find og:image")
        
        logo_time = time.time() - logo_start

        result = {
            "name": app_name or "Unknown App",
            "developer": developer or "Unknown Developer",
            "logo_url": logo_url,
            "success": bool(app_name)
        }

        if result["success"]:
            _save_to_cache(url, result)

        total_time = time.time() - start_time

        return result

    except Exception as e:
        total_time = time.time() - start_time

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
    if not urls:
        return {}
        
    batch_start = time.time()
    
    driver_init_start = time.time()
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-images") 
    chrome_options.add_argument("--window-size=1280,720") 
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    
    results = {}
    driver = None
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver_init_time = time.time() - driver_init_start
        
        for i, url in enumerate(urls, 1):
            url_start = time.time()
            print(f"📍 [{i}/{len(urls)}] Парсинг: {url}")
            result = parse_appexchange_improved(url, driver=driver, reuse_driver=True)
            results[url] = result
            url_time = time.time() - url_start
            print(f"⏱️ URL #{i} время: {url_time:.2f}c")
            
    except Exception as e:
        print(f" {e}")
    finally:
        if driver:
            close_start = time.time()
            driver.quit()
            close_time = time.time() - close_start
            
    batch_total = time.time() - batch_start

    return results


def download_logo(logo_url: str, target_size=(100, 100)):

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
    result = parse_appexchange_improved(test_url)