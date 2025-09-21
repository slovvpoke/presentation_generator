"""
sfapps_template_generator.py
=================================

This module provides a high–level helper for constructing
PowerPoint presentations from a pre‐built template.  Unlike
``sfapps_presentation_generator.py`` – which rebuilds each slide from
scratch – this module edits an existing PPTX file in place.  It
maintains all decorative artwork, backgrounds and layout elements
defined in the original template and only replaces the fields the
caller cares about: the cover page title, the per–application name,
publisher and logo, and the closing call–to–action.

The workflow is as follows:

* The caller specifies a topic (industry/category), a list of
  AppExchange URLs and a URL for the final slide.  Optionally a
  dictionary of overrides can provide custom names, publishers and
  logo images when automatic extraction fails or should be
  customised.
* The template file is opened using ``python-pptx``.  The template
  shipped with this assignment contains a cover slide, ten
  programme slides (#1 through #10) and a closing slide.  If more
  than ten applications are supplied the second programme slide is
  duplicated until enough placeholders exist.
* Each programme slide is updated: the number is set to ``#1``,
  ``#2`` etc., the app name and publisher text is replaced, and the
  logo image is swapped.  Decorative artwork is left untouched.
* Any unused programme slides are removed so the final deck only
  contains the cover, the required programme slides and the
  closing slide.
* The cover slide is updated by replacing the ``$industry`` token
  with the supplied topic.  The closing slide is similarly updated
  and the logo on that slide is given a hyperlink to the final URL.
* The result is written to ``output_pptx``.  If LibreOffice is
  available a PDF is also produced at ``output_pdf``.

The module exposes a single public entry point:

    create_presentation_from_template(topic, links, final_url,
                                      template_path, output_pptx,
                                      output_pdf=None,
                                      app_overrides=None)

Requirements
------------

* python-pptx
* requests
* beautifulsoup4
* Pillow (for image scaling)
* LibreOffice in headless mode (optional, for PDF conversion)
"""

import os
import re
import subprocess
from copy import deepcopy
from dataclasses import dataclass, field
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn


@dataclass
class AppMetadata:
    """Container for app details extracted from an AppExchange listing."""

    url: str
    name: str
    developer: str
    logo_bytes: bytes
    logo_mime: str


