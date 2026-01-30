#!/usr/bin/env python3
"""
Script to edit the downloaded archive site.
- Copies archive folder to publish folder
- Removes PayPal donation links
- Removes "eat"/"eats" header links
- Changes "Charm City Art Space is" to "Charm City Art Space was"
- Removes appreciation/donation request text
- Replaces donation text with closing message and link to The Undercroft
- Moves last show from current events to past events
- Adds mobile responsive CSS
"""

import os
import re
import shutil
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

# Load configuration
CONFIG_FILE = "config.yaml"


def load_config() -> dict:
    """Load configuration from YAML file."""
    config_path = Path(CONFIG_FILE)
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


config = load_config()
ARCHIVE_DIR = config.get('archive_dir', 'archive')
PUBLISH_DIR = config.get('publish_dir', 'docs')

UNDERCROFT_HTML = (
    'Charm City Art Space held its last show in November of 2015. '
    'If you would like to contribute to a community arts space in Baltimore, '
    'please consider <a href="https://theundercroft.org/">The Undercroft</a>.'
)

APPRECIATION_PATTERN = re.compile(
    r"Anything you can give is appreciated\.?\s*We need your help to keep us going\.?",
    re.IGNORECASE
)


def remove_paypal_links(soup: BeautifulSoup) -> int:
    """Remove PayPal donation links, forms, images, and related elements."""
    removed = 0

    # Remove links and forms
    for element in soup.find_all('a', href=True):
        href = element['href'].lower()
        if 'paypal' in href or 'donate' in href:
            element.decompose()
            removed += 1

    for form in soup.find_all('form', action=True):
        if 'paypal' in form['action'].lower():
            form.decompose()
            removed += 1

    # Remove PayPal images (and parent links)
    for img in soup.find_all('img'):
        src = (img.get('src') or '').lower()
        alt = (img.get('alt') or '').lower()
        if 'paypal' in src or 'paypal' in alt or 'donate' in alt:
            parent = img.parent
            (parent if parent and parent.name == 'a' else img).decompose()
            removed += 1

    # Remove elements with paypal/donate classes or ids
    for attr_search in [
        {'class_': re.compile(r'paypal|donate', re.IGNORECASE)},
        {'id': re.compile(r'paypal|donate', re.IGNORECASE)},
    ]:
        for element in soup.find_all(**attr_search):
            element.decompose()
            removed += 1

    # Remove remaining donate+paypal buttons/links
    for element in soup.find_all(['a', 'button', 'input']):
        text = element.get_text().lower()
        if 'donate' in text and 'paypal' in text:
            element.decompose()
            removed += 1

    return removed


def remove_eats_links(soup: BeautifulSoup) -> int:
    """Remove 'eats' and 'eat' header links and their parent list items."""
    removed = 0

    # Find and remove links first, then clean up empty parent li's
    for element in soup.find_all('a'):
        text = element.get_text().lower().strip()
        href = (element.get('href') or '').lower()

        if text in ['eats', 'eat'] or 'eats' in href or '/eat' in href or 'eat.html' in href:
            parent = element.parent
            if parent and parent.name == 'li':
                parent.decompose()
            else:
                element.decompose()
            removed += 1

    # Clean up any remaining bare li/span with just "eat"/"eats"
    for element in soup.find_all(['li', 'span']):
        if element.get_text().lower().strip() in ['eats', 'eat']:
            element.decompose()
            removed += 1

    return removed


def replace_text_patterns(soup: BeautifulSoup) -> tuple[int, int, int]:
    """Handle all text replacements: is->was, appreciation removal, donation replacement.
    Returns (is_was_count, appreciation_count, donation_count)."""
    is_was = 0
    appreciation = 0
    donation = 0

    # Replace "Charm City Art Space is" with "was"
    for text_node in soup.find_all(string=re.compile(r'Charm City Art Space is', re.IGNORECASE)):
        original = str(text_node)
        new_text = re.sub(r'Charm City Art Space is', 'Charm City Art Space was', original, flags=re.IGNORECASE)
        if new_text != original:
            text_node.replace_with(new_text)
            is_was += original.lower().count('charm city art space is')

    # Remove appreciation text
    for text_node in soup.find_all(string=APPRECIATION_PATTERN):
        original = str(text_node)
        new_text = APPRECIATION_PATTERN.sub('', original).strip()
        if new_text != original:
            if new_text:
                text_node.replace_with(new_text)
            else:
                parent = text_node.parent
                text_node.extract()
                if parent and not parent.get_text(strip=True):
                    parent.decompose()
            appreciation += 1

    # Replace donation request text with Undercroft message
    for element in soup.find_all(string=re.compile(r'Make a general donation to CCAS', re.IGNORECASE)):
        parent = element.parent
        if parent and 'Make a general donation' in parent.get_text():
            parent.clear()
            parent.append(BeautifulSoup(UNDERCROFT_HTML, 'html.parser'))
            donation += 1

    # Also check container elements
    for container in soup.find_all(['div', 'p', 'section', 'aside']):
        text = container.get_text()
        if 'Make a general donation to CCAS' in text and 'keep us going' in text:
            container.clear()
            container.append(BeautifulSoup(f'<p>{UNDERCROFT_HTML}</p>', 'html.parser'))
            donation += 1

    return is_was, appreciation, donation


