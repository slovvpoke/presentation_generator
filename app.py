#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask Web Application for SFApps Presentation Generator
========================================================

Web interface for automatic generation of PowerPoint presentations 
"Best Apps for {Industry        except Exception as e:
        print(f"❌ Parsing error: {e}")

    # If all attempts fail
    print(f"❌ Failed to get metadata: {url}")
    return AppMetadata(
        url=url,
        name="Failed to load name",
        developer="Failed to load developer",le on AppExchange" based on ready template.

Features:
- Input presentation topic (industry)
- Input list of AppExchange application links (1-10 links)
- Automatic extraction of logos, names and developers
- Manual data override capability
- Slide preview
- Export to PPTX and PDF formats
"""

import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import uuid
import base64
import mimetypes
from typing import Optional, Dict, Any

import requests
from flask import Flask, render_template, request, flash, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename

# Import presentation generator functions
from sfapps_template_generator import (
    create_presentation_from_template, 
    AppMetadata
)

# Import main Selenium parser
try:
    from appexchange_parser import parse_appexchange_improved, parse_multiple_appexchange_urls
    PARSER_AVAILABLE = True
    print("✅ Selenium parser with Shadow DOM available")
except ImportError:
    PARSER_AVAILABLE = False
    print("❌ Error: Selenium parser not available!")

app = Flask(__name__)
app.secret_key = 'sfapps-presentation-generator-secret-key-2025'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'}  # extended
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure uploads folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------- MIME helpers ----------

def sniff_mime(logo_bytes: bytes, url_hint: str = "", header_mime: str = "") -> str:
    """
    Determine correct MIME for data:URI and/or for passing to generator.
    Priority: header_mime → by signature → by extension → image/png.
    """
    header_mime = (header_mime or "").lower().strip()
    if header_mime.startswith("image/"):
        return header_mime

    b = logo_bytes or b""
    h = b[:256]

    # SVG (by content)
    if b and (h.lstrip().startswith(b"<?xml") or b"<svg" in h.lower()):
        return "image/svg+xml"
    # PNG
    if h.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    # JPEG
    if h.startswith(b"\xff\xd8"):
        return "image/jpeg"
    # GIF
    if h.startswith(b"GIF87a") or h.startswith(b"GIF89a"):
        return "image/gif"
    # WebP
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "image/webp"

    # By URL extension
    if url_hint:
        guess = mimetypes.guess_type(url_hint)[0]
        if guess:
            return guess

    return "image/png"


# ---------- Helper functions ----------

def allowed_file(filename):
    """Check allowed file extensions"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file):
    """Save uploaded file and return path"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        return filepath
    return None


def fetch_multiple_app_metadata(urls: list) -> Dict[str, AppMetadata]:
    """Fast metadata retrieval for multiple URLs simultaneously"""
    if not PARSER_AVAILABLE:
        print("❌ Parser not available!")
        return {}
    
    if not urls:
        return {}
    
    print(f"🚀 Fast batch parsing {len(urls)} links...")
    
    # Common headers for image downloads
    img_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8", 
        "Referer": "https://appexchange.salesforce.com/",
    }

    def _download_logo(logo_url: str):
        print(f"🔄 Downloading logo: {logo_url}")
        try:
            r = requests.get(logo_url, timeout=5, headers=img_headers)  # Was 10, now 5 seconds
            if r.status_code == 200:
                logo_bytes = r.content
                logo_mime = sniff_mime(logo_bytes, url_hint=logo_url, header_mime=r.headers.get("content-type", ""))
                print(f"✅ Logo downloaded: {len(logo_bytes)} bytes")
                return logo_bytes, logo_mime
        except Exception as e:
            print(f"❌ Logo download error: {e}")
        return b"", "image/png"
    
    # Batch parsing of all URLs
    # Parse each URL individually with fallback
    parse_results = {}
    for url in urls:
        try:
            result = parse_appexchange_improved(url)
            parse_results[url] = result
        except Exception as e:
            print(f"❌ Failed to parse {url}: {e}")
            parse_results[url] = {
                'name': 'Manual input required',
                'developer': 'Manual input required', 
                'description': 'Manual input required',
                'logo_url': None,
                'success': False
            }
    
    # Parallel logo downloads
    logo_downloads = {}
    logo_urls_to_download = [(url, result.get('logo_url')) for url, result in parse_results.items() 
                            if result.get('logo_url') and result.get('success')]
    
    print(f"🚀 Parallel download of {len(logo_urls_to_download)} logos...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(_download_logo, logo_url): app_url 
            for app_url, logo_url in logo_urls_to_download
        }
        
        for future in concurrent.futures.as_completed(future_to_url):
            app_url = future_to_url[future]
            try:
                logo_bytes, logo_mime = future.result()
                logo_downloads[app_url] = (logo_bytes, logo_mime)
            except Exception as e:
                print(f"❌ Logo download error for {app_url}: {e}")
                logo_downloads[app_url] = (b"", "image/png")
    
    # Convert results to AppMetadata
    metadata_results = {}
    for url, result in parse_results.items():
        name = result.get('name', 'Unknown App')
        developer = result.get('developer', 'Unknown Developer')
        
        # Get logo from parallel download
        logo_bytes, logo_mime = logo_downloads.get(url, (b"", "image/png"))
            
        metadata = AppMetadata(
            url=url, 
            name=name, 
            developer=developer, 
            logo_bytes=logo_bytes, 
            logo_mime=logo_mime
        )
        metadata_results[url] = metadata
        
    print(f"✅ Batch parsing completed: {len(metadata_results)} metadata ready")
    return metadata_results


def fetch_app_metadata_with_fallback(url: str) -> Optional[AppMetadata]:
    """Get metadata via single Selenium parser with Shadow DOM support"""
    # Common headers for image downloads (WebP/SVG etc.)
    img_headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://appexchange.salesforce.com/",
    }

    def _download_logo(logo_url: str):
        try:
            r = requests.get(logo_url, timeout=10, headers=img_headers)
            if r.status_code == 200:
                logo_bytes = r.content
                logo_mime = sniff_mime(logo_bytes, url_hint=logo_url, header_mime=r.headers.get("content-type", ""))
                return logo_bytes, logo_mime
        except Exception as e:
            print(f"Logo download error: {e}")
        return b"", "image/png"

    # Единственный парсер: Selenium с Shadow DOM
    if not PARSER_AVAILABLE:
        print("❌ Parser not available!")
        return AppMetadata(
            url=url,
            name="Parser not available",
            developer="Install dependencies",
            logo_bytes=b'',
            logo_mime='image/png'
        )

    try:
        print(f"🔄 Parsing data from {url}")
        result = parse_appexchange_improved(url)
        
        if result and result.get('success'):
            name = result.get('name', 'Unknown App')
            developer = result.get('developer', 'Unknown Developer')
            logo_bytes, logo_mime = b"", "image/png"
            logo_url = result.get('logo_url')
            
            print(f"📊 Data from parser:")
            print(f"   Name: {name}")
            print(f"   Developer: {developer}")
            print(f"   Logo URL: {logo_url}")
            
            if logo_url:
                logo_bytes, logo_mime = _download_logo(logo_url)
                print(f"📊 After logo download:")
                print(f"   Logo_bytes size: {len(logo_bytes)} bytes")
                print(f"   MIME type: {logo_mime}")
                
            metadata = AppMetadata(url=url, name=name, developer=developer, logo_bytes=logo_bytes, logo_mime=logo_mime)
            print(f"📊 Created AppMetadata object:")
            print(f"   metadata.logo_bytes size: {len(metadata.logo_bytes) if metadata.logo_bytes else 0} bytes")
            print(f"   metadata.logo_mime: {getattr(metadata, 'logo_mime', 'not set')}")
            
            return metadata
        else:
            print(f"❌ Parser could not extract data from {url}")
            
    except Exception as e:
        print(f"❌ Ошибка при парсинге: {e}")

    # Если все попытки неудачны
    print(f"❌ Не удалось получить метаданные: {url}")
    return AppMetadata(
        url=url,
        name="Не удалось загрузить название",
        developer="Не удалось загрузить разработчика",
        logo_bytes=b'',
        logo_mime='image/png'
    )


def process_form_data(form_data, files):
    """Process form data and create structure for generator"""
    industry = form_data.get('industry', '').strip()
    final_url = form_data.get('final_url', '').strip()

    # Get links from textarea (one per line)
    app_links_text = form_data.get('app_links', '').strip()
    app_links = [link.strip() for link in app_links_text.split('\n') if link.strip()]
    
    # Override arrays are removed for now (will be empty)
    app_names = []
    app_developers = []  
    app_logos = []

    if len(app_links) < 1:
        raise ValueError("At least 1 application link required")
    if len(app_links) > 50:
        raise ValueError("Maximum number of links: 50 (for performance)")

    # Only manual user overrides (currently disabled)
    overrides: Dict[str, Dict[str, Any]] = {}
    for i, link in enumerate(app_links):
        od: Dict[str, Any] = {}
        if i < len(app_names) and app_names[i].strip():
            od['name'] = app_names[i].strip()
        if i < len(app_developers) and app_developers[i].strip():
            od['developer'] = app_developers[i].strip()
        if i < len(app_logos) and app_logos[i].filename:
            logo_path = save_uploaded_file(app_logos[i])
            if logo_path:
                od['logo_path'] = logo_path
                od['logo_mime'] = mimetypes.guess_type(logo_path)[0] or 'image/png'
        if od:
            overrides[link] = od

    return {
        'industry': industry,
        'app_links': app_links,
        'final_url': final_url,
        'overrides': overrides
    }


def resolve_multiple_app_data(links: list, overrides: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Fast resolution of data for multiple links simultaneously.
    Uses batch parsing to speed up 3-5 times.
    """
    results = {}
    
    # Determine which links need auto-parsing
    links_need_parsing = []
    for link in links:
        data = {}
        
        # 1) manual overrides
        if link in overrides:
            data.update(overrides[link])
        
        # 2) check if auto-parsing is needed
        need_logo = ('logo_path' not in data and 'logo_bytes' not in data)
        if 'name' not in data or 'developer' not in data or need_logo:
            links_need_parsing.append(link)
            
        results[link] = data
    
    # Batch parsing of all needed links at once
    if links_need_parsing:
        print(f"🚀 Batch auto-parsing for {len(links_need_parsing)} links...")
        parsed_metadata = fetch_multiple_app_metadata(links_need_parsing)
        
        # Supplement data with parsing results
        for link in links_need_parsing:
            data = results[link]
            meta = parsed_metadata.get(link)
            
            if meta:
                if 'name' not in data and meta.name:
                    data['name'] = meta.name
                if 'developer' not in data and meta.developer:
                    data['developer'] = meta.developer
                
                need_logo = ('logo_path' not in data and 'logo_bytes' not in data)
                if need_logo and getattr(meta, 'logo_bytes', b''):
                    data['logo_bytes'] = meta.logo_bytes
                    data['logo_mime'] = getattr(meta, 'logo_mime', None) or sniff_mime(meta.logo_bytes, url_hint=link)
    
    # Finalize all data
    for link, data in results.items():
        # If user uploaded file but didn't specify mime - determine by extension
        if 'logo_path' in data and 'logo_mime' not in data:
            data['logo_mime'] = mimetypes.guess_type(data['logo_path'])[0] or 'image/png'

        # Guarantee presence of basic fields
        data.setdefault('name', '⚠️ Manual input required')
        data.setdefault('developer', '⚠️ Manual input required')
    
    return results


def resolve_app_data(link: str, overrides: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Single source of truth: collects data for one application.
    1) Takes manual overrides (name/developer/logo_path);
    2) If something is missing - fills in via Selenium parser (fetch_app_metadata_with_fallback);
    3) Returns dictionary suitable for both preview and generator.
    """
    data: Dict[str, Any] = {}

    # 1) manual overrides
    if link in overrides:
        data.update(overrides[link])

    # 2) auto-parsing if something is missing
    need_logo = ('logo_path' not in data and 'logo_bytes' not in data)
    if 'name' not in data or 'developer' not in data or need_logo:
        meta = fetch_app_metadata_with_fallback(link)
        if meta:
            if 'name' not in data and meta.name:
                data['name'] = meta.name
            if 'developer' not in data and meta.developer:
                data['developer'] = meta.developer
            if need_logo and getattr(meta, 'logo_bytes', b''):
                data['logo_bytes'] = meta.logo_bytes
                data['logo_mime'] = getattr(meta, 'logo_mime', None) or sniff_mime(meta.logo_bytes, url_hint=link)

    # If user uploaded file but didn't specify mime - determine by extension
    if 'logo_path' in data and 'logo_mime' not in data:
        data['logo_mime'] = mimetypes.guess_type(data['logo_path'])[0] or 'image/png'

    # Guarantee presence of basic fields
    data.setdefault('name', '⚠️ Manual input required')
    data.setdefault('developer', '⚠️ Manual input required')

    return data


def create_preview_data(industry, app_links, final_url, overrides):
    """Create data for preview (FAST version with batch parsing)"""
    preview_slides = []

    # Title slide - clean header
    preview_slides.append({
        'title': 'Title slide',
        'content': f'<h4>Best Apps for {industry} Available on AppExchange</h4>',
        'image': None
    })

    # FAST batch parsing of all links at once
    print(f"🚀 Fast preview for {len(app_links)} links...")
    all_resolved_data = resolve_multiple_app_data(app_links, overrides)

    # Application slides
    for i, link in enumerate(app_links):
        slide_num = i + 1
        resolved = all_resolved_data[link]

        # Prepare logo for preview (base64) with correct MIME
        logo_data = None
        if 'logo_path' in resolved and os.path.exists(resolved['logo_path']):
            try:
                with open(resolved['logo_path'], 'rb') as f:
                    logo_bytes = f.read()
                mime = resolved.get('logo_mime') or mimetypes.guess_type(resolved['logo_path'])[0] or 'image/png'
                logo_data = f"data:{mime};base64,{base64.b64encode(logo_bytes).decode()}"
            except Exception as e:
                print(f"{e}")
        elif 'logo_bytes' in resolved and resolved['logo_bytes']:
            try:
                mime = resolved.get('logo_mime') or sniff_mime(resolved['logo_bytes'], url_hint=link)
                logo_data = f"data:{mime};base64,{base64.b64encode(resolved['logo_bytes']).decode()}"
            except Exception as e:
                print(f"⚠️ Error processing logo_bytes for {resolved['name']}: {e}")
        else:
            print(f"❌ Logo not found for {resolved['name']}: logo_path={resolved.get('logo_path')}, logo_bytes={len(resolved.get('logo_bytes', b''))} bytes")

        preview_slides.append({
            'title': f'App #{slide_num}',
            'content': (
                f'<h5>{resolved["name"]}</h5>'
                f'<p>{resolved["developer"]}</p>'
                f'<small class="text-muted">{link}</small>'
            ),
            'image': logo_data
        })

    preview_slides.append({
        'title': 'Final Slide',
        'content': (
            f'<h4>Best Apps for {industry} Available on AppExchange</h4>'
            f'<p>Link: <a href="{final_url}" target="_blank">{final_url}</a></p>'
        ),
        'image': None
    })

    print(f"✅ Fast preview ready in seconds!")
    return {'slides': preview_slides}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate_presentation():
    """Generate presentation or preview"""
    try:
        data = process_form_data(request.form, request.files)
        industry = data['industry']
        app_links = data['app_links']
        final_url = data['final_url']
        overrides = data['overrides']

        if request.form.get('preview') == 'true':
            preview_data = create_preview_data(industry, app_links, final_url, overrides)
            return jsonify({'success': True, 'preview': preview_data})

        # Prepare final overrides for generator (FAST version)
        print(f"\n🚀 Fast preparation of data for presentation generator:")
        print(f"   Number of links: {len(app_links)}")

        # FAST batch parsing of all links at once
        all_resolved_data = resolve_multiple_app_data(app_links, overrides)
        
        resolved_overrides: Dict[str, Dict[str, Any]] = {}
        for i, link in enumerate(app_links, 1):
            resolved = all_resolved_data[link]
            print(f"\n   App #{i}: {link}")
            print(f"     Name: {resolved['name']}")
            print(f"     Developer: {resolved['developer']}")

            ro: Dict[str, Any] = {
                'name': resolved['name'],
                'developer': resolved['developer']
            }

            # Logo
            has_logo = False
            if 'logo_path' in resolved:
                ro['logo_path'] = resolved['logo_path']
                print(f"     Logo: file {resolved['logo_path']}")
                has_logo = True
            if 'logo_bytes' in resolved:
                ro['logo_bytes'] = resolved['logo_bytes']
                logo_size = len(resolved['logo_bytes']) if resolved['logo_bytes'] else 0
                print(f"     Logo bytes: {logo_size} bytes")
                has_logo = True
            if 'logo_mime' in resolved:
                ro['logo_mime'] = resolved['logo_mime']
                print(f"     MIME type: {resolved['logo_mime']}")

            if not has_logo:
                print(f"     ⚠️ WARNING: Logo not found!")

            resolved_overrides[link] = ro

        print(f"\n✅ Fast preparation of data completed!")

        # Output format
        output_format = request.form.get('format', 'pptx')

        # Template
        template_path = 'Copy of SFApps.info Best Apps Presentation Template.pptx'
        if not os.path.exists(template_path):
            flash('Presentation template not found', 'error')
            return redirect(url_for('index'))

        # Temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as tmp_pptx:
            output_pptx = tmp_pptx.name
        output_pdf = None
        if output_format == 'pdf':
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                output_pdf = tmp_pdf.name

        try:
            # Generation: passing already RESOLVED data
            create_presentation_from_template(
                topic=industry,
                links=app_links,
                final_url=final_url,
                template_path=template_path,
                output_pptx=output_pptx,
                output_pdf=output_pdf,
                app_overrides=resolved_overrides
            )

            # What we return to the user
            if output_format == 'pdf' and output_pdf and os.path.exists(output_pdf):
                send_file_path = output_pdf
                mimetype = 'application/pdf'
                filename = f'Best_Apps_for_{industry}.pdf'
            else:
                send_file_path = output_pptx
                mimetype = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                filename = f'Best_Apps_for_{industry}.pptx'

            return send_file(
                send_file_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )

        finally:
            # Remove temporary files
            try:
                if os.path.exists(output_pptx):
                    os.unlink(output_pptx)
                if output_pdf and os.path.exists(output_pdf):
                    os.unlink(output_pdf)
            except Exception:
                pass
            # Remove uploaded user logos (if not needed further)
            for od in overrides.values():
                lp = od.get('logo_path')
                # If you want to keep them — remove the deletion below
                if lp and os.path.exists(lp):
                    try:
                        os.unlink(lp)
                    except Exception:
                        pass

    except ValueError as e:
        if request.form.get('preview') == 'true':
            return jsonify({'success': False, 'error': str(e)})
        flash(str(e), 'error')
        return redirect(url_for('index'))

    except Exception as e:
        if request.form.get('preview') == 'true':
            return jsonify({'success': False, 'error': f'Generation error: {str(e)}'})
        flash(f'Error generating presentation: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.errorhandler(413)
def too_large(e):
    """File size error handler"""
    flash('File too large. Maximum size: 16MB', 'error')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(e):
    """Обработка 404 ошибки"""
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(e):
    """Internal server error handler"""
    flash('Internal server error. Please try again.', 'error')
    return render_template('index.html'), 500


if __name__ == '__main__':
    print("Starting SFApps Presentation Generator...")
    print("📁 Working directory:", os.getcwd())
    print("📄 Template:", "Copy of SFApps.info Best Apps Presentation Template.pptx")
    print("🌐 Open in browser: http://localhost:5001")
    print("-" * 50)
    app.run(debug=True, host='0.0.0.0', port=5001)