def _extract_from_html(html: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Given the HTML body of an AppExchange listing this helper will try
    to extract the application name, the developer/publisher and a
    logo URL.  CSS selectors are prioritized, falling back to JSON and 
    OpenGraph metadata.

    Parameters
    ----------
    html: str
        Raw HTML string from the AppExchange listing page.

    Returns
    -------
    (name, developer, logo_url): Tuple of three strings or ``None`` if
    a field cannot be determined.
    """
    soup = BeautifulSoup(html, 'html.parser')
    name = None
    dev = None
    logo = None
    
    # Try CSS selectors first (most reliable for AppExchange)
    # Try various selectors for app name
    name_selectors = [
        '.listing-title h1',
        'h1[data-test-id="listing-title"]',
        'h1.listing-header__title',
        '[data-testid="listing-title"]',
        '.app-title',
        '.listing-name'
    ]
    for selector in name_selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text().strip()
            if text:  # Make sure text is not empty
                name = text
                print(f"Найдено название через селектор '{selector}': {name}")
                break

    # Try various selectors for developer
    dev_selectors = [
        '.listing-title p',
        '[data-test-id="listing-publisher"]',
        '.listing-header__publisher',
        '[data-testid="listing-publisher"]',
        '.app-publisher',
        '.listing-publisher'
    ]
    for selector in dev_selectors:
        element = soup.select_one(selector)
        if element:
            dev_text = element.get_text().strip()
            if dev_text:  # Make sure text is not empty
                # Remove "By " prefix if present
                if dev_text.lower().startswith('by '):
                    dev = dev_text[3:].strip()
                else:
                    dev = dev_text
                print(f"Найден разработчик через селектор '{selector}': {dev}")
                break

    # Try various selectors for logo
    logo_selectors = [
        '.summary .listing-logo .ads-image',
        '[data-test-id="listing-logo"] img',
        '.listing-header__logo img',
        '[data-testid="listing-logo"] img',
        '.app-logo img',
        '.listing-logo img'
    ]
    for selector in logo_selectors:
        element = soup.select_one(selector)
        if element:
            # Try different attributes for image URL
            logo = element.get('src') or element.get('data-src') or element.get('data-original') or element.get('data-lazy')
            if logo:
                print(f"Найден логотип через селектор '{selector}': {logo}")
                break
    
    # Try to extract from JSON script tags only if CSS failed
    if not all([name, dev, logo]):
        script_tags = soup.find_all('script', type='application/json')
        for script in script_tags:
            try:
                import json
                data = json.loads(script.get_text())
                # Try to find app data in JSON structure
                if isinstance(data, dict):
                    # Look for common patterns in JSON data
                    for key, value in data.items():
                        if isinstance(value, dict):
                            if 'name' in value and 'developer' in value:
                                name = name or value.get('name')
                                dev = dev or value.get('developer')
                            elif 'title' in value and 'publisher' in value:
                                name = name or value.get('title')
                                dev = dev or value.get('publisher')
            except:
                continue
    
    # Final fallback to OpenGraph metadata
    if not name:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title_content = og_title['content']
            # Remove common suffixes like "| Salesforce AppExchange"
            if '|' in title_content:
                name = title_content.split('|')[0].strip()
            else:
                name = title_content.strip()
    
    if not logo:
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            logo = og_image['content']
    
    if not dev:
        # Look for Twitter metadata
        twitter_data1 = soup.find('meta', attrs={'name': 'twitter:data1'})
        if twitter_data1 and twitter_data1.get('content'):
            dev = twitter_data1['content'].strip()
        else:
            # Look for any span/text containing "By"
            by_elements = soup.find_all(string=re.compile(r'By\s+', re.IGNORECASE))
            for by_text in by_elements:
                if by_text.strip():
                    dev = by_text.replace('By', '').strip()
                    break
    
    return name, dev, logo


def fetch_app_metadata(url: str, timeout: int = 20) -> Optional[AppMetadata]:
    """
    Retrieve metadata for an AppExchange listing.  If extraction or
    download fails, ``None`` is returned.

    Parameters
    ----------
    url: str
        URL of the AppExchange listing.
    timeout: int, optional
        Maximum number of seconds to wait for HTTP requests.

    Returns
    -------
    AppMetadata or None
        ``AppMetadata`` containing the name, developer and logo bytes
        if successful, otherwise ``None``.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return None
    name, dev, logo_url = _extract_from_html(resp.text)
    if not name or not dev or not logo_url:
        return None
    # Fetch logo
    try:
        img_resp = requests.get(logo_url, headers=headers, timeout=timeout)
        img_resp.raise_for_status()
        logo_bytes = img_resp.content
        logo_mime = img_resp.headers.get('Content-Type', 'image/png')
    except Exception:
        return None
    return AppMetadata(url=url, name=name, developer=dev, logo_bytes=logo_bytes, logo_mime=logo_mime)


def _clone_slide(prs: Presentation, index: int) -> None:
    """
    Clone the slide at position ``index`` and append the clone to the
    end of the slide collection.  All shapes on the source slide are
    deep–copied; group shapes are not present in the provided
    template so no special casing is necessary.  The new slide uses
    the same layout as the source slide.

    Parameters
    ----------
    prs: Presentation
        The presentation object to operate on.
    index: int
        Zero based index of the slide to clone.
    """
    source = prs.slides[index]
    layout = prs.slide_layouts[0]  # Only one layout defined in template
    new_slide = prs.slides.add_slide(layout)
    for shape in source.shapes:
        new_slide.shapes._spTree.append(deepcopy(shape.element))


def _remove_slide(prs: Presentation, index: int) -> None:
    """
    Remove the slide at the specified index from the presentation.

    This helper updates the slide id list and drops the corresponding
    relationship from the presentation part.  Without both steps the
    PPTX would become corrupt.

    Parameters
    ----------
    prs: Presentation
        The presentation from which to remove a slide.
    index: int
        Zero based slide index to remove.
    """
    from pptx.oxml.ns import qn
    slide = prs.slides[index]
    slide_id = slide.slide_id
    sldIdLst = prs.slides._sldIdLst
    relId = None
    for sldId in list(sldIdLst):
        if int(sldId.get('id')) == slide_id:
            relId = sldId.get(qn('r:id'))
            sldIdLst.remove(sldId)
            break
    if relId:
        prs.part.drop_rel(relId)


def _find_logo_shape(slide) -> Optional[int]:
    """
    Given a slide, attempt to identify the picture shape that contains
    the application logo.  The heuristic is to pick the picture
    shape whose width and height are both between 1 and 4 inches and
    which has the largest area among such candidates.  Decorative
    icons on the template are much smaller or much larger, so this
    rule works reliably on the provided design.

    Parameters
    ----------
    slide: pptx.slide.Slide
        A slide object to inspect.

    Returns
    -------
    int or None
        The index of the candidate shape or ``None`` if none match.
    """
    candidates: List[Tuple[float, int]] = []
    for idx, shape in enumerate(slide.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            w = shape.width / 914400.0
            h = shape.height / 914400.0
            area = w * h
            if 1.0 < w < 4.0 and 1.0 < h < 4.0:
                candidates.append((area, idx))
    if not candidates:
        return None
    candidates.sort(reverse=True)  # Largest area first
    return candidates[0][1]


def _update_slide_fields(slide, app: AppMetadata, number: int) -> None:
    """
    Replace the number, name, developer and logo on a single
    programme slide.  The function searches for the first text
    shape containing a hash ('#') and replaces its text with ``#n``.
    It then searches for the first text shape beginning with "By"
    (case–insensitive) and replaces it with the developer string.  Any
    remaining text shape containing the original app name from the
    template is replaced with ``app.name``.  Finally the logo
    placeholder picture is updated by replacing its underlying image
    part.

    Parameters
    ----------
    slide: pptx.slide.Slide
        The slide to operate on.
    app: AppMetadata
        Data for the application to fill in.
    number: int
        One–based sequence number to display on the slide.
    """
    # Update text shapes
    replaced_name = False
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        text = shape.text
        if '#' in text:
            # Normalize to a single number with leading space as in the template
            shape.text = f" #{number}"
            continue
        lowered = text.strip().lower()
        if lowered.startswith('by '):
            shape.text = f"By {app.developer}"
            continue
        # Replace the template app name – only the first occurrence
        if not replaced_name and text.strip():
            # If the text originally came from the template it will
            # match one of the placeholder names; simply replace it.
            shape.text = app.name
            replaced_name = True
            continue
    # Update logo image
    idx = _find_logo_shape(slide)
    if idx is not None:
        pic_shape = slide.shapes[idx]
        # Acquire the relationship id pointing to the image
        rId = pic_shape._element.blip_rId
        image_part = slide.part.related_part(rId)
        # Load image into PIL to scale it down if necessary
        try:
            with Image.open(BytesIO(app.logo_bytes)) as img:
                # Determine max bounding box in pixels based on slide
                max_w = pic_shape.width
                max_h = pic_shape.height
                # Convert to pixels at 96 DPI (~ px per inch) for PIL
                max_w_px = int(max_w * 96 / 914400)
                max_h_px = int(max_h * 96 / 914400)
                # Resize while preserving aspect ratio
                w, h = img.size
                ratio = min(max_w_px / w, max_h_px / h)
                if ratio < 1.0:
                    new_size = (int(w * ratio), int(h * ratio))
                    img = img.resize(new_size, Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, format='PNG')
                new_bytes = buf.getvalue()
        except Exception:
            # If resizing fails, fall back to original bytes
            new_bytes = app.logo_bytes
        # Overwrite the underlying image part
        image_part._blob = new_bytes


def _update_cover_slide(slide, topic: str) -> None:
    """
    Replace the ``$industry`` token on the cover slide with the
    provided topic string.  Any text shape containing the token will
    have it substituted without altering other characters.

    Parameters
    ----------
    slide: pptx.slide.Slide
        The cover slide to modify.
    topic: str
        The replacement topic string.
    """
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if '$industry' in shape.text:
            shape.text = shape.text.replace('$industry', topic)


def _update_closing_slide(slide, topic: str, final_url: str) -> None:
    """
    Update the closing slide with the topic and assign a hyperlink to
    the SFApps button/logo.  The template includes two text shapes
    which both contain ``$industry``; these are updated.  A picture
    shape bearing the SFApps logo is given a click hyperlink to
    ``final_url``.  If no such picture can be found the hyperlink
    assignment is silently skipped.

    Parameters
    ----------
    slide: pptx.slide.Slide
        The closing slide.
    topic: str
        The industry/category string.
    final_url: str
        URL to assign to the clickable logo.
    """
    # Replace $industry in text
    for shape in slide.shapes:
        if shape.has_text_frame:
            if '$industry' in shape.text:
                shape.text = shape.text.replace('$industry', topic)
    # Assign hyperlink to picture containing SFApps logo; heuristic is
    # to pick the image with a long width and small height (the pill
    # shaped button) – this is picture index 3 in the template.
    for shape in slide.shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            # Calculate aspect ratio; the SFApps pill button is wide and
            # short compared to others.
            w = shape.width / 914400.0
            h = shape.height / 914400.0
            if w > 4.0 and h < 2.0:
                # Assign hyperlink
                try:
                    shape.click_action.hyperlink.address = final_url
                except Exception:
                    pass
                break


def _scale_logo_to_fit(image_bytes: bytes, max_width: int, max_height: int) -> bytes:
    """
    Given raw image bytes, return new bytes scaled down to fit within
    ``max_width`` x ``max_height`` EMU.  If the original image is
    smaller than the bounding box it is returned unchanged.  DPI is
    assumed to be 96 for conversion.
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            w, h = img.size
            # Convert max dimensions to pixels
            max_w_px = int(max_width * 96 / 914400)
            max_h_px = int(max_height * 96 / 914400)
            ratio = min(max_w_px / w, max_h_px / h)
            if ratio < 1.0:
                new_size = (int(w * ratio), int(h * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
    except Exception:
        return image_bytes


def create_presentation_from_template(
    topic: str,
    links: List[str],
    final_url: str,
    template_path: str,
    output_pptx: str = 'output.pptx',
    output_pdf: Optional[str] = None,
    app_overrides: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> str:
    """
    Build a PPTX based upon a provided template.  The function
    preserves all original artwork and layout elements while updating
    just the dynamic content.  If more applications are provided
    than there are programme slides in the template, additional
    slides are cloned from the second programme slide to
    accommodate them.

    Parameters
    ----------
    topic: str
        Industry or category displayed on the cover and closing slide.
    links: List[str]
        AppExchange listing URLs; each will occupy one programme slide.
    final_url: str
        URL linked from the closing slide button.
    template_path: str
        Path to the PPTX template file.
    output_pptx: str, optional
        Destination path for the generated PPTX file.
    output_pdf: str, optional
        If provided and LibreOffice is installed the PPTX will be
        converted to PDF at this location.
    app_overrides: dict, optional
        Mapping of URL to a dictionary with keys "name", "developer"
        and optionally ``"logo_path"`` to override extracted data.

    Returns
    -------
    str
        Path to the written PPTX file.
    """
    # Prepare app metadata list
    apps: List[AppMetadata] = []
    overrides = app_overrides or {}
    for link in links:
        link = link.strip()
        meta = None
        if link in overrides:
            ovr = overrides[link]
            # Read logo bytes if provided; if not present we skip
            logo_bytes = None
            logo_mime = 'image/png'
            if 'logo_path' in ovr and ovr['logo_path']:
                try:
                    with open(ovr['logo_path'], 'rb') as f:
                        logo_bytes = f.read()
                except Exception:
                    logo_bytes = None
            meta = AppMetadata(
                url=link,
                name=ovr.get('name', ''),
                developer=ovr.get('developer', ''),
                logo_bytes=logo_bytes if logo_bytes else b'',
                logo_mime=logo_mime,
            )
        else:
            fetched = fetch_app_metadata(link)
            if fetched:
                meta = fetched
        if meta is None:
            # Fallback placeholder metadata if fetching failed
            meta = AppMetadata(
                url=link,
                name='Unknown App',
                developer='Unknown',
                logo_bytes=b'',
                logo_mime='image/png'
            )
        apps.append(meta)
    # Open template
    prs = Presentation(template_path)
    # Determine how many programme slides exist in template; in the
    # supplied file there are 10 (slides 2-11).  We'll treat any
    # slides between the cover (index 0) and closing slide (last) as
    # programme slides.
    total_slides = len(prs.slides)
    closing_index = total_slides - 1
    programme_start = 1
    programme_count = closing_index - programme_start
    needed = len(apps)
    # Clone the second programme slide if more slides are required
    if needed > programme_count:
        extra = needed - programme_count
        for _ in range(extra):
            _clone_slide(prs, programme_start)  # duplicate second programme slide
        # After cloning, programme_count grows accordingly and the
        # closing slide index shifts; update variables
        closing_index = len(prs.slides) - 1
    # Remove unused programme slides if fewer apps are supplied
    if needed < programme_count:
        # remove from the end of programme region until count matches
        remove_count = programme_count - needed
        # Remove slides starting just before closing_index, preserve closing
        for i in range(remove_count):
            _remove_slide(prs, closing_index - 1 - i)
        closing_index = len(prs.slides) - 1
    # Update cover slide
    _update_cover_slide(prs.slides[0], topic)
    # Update programme slides
    for i, app in enumerate(apps):
        slide_index = programme_start + i
        slide = prs.slides[slide_index]
        _update_slide_fields(slide, app, i + 1)
    # Update closing slide
    closing_slide = prs.slides[closing_index]
    _update_closing_slide(closing_slide, topic, final_url)
    # Save PPTX
    prs.save(output_pptx)
    # Optionally convert to PDF using LibreOffice
    if output_pdf:
        try:
            subprocess.run(
                [
                    'libreoffice',
                    '--headless',
                    '--convert-to',
                    'pdf',
                    '--outdir',
                    os.path.dirname(os.path.abspath(output_pdf)),
                    os.path.abspath(output_pptx),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            # If conversion fails silently ignore
            pass
    return output_pptx


if __name__ == '__main__':  # pragma: no cover
    import argparse
    parser = argparse.ArgumentParser(description='Build a PPTX from a template.')
    parser.add_argument('--topic', required=True, help='Topic or industry for the presentation')
    parser.add_argument('--links', required=True, help='Comma-separated list of AppExchange listing URLs')
    parser.add_argument('--final-url', required=True, help='URL to link from the closing slide')
    parser.add_argument('--template', default='template.pptx', help='Path to the PPTX template')
    parser.add_argument('--output', default='generated.pptx', help='Output PPTX file')
    parser.add_argument('--pdf', default=None, help='Optional output PDF file')
    args = parser.parse_args()
    links = [s.strip() for s in args.links.split(',') if s.strip()]
    create_presentation_from_template(
        topic=args.topic,
        links=links,
        final_url=args.final_url,
        template_path=args.template,
        output_pptx=args.output,
        output_pdf=args.pdf,
    )