def inject_hamburger_menu(soup: BeautifulSoup) -> bool:
    """Inject hamburger menu button and toggle script for mobile."""
    menu = soup.find(id='menu')
    if not menu or soup.find(id='hamburger-btn'):
        return False

    header = soup.find(id='header')

    # Create hamburger button
    hamburger = soup.new_tag('button', id='hamburger-btn')
    hamburger.attrs['aria-label'] = 'Menu'
    hamburger.attrs['type'] = 'button'
    hamburger.string = '\u2630'  # ☰

    # Place inside header for absolute positioning, or before menu as fallback
    if header:
        header.append(hamburger)
    else:
        menu.insert_before(hamburger)

    # Add toggle JavaScript
    script = soup.new_tag('script')
    script.string = """
(function() {
    var btn = document.getElementById('hamburger-btn');
    var menu = document.getElementById('menu');
    if (!btn || !menu) return;
    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        menu.classList.toggle('menu-open');
        btn.classList.toggle('active');
    });
    document.addEventListener('click', function(e) {
        if (!menu.contains(e.target) && !btn.contains(e.target)) {
            menu.classList.remove('menu-open');
            btn.classList.remove('active');
        }
    });
    var links = menu.getElementsByTagName('a');
    for (var i = 0; i < links.length; i++) {
        links[i].addEventListener('click', function() {
            menu.classList.remove('menu-open');
            btn.classList.remove('active');
        });
    }
})();"""
    body = soup.find('body')
    if body:
        body.append(script)
    else:
        soup.append(script)

    return True


def inject_mobile_banner(soup: BeautifulSoup) -> bool:
    """Inject a mobile-only banner with the closing message right under the header."""
    menu = soup.find(id='menu')
    if not menu or soup.find(id='mobile-banner'):
        return False

    banner = soup.new_tag('div', id='mobile-banner')
    banner.append(BeautifulSoup(UNDERCROFT_HTML, 'html.parser'))

    # Insert after #menu so it appears between menu and content in the flex layout
    menu.insert_after(banner)
    return True


def inject_responsive(soup: BeautifulSoup, css_relative_path: str) -> bool:
    """Inject viewport meta tag and link to responsive CSS."""
    head = soup.find('head')
    if not head:
        html_tag = soup.find('html')
        if not html_tag:
            return False
        head = soup.new_tag('head')
        html_tag.insert(0, head)

    injected = False

    if not soup.find('meta', attrs={'name': 'viewport'}):
        viewport = soup.new_tag('meta')
        viewport['name'] = 'viewport'
        viewport['content'] = 'width=device-width, initial-scale=1.0'
        head.insert(0, viewport)
        injected = True

    if not soup.find('link', href=re.compile(r'responsive\.css')):
        link = soup.new_tag('link')
        link['rel'] = 'stylesheet'
        link['href'] = css_relative_path
        head.append(link)
        injected = True

    return injected


def process_html_file(file_path: Path, publish_path: Path) -> dict[str, int]:
    """Process a single HTML file. Returns dict of change counts."""
    counts = {'paypal': 0, 'eats': 0, 'is_was': 0, 'appreciation': 0, 'donation': 0, 'responsive': 0, 'hamburger': 0, 'banner': 0}

    try:
        html = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            html = file_path.read_text(encoding='latin-1')
        except Exception:
            return counts

    soup = BeautifulSoup(html, 'html.parser')

    counts['paypal'] = remove_paypal_links(soup)
    counts['eats'] = remove_eats_links(soup)
    counts['is_was'], counts['appreciation'], counts['donation'] = replace_text_patterns(soup)

    css_relative_path = os.path.relpath(publish_path / 'responsive.css', file_path.parent)
    if inject_responsive(soup, css_relative_path):
        counts['responsive'] = 1

    if inject_hamburger_menu(soup):
        counts['hamburger'] = 1

    if inject_mobile_banner(soup):
        counts['banner'] = 1

    if any(counts.values()):
        file_path.write_text(str(soup), encoding='utf-8')

    return counts


def create_responsive_css(publish_path: Path) -> None:
    """Create a responsive.css file in the publish directory."""
    css = '''/* Hidden on desktop */
#hamburger-btn {
    display: none;
}

#mobile-banner {
    display: none;
}

/* Mobile responsive overrides */
@media screen and (max-width: 768px) {
    /* Sticky header/footer layout using flexbox */
    html, body {
        overflow: hidden !important;
        width: 100% !important;
        height: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    body {
        font-size: 16px !important;
        line-height: 1.5 !important;
    }

    #container {
        display: flex !important;
        flex-direction: column !important;
        height: 100vh !important;
        height: 100dvh !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        overflow: hidden !important;
        position: relative !important;
        box-sizing: border-box !important;
    }

    /* Sticky header */
    #header {
        flex-shrink: 0 !important;
        position: relative !important;
        width: 100% !important;
        z-index: 100 !important;
        height: auto !important;
    }

    #header img {
        width: 100% !important;
        height: auto !important;
        display: block !important;
    }

    /* Hamburger button */
    #hamburger-btn {
        display: block !important;
        position: absolute !important;
        right: 10px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        z-index: 200 !important;
        background: rgba(204, 102, 0, 0.9) !important;
        color: white !important;
        border: none !important;
        font-size: 24px !important;
        line-height: 1 !important;
        padding: 6px 12px !important;
        cursor: pointer !important;
        border-radius: 4px !important;
    }

    #hamburger-btn.active {
        background: rgba(153, 85, 0, 0.95) !important;
    }

    /* Menu - hidden by default, dropdown when hamburger is active */
    #menu {
        display: none !important;
        flex-shrink: 0 !important;
        width: 100% !important;
        height: auto !important;
        background: #CC6600 !important;
        z-index: 99 !important;
        box-sizing: border-box !important;
    }

    #menu.menu-open {
        display: block !important;
    }

    #menu a {
        display: block !important;
        padding: 12px 20px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        text-decoration: none !important;
        font-size: 16px !important;
        width: auto !important;
    }

    #menu a:last-child {
        border-bottom: none !important;
    }

    #menu a:hover,
    #menu a:active {
        background: #995500 !important;
        text-decoration: none !important;
    }

    /* Mobile banner - closing message under header */
    #mobile-banner {
        display: block !important;
        flex-shrink: 0 !important;
        width: 100% !important;
        background: #996600 !important;
        color: white !important;
        padding: 8px 15px !important;
        font-size: 13px !important;
        line-height: 1.4 !important;
        text-align: center !important;
        box-sizing: border-box !important;
        z-index: 98 !important;
    }

    #mobile-banner a {
        color: #FFD700 !important;
        text-decoration: underline !important;
    }

    /* Scrollable content area */
    #content {
        flex: 1 1 auto !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        width: 100% !important;
        max-width: 100% !important;
        height: auto !important;
        min-height: 0 !important;
        padding: 10px !important;
        box-sizing: border-box !important;
        position: relative !important;
    }

    /* Main text area fluid */
    .text {
        width: 100% !important;
        max-width: 100% !important;
        position: static !important;
        float: none !important;
        display: block !important;
        margin: 0 !important;
        padding: 10px 5px !important;
        box-sizing: border-box !important;
        left: auto !important;
        top: auto !important;
    }

    /* Hide sidebar on mobile - content is in the mobile banner */
    #notes {
        display: none !important;
    }

    /* Sticky footer */
    #footer {
        flex-shrink: 0 !important;
        width: 100% !important;
        z-index: 100 !important;
        height: auto !important;
    }

    #footer img {
        width: 100% !important;
        height: auto !important;
        display: block !important;
    }

    /* Tables */
    table {
        width: 100% !important;
        max-width: 100% !important;
        table-layout: auto !important;
    }

    td, th {
        display: block !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Responsive media */
    img {
        max-width: 100% !important;
        height: auto !important;
    }

    iframe, embed, object, video {
        max-width: 100% !important;
        height: auto !important;
    }

    /* Text overflow */
    p, li, span, a, h1, h2, h3, h4, h5, h6, div {
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    pre, code {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        max-width: 100% !important;
        overflow-x: auto !important;
    }

    /* Stack layouts vertically */
    #sidebar, #left, #right,
    .sidebar, .left, .right,
    #leftcol, #rightcol, #maincol,
    .leftcol, .rightcol, .maincol {
        width: 100% !important;
        float: none !important;
        display: block !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }

    /* Headings */
    h1 { font-size: 1.6em !important; }
    h2 { font-size: 1.4em !important; }
    h3 { font-size: 1.2em !important; }

    /* Hide spacer elements */
    img[width="1"], img[height="1"],
    td[width="1"], td[height="1"] {
        display: none !important;
    }

    center { text-align: left !important; }
}

/* Small phones */
@media screen and (max-width: 480px) {
    body {
        font-size: 14px !important;
    }

    #hamburger-btn {
        font-size: 20px !important;
        padding: 4px 10px !important;
    }

    #menu a {
        padding: 10px 15px !important;
        font-size: 14px !important;
    }

    h1 { font-size: 1.4em !important; }
    h2 { font-size: 1.2em !important; }
    h3 { font-size: 1.1em !important; }
}
'''
    (publish_path / 'responsive.css').write_text(css, encoding='utf-8')
    print("  Created responsive.css")


def add_content_divs(publish_path: Path) -> dict:
    """Add div elements with id='newContent' at specific locations for content injection.

    Returns dict with keys 'index' and 'events' indicating success.
    """
    results = {'index': False, 'events': False}

    # 1. Add newContent div to index.html after the blurb paragraph
    index_page = publish_path / 'index.html'
    if index_page.exists():
        html = index_page.read_text(encoding='utf-8')
        blurb_marker = 'from all over to showcase their work in our fine city.<br/>\n</div>'

        if blurb_marker in html:
            # Check if newContent div already added at this location
            if blurb_marker + '\n<div id="newContent"></div>' not in html:
                # Insert the newContent div after the blurb div
                html = html.replace(
                    blurb_marker,
                    blurb_marker + '\n<div id="newContent"></div>',
                    1  # Only replace first occurrence
                )
                index_page.write_text(html, encoding='utf-8')
                results['index'] = True

    # 2. Add newContent div to events.html after the blurb paragraph
    events_page = publish_path / 'events.html'
    if events_page.exists():
        html = events_page.read_text(encoding='utf-8')
        blurb_marker = '<div class="blurb">CCAS is dedicated to promoting independent arts of all mediums in Baltimore City.  Click the link below to find out about  our  gallery schedule.</div>'

        if blurb_marker in html:
            # Check if newContent div already added at this location
            if blurb_marker + '\n<div id="newContent"></div>' not in html:
                # Insert the newContent div after the blurb div
                html = html.replace(
                    blurb_marker,
                    blurb_marker + '\n<div id="newContent"></div>',
                    1  # Only replace first occurrence
                )
                events_page.write_text(html, encoding='utf-8')
                results['events'] = True

    return results


def move_last_show_to_past_events(publish_path: Path) -> bool:
    """Move the last show from the events page to the past events page with correct show number.

    Uses regex on raw HTML to avoid BeautifulSoup restructuring the malformed
    nested <p> tags in events.html, which would merge the show paragraph with
    the Gallery/Past Events links.
    """
    last_show_marker = "LAST SHOW AT 1731 MARYAND AVE"

    events_page = publish_path / 'events.html'
    past_page = publish_path / 'past.html'

    if not events_page.exists():
        print("  Could not find events.html")
        return False
    if not past_page.exists():
        print("  Could not find past.html")
        return False

    # Remove the last show from events page using regex (not BS) to preserve
    # surrounding HTML structure with malformed <p> nesting
    events_html = events_page.read_text(encoding='utf-8')
    if last_show_marker not in events_html:
        print("  Last show not found on events page")
        return False

    show_pattern = re.compile(
        r'<p[^>]*>\s*<b>\s*Wednesday,\s*November\s*11th.*?'
        r'LAST SHOW AT 1731 MARYAND AVE.*?'
        r'Jumbled\b.*?</p>',
        re.DOTALL | re.IGNORECASE
    )

    new_html = show_pattern.sub('', events_html, count=1)
    if new_html != events_html:
        events_page.write_text(new_html, encoding='utf-8')
        print("  Removed last show from events.html")
    else:
        print("  Could not match last show pattern in events.html")
        return False

    # Check if already on past events page
    past_html = past_page.read_text(encoding='utf-8')
    if last_show_marker in past_html:
        print("  Last show already exists on past.html with correct numbering")
        return True

    # Find the last show number on the past events page
    last_number = 0
    for match in re.finditer(r'^(\d{1,4})\.', past_html, re.MULTILINE):
        num = int(match.group(1))
        if num > last_number:
            last_number = num

    next_number = last_number + 1

    # Format in past events style (number, date without time, no contact info)
    show_entry = (
        f'<p>{next_number}. <b>Wednesday, November 11th</b><br>'
        'LAST SHOW AT 1731 MARYAND AVE<br>'
        'Eze Jackson<br>'
        'Dylijens<br>'
        'Cornelius the Third<br>'
        'Kahlil Ali<br>'
        'Jumbled</p>\n'
    )

    # Insert before the NOTICE paragraph or end of content div
    notice_pos = past_html.find('NOTICE: DUE TO UNFORSEEN')
    if notice_pos >= 0:
        insert_pos = past_html.rfind('<p', 0, notice_pos)
        if insert_pos >= 0:
            past_html = past_html[:insert_pos] + show_entry + past_html[insert_pos:]
            past_page.write_text(past_html, encoding='utf-8')
            print(f"  Added last show as #{next_number} to past.html")
            return True

    # Fallback: insert before closing </div> of text area
    text_div_end = past_html.find('</div>', past_html.rfind(str(last_number) + '.'))
    if text_div_end >= 0:
        past_html = past_html[:text_div_end] + show_entry + past_html[text_div_end:]
        past_page.write_text(past_html, encoding='utf-8')
        print(f"  Added last show as #{next_number} to past.html")
        return True

    print("  Could not find insertion point in past events page")
    return False


def main():
    archive_path = Path(ARCHIVE_DIR)
    publish_path = Path(PUBLISH_DIR)

    if not archive_path.exists():
        print(f"Archive directory '{ARCHIVE_DIR}' not found!")
        return

    # Copy archive to publish folder
    print(f"Copying {ARCHIVE_DIR} to {PUBLISH_DIR}...")
    if publish_path.exists():
        print(f"  Removing existing {PUBLISH_DIR} folder...")
        shutil.rmtree(publish_path)
    shutil.copytree(archive_path, publish_path)
    print("  Copied successfully!")

    # Create responsive CSS
    print("\nCreating responsive CSS...")
    create_responsive_css(publish_path)

    # Process HTML files
    html_files = list(publish_path.rglob('*.html'))
    print(f"\nFound {len(html_files)} HTML files to process")

    totals = {'paypal': 0, 'eats': 0, 'is_was': 0, 'appreciation': 0, 'donation': 0, 'responsive': 0, 'hamburger': 0, 'banner': 0}
    files_modified = 0

    labels = {
        'paypal': 'Removed {} PayPal element(s)',
        'eats': 'Removed {} Eats element(s)',
        'is_was': "Replaced {} 'is' -> 'was' occurrence(s)",
        'appreciation': 'Removed {} appreciation text(s)',
        'donation': 'Replaced {} donation text(s) with Undercroft message',
        'responsive': 'Injected responsive CSS',
        'hamburger': 'Injected hamburger menu',
        'banner': 'Injected mobile banner',
    }

    for file_path in html_files:
        counts = process_html_file(file_path, publish_path)

        if any(counts.values()):
            files_modified += 1
            print(f"  Modified: {file_path.relative_to(publish_path)}")
            for key, count in counts.items():
                if count > 0:
                    print(f"    - {labels[key].format(count)}")

        for key in totals:
            totals[key] += counts[key]

    # Move last show
    print("\nMoving last show to past events...")
    last_show_moved = move_last_show_to_past_events(publish_path)

    # Add newContent divs for dynamic content injection
    print("\nAdding newContent divs...")
    content_divs = add_content_divs(publish_path)
    if content_divs['index']:
        print("  Added newContent div to index.html")
    if content_divs['events']:
        print("  Added newContent div to events.html")

    print(f"\n{'='*50}")
    print(f"Edit complete!")
    print(f"Output directory: {publish_path.absolute()}")
    print(f"Files modified: {files_modified}")
    for key, label in labels.items():
        print(f"  {label.format(totals[key])}")
    print(f"  Last show moved: {'Yes' if last_show_moved else 'No'}")
    print(f"  newContent divs added: {sum(content_divs.values())} of 2")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
