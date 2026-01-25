#!/usr/bin/env python3
"""
Script to download the latest Wayback Machine snapshot of ccspace.org
and create a clean static site archive with all assets.
All Wayback Machine artifacts are stripped out.
PHP files are converted to .html files.
"""

import os
import re
import hashlib
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup, Comment

# Configuration
DOMAIN = "ccspace.org"
ARCHIVE_DIR = "archive"
WAYBACK_CDX_API = "https://web.archive.org/cdx/search/cdx"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Specific snapshot to use
SNAPSHOT_TIMESTAMP = "20170509211847"
SNAPSHOT_URL = "http://www.ccspace.org/"

# File extensions to download as assets
ASSET_EXTENSIONS = {
    '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
    '.woff', '.woff2', '.ttf', '.eot', '.otf', '.webp', '.mp4', '.webm',
    '.pdf', '.json', '.xml', '.map'
}

# Wayback URL pattern
WAYBACK_PATTERN = re.compile(
    r'(?:https?:)?//web\.archive\.org/web/(\d+)(?:[a-z]*_)?/(https?://[^\s"\'<>]+|[^\s"\'<>]+)'
)

# Pattern to match PHP URLs with query parameters
PHP_ACTION_PATTERN = re.compile(r'index\.php\?action=([^&\s"\'<>]+)')


class WaybackArchiver:
    def __init__(self, domain: str, output_dir: str):
        self.domain = domain
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.downloaded_urls = set()
        self.url_to_local = {}  # Maps original URL -> local Path
        self.php_to_html = {}   # Maps PHP URL patterns -> HTML filenames
        self.snapshot_timestamp = None

    def get_latest_snapshot_timestamp(self) -> str | None:
        """Get the snapshot timestamp to use."""
        # Use the specific snapshot timestamp
        self.snapshot_timestamp = SNAPSHOT_TIMESTAMP
        print(f"Using snapshot from {SNAPSHOT_TIMESTAMP}")
        print(f"Snapshot URL: https://web.archive.org/web/{SNAPSHOT_TIMESTAMP}/{SNAPSHOT_URL}")
        return self.snapshot_timestamp

    def get_all_pages(self) -> list[tuple[str, str]]:
        """Get all archived pages for the domain around the snapshot timestamp."""
        print(f"Fetching list of all archived pages...")

        pages = []

        # Search for both www and non-www versions
        search_urls = [f'www.{self.domain}/*', f'{self.domain}/*']

        for search_url in search_urls:
            response = self.session.get(
                WAYBACK_CDX_API,
                params={
                    'url': search_url,
                    'output': 'json',
                    'filter': 'statuscode:200',
                    'fl': 'original,timestamp,mimetype',
                    'from': SNAPSHOT_TIMESTAMP[:8],  # Use date part for range
                    'to': SNAPSHOT_TIMESTAMP[:8],
                }
            )

            if response.status_code == 200:
                data = response.json()
                if len(data) > 1:
                    # Get the closest timestamp to our target for each URL
                    url_data = {}
                    for row in data[1:]:
                        original_url = row[0]
                        timestamp = row[1]
                        mimetype = row[2] if len(row) > 2 else ''

                        # Only include HTML pages
                        if 'text/html' in mimetype or not mimetype:
                            # Prefer timestamp closest to our snapshot
                            if original_url not in url_data:
                                url_data[original_url] = timestamp
                            elif abs(int(timestamp) - int(SNAPSHOT_TIMESTAMP)) < abs(int(url_data[original_url]) - int(SNAPSHOT_TIMESTAMP)):
                                url_data[original_url] = timestamp

                    for url, ts in url_data.items():
                        pages.append((ts, url))

        # If no pages found for that exact date, search broader
        if not pages:
            print("No pages found for exact date, searching broader range...")
            for search_url in search_urls:
                response = self.session.get(
                    WAYBACK_CDX_API,
                    params={
                        'url': search_url,
                        'output': 'json',
                        'filter': 'statuscode:200',
                        'fl': 'original,timestamp,mimetype',
                        'from': '2017',
                        'to': '2017',
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if len(data) > 1:
                        url_data = {}
                        for row in data[1:]:
                            original_url = row[0]
                            timestamp = row[1]
                            mimetype = row[2] if len(row) > 2 else ''

                            if 'text/html' in mimetype or not mimetype:
                                if original_url not in url_data:
                                    url_data[original_url] = timestamp
                                elif abs(int(timestamp) - int(SNAPSHOT_TIMESTAMP)) < abs(int(url_data[original_url]) - int(SNAPSHOT_TIMESTAMP)):
                                    url_data[original_url] = timestamp

                        for url, ts in url_data.items():
                            pages.append((ts, url))

        print(f"Found {len(pages)} pages")
        return pages

    def build_raw_wayback_url(self, timestamp: str, original_url: str) -> str:
        """Build a Wayback URL that returns raw/original content."""
        # id_ modifier returns the original content without any modifications
        return f"https://web.archive.org/web/{timestamp}id_/{original_url}"

    def download_content(self, timestamp: str, original_url: str, is_binary: bool = False) -> bytes | str | None:
        """Download content from the Wayback Machine."""
        cache_key = f"{timestamp}/{original_url}"
        if cache_key in self.downloaded_urls:
            return None

        wayback_url = self.build_raw_wayback_url(timestamp, original_url)

        try:
            response = self.session.get(wayback_url, timeout=30)

            if response.status_code == 200:
                self.downloaded_urls.add(cache_key)
                if is_binary:
                    return response.content
                return response.text
            else:
                print(f"  HTTP {response.status_code} for {original_url}")
        except Exception as e:
            print(f"  Error downloading {original_url}: {e}")

        return None

    def clean_url(self, url: str) -> str | None:
        """Extract original URL from a potentially Wayback-wrapped URL."""
        if not url:
            return None

        # Skip non-http URLs
        if url.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '#', 'about:')):
            return None

        # Check if it's a Wayback URL and extract the original
        match = WAYBACK_PATTERN.match(url)
        if match:
            original = match.group(2)
            if not original.startswith('http'):
                original = 'https://' + original
            return original

        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url

        # Return as-is if it's already a clean URL
        if url.startswith(('http://', 'https://')):
            return url

        return url

    def url_to_local_path(self, url: str) -> Path:
        """Convert a URL to a local file path. PHP files are converted to HTML."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')

        if not path:
            path = 'index.html'
        elif path.endswith('/'):
            path = path + 'index.html'
        elif '.' not in path.split('/')[-1]:
            path = path + '/index.html'

        # Handle query strings - create meaningful names for PHP action URLs
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)

            # Special handling for index.php?action=X patterns
            if 'action' in query_params and path.endswith('.php'):
                action = query_params['action'][0]
                # Create a clean filename from the action
                action_clean = re.sub(r'[^\w\-]', '_', action)
                base_dir = os.path.dirname(path)
                if base_dir:
                    path = f"{base_dir}/{action_clean}.html"
                else:
                    path = f"{action_clean}.html"
                # Store mapping for link rewriting
                php_pattern = f"{parsed.path}?action={action}"
                self.php_to_html[php_pattern] = path
            else:
                # Generic query string handling
                query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
                base, ext = os.path.splitext(path)
                path = f"{base}_{query_hash}{ext}"

        # Convert .php extension to .html
        if path.endswith('.php'):
            path = path[:-4] + '.html'

        return self.output_dir / path

    def convert_php_url_to_html_path(self, url: str) -> str | None:
        """Convert a PHP URL to its local HTML path."""
        if not url:
            return None

        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        query = parsed.query

        # Check for index.php?action=X pattern
        if query and path.endswith('.php'):
            query_params = urllib.parse.parse_qs(query)
            if 'action' in query_params:
                action = query_params['action'][0]
                php_pattern = f"{path}?action={action}"
                if php_pattern in self.php_to_html:
                    return self.php_to_html[php_pattern]
                # Generate expected path even if not in mapping yet
                action_clean = re.sub(r'[^\w\-]', '_', action)
                base_dir = os.path.dirname(path.strip('/'))
                if base_dir:
                    return f"{base_dir}/{action_clean}.html"
                return f"{action_clean}.html"

        # Simple .php to .html conversion
        if path.endswith('.php'):
            return path[:-4] + '.html'

        return None

    def strip_wayback_artifacts(self, html: str) -> str:
        """Remove all Wayback Machine artifacts from HTML."""
        # Remove Wayback toolbar comments and content
        html = re.sub(
            r'<!--\s*BEGIN WAYBACK TOOLBAR INSERT\s*-->.*?<!--\s*END WAYBACK TOOLBAR INSERT\s*-->',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove wombat.js and other archive.org scripts
        html = re.sub(
            r'<script[^>]*src=["\'][^"\']*(?:archive\.org|wombat)[^"\']*["\'][^>]*>.*?</script>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove inline scripts containing archive.org references
        html = re.sub(
            r'<script[^>]*>(?:(?!</script>).)*(?:__wm\.|wombat|archive\.org|WB_wombat)(?:(?!</script>).)*</script>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove archive.org stylesheets
        html = re.sub(
            r'<link[^>]*href=["\'][^"\']*archive\.org[^"\']*["\'][^>]*>',
            '', html, flags=re.IGNORECASE
        )

        # Remove style blocks with archive.org content
        html = re.sub(
            r'<style[^>]*>(?:(?!</style>).)*archive\.org(?:(?!</style>).)*</style>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )

        # Clean up Wayback URLs in remaining content
        def replace_wayback_url(match):
            original = match.group(2)
            if not original.startswith('http'):
                original = 'https://' + original
            return original

        html = WAYBACK_PATTERN.sub(replace_wayback_url, html)

        return html

    def extract_and_clean_urls(self, html: str, base_url: str) -> set[str]:
        """Extract all URLs from HTML and return clean original URLs."""
        urls = set()
        soup = BeautifulSoup(html, 'html.parser')

        # Remove Wayback elements first
        for element in soup.find_all(id=re.compile(r'^wm-|^playback', re.IGNORECASE)):
            element.decompose()
        for element in soup.find_all(class_=re.compile(r'^wm-', re.IGNORECASE)):
            element.decompose()

        # Remove HTML comments (including Wayback markers)
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Extract URLs from various attributes
        url_attrs = [
            ('a', 'href'), ('link', 'href'), ('script', 'src'),
            ('img', 'src'), ('source', 'src'), ('video', 'src'),
            ('video', 'poster'), ('audio', 'src'), ('iframe', 'src'),
            ('object', 'data'), ('embed', 'src'), ('form', 'action'),
        ]

        parsed_base = urllib.parse.urlparse(base_url)
        base_for_relative = f"{parsed_base.scheme}://{parsed_base.netloc}"

        for tag, attr in url_attrs:
            for element in soup.find_all(tag):
                value = element.get(attr)
                if value:
                    clean = self.clean_url(value)
                    if clean:
                        # Handle relative URLs
                        if not clean.startswith(('http://', 'https://')):
                            if clean.startswith('/'):
                                clean = base_for_relative + clean
                            else:
                                clean = urllib.parse.urljoin(base_url, clean)
                        urls.add(clean)

        # Handle srcset
        for element in soup.find_all(srcset=True):
            for part in element['srcset'].split(','):
                url = part.strip().split()[0] if part.strip() else ''
                if url:
                    clean = self.clean_url(url)
                    if clean:
                        if not clean.startswith(('http://', 'https://')):
                            if clean.startswith('/'):
                                clean = base_for_relative + clean
                            else:
                                clean = urllib.parse.urljoin(base_url, clean)
                        urls.add(clean)

        # Extract from inline styles
        css_url_pattern = re.compile(r'url\(["\']?([^)"\']+)["\']?\)')

        for style in soup.find_all('style'):
            if style.string:
                for match in css_url_pattern.finditer(style.string):
                    clean = self.clean_url(match.group(1))
                    if clean:
                        if not clean.startswith(('http://', 'https://')):
                            clean = urllib.parse.urljoin(base_url, clean)
                        urls.add(clean)

        for element in soup.find_all(style=True):
            for match in css_url_pattern.finditer(element['style']):
                clean = self.clean_url(match.group(1))
                if clean:
                    if not clean.startswith(('http://', 'https://')):
                        clean = urllib.parse.urljoin(base_url, clean)
                    urls.add(clean)

        return urls

    def rewrite_html_links(self, html: str, page_path: Path) -> str:
        """Rewrite all URLs in HTML to point to local files."""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove all Wayback-related elements
        for element in soup.find_all(id=re.compile(r'^wm-|^playback|^donato', re.IGNORECASE)):
            element.decompose()
        for element in soup.find_all(class_=re.compile(r'^wm-|^wb-', re.IGNORECASE)):
            element.decompose()

        # Remove scripts with archive.org
        for script in soup.find_all('script'):
            src = script.get('src', '')
            content = script.string or ''
            if 'archive.org' in src or 'wombat' in src or \
               'archive.org' in content or '__wm' in content or 'wombat' in content:
                script.decompose()

        # Remove archive.org links/styles
        for link in soup.find_all('link'):
            href = link.get('href', '')
            if 'archive.org' in href:
                link.decompose()

        # Remove HTML comments
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # Rewrite URLs in attributes
        url_attrs = [
            ('a', 'href'), ('link', 'href'), ('script', 'src'),
            ('img', 'src'), ('source', 'src'), ('video', 'src'),
            ('video', 'poster'), ('audio', 'src'), ('iframe', 'src'),
            ('object', 'data'), ('embed', 'src'),
        ]

        for tag, attr in url_attrs:
            for element in soup.find_all(tag):
                value = element.get(attr)
                if not value:
                    continue

                # Clean Wayback URL first
                clean = self.clean_url(value)
                if not clean:
                    continue

                # Check if we have a local copy
                if clean in self.url_to_local:
                    local_path = self.url_to_local[clean]
                    relative = os.path.relpath(local_path, page_path.parent)
                    element[attr] = relative
                elif self.domain in clean or f'www.{self.domain}' in clean:
                    # It's from our domain - check if it's a PHP URL
                    html_path = self.convert_php_url_to_html_path(clean)
                    if html_path:
                        # Convert to relative path from current page
                        full_html_path = self.output_dir / html_path.lstrip('/')
                        relative = os.path.relpath(full_html_path, page_path.parent)
                        element[attr] = relative
                    else:
                        # Make relative anyway
                        parsed = urllib.parse.urlparse(clean)
                        element[attr] = parsed.path or '/'
                else:
                    # External URL - keep clean version
                    element[attr] = clean

        # Rewrite srcset
        for element in soup.find_all(srcset=True):
            new_parts = []
            for part in element['srcset'].split(','):
                parts = part.strip().split()
                if parts:
                    url = parts[0]
                    clean = self.clean_url(url)
                    if clean and clean in self.url_to_local:
                        local_path = self.url_to_local[clean]
                        relative = os.path.relpath(local_path, page_path.parent)
                        parts[0] = relative
                    elif clean:
                        parts[0] = clean
                    new_parts.append(' '.join(parts))
            element['srcset'] = ', '.join(new_parts)

        # Rewrite relative PHP action links (e.g., href="index.php?action=foo")
        for element in soup.find_all(href=True):
            href = element['href']
            # Skip if already processed or external
            if href.startswith(('http://', 'https://', '#', 'mailto:', 'tel:', 'javascript:')):
                continue

            # Check for PHP action URLs (e.g., index.php?action=foo)
            match = PHP_ACTION_PATTERN.search(href)
            if match:
                action = match.group(1)
                action_clean = re.sub(r'[^\w\-]', '_', action)
                # Determine the directory from the PHP path
                php_path = href.split('?')[0]
                base_dir = os.path.dirname(php_path)
                if base_dir and base_dir != '.':
                    html_file = f"{base_dir}/{action_clean}.html"
                else:
                    html_file = f"{action_clean}.html"
                element['href'] = html_file
            # Check for simple .php links without query params
            elif href.endswith('.php'):
                element['href'] = href[:-4] + '.html'
            # Check for .php with other query params
            elif '.php?' in href:
                # Convert the PHP part to HTML and keep query params as hash for filename
                php_part = href.split('?')[0]
                query_part = href.split('?')[1]
                query_hash = hashlib.md5(query_part.encode()).hexdigest()[:8]
                element['href'] = f"{php_part[:-4]}_{query_hash}.html"

        # Convert absolute paths starting with / to relative paths
        for element in soup.find_all(href=True):
            href = element['href']
            if href.startswith('/') and not href.startswith('//'):
                # Convert absolute path to relative path
                absolute_path = self.output_dir / href.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                element['href'] = relative

        # Also handle src attributes for any PHP references
        for element in soup.find_all(src=True):
            src = element['src']
            if src.endswith('.php'):
                element['src'] = src[:-4] + '.html'

        # Handle form actions pointing to PHP
        for form in soup.find_all('form', action=True):
            action = form['action']
            if action.endswith('.php'):
                form['action'] = action[:-4] + '.html'
            elif PHP_ACTION_PATTERN.search(action):
                match = PHP_ACTION_PATTERN.search(action)
                action_name = match.group(1)
                action_clean = re.sub(r'[^\w\-]', '_', action_name)
                form['action'] = f"{action_clean}.html"

        # Fix local HTML links that incorrectly start with //
        # e.g., //manifesto.html -> manifesto.html
        for element in soup.find_all(href=True):
            href = element['href']
            if href.startswith('//'):
                # Check if it's a local file (ends with .html or other local extensions)
                remainder = href[2:]
                if remainder.endswith('.html') or '.html?' in remainder or '.html#' in remainder:
                    element['href'] = remainder
                elif '.' not in remainder.split('/')[0]:
                    # No domain (no dot in first part), likely a local path
                    element['href'] = remainder
                else:
                    # External URL, add https:
                    element['href'] = 'https:' + href

        for element in soup.find_all(src=True):
            src = element['src']
            if src.startswith('//'):
                remainder = src[2:]
                if remainder.endswith('.html') or '.html?' in remainder:
                    element['src'] = remainder
                elif '.' not in remainder.split('/')[0]:
                    element['src'] = remainder
                else:
                    element['src'] = 'https:' + src

        # Fix malformed local HTML links (e.g., https://booking.html -> booking.html)
        for element in soup.find_all(href=True):
            href = element['href']
            # Match patterns like https://something.html or http://something.html where it's a local file
            if re.match(r'^https?://[^/]+\.html$', href):
                # Extract just the filename
                element['href'] = href.split('://')[-1]
            elif re.match(r'^https?://[^/]+\.html\?', href):
                # Handle with query strings
                element['href'] = href.split('://')[-1]

        for element in soup.find_all(src=True):
            src = element['src']
            if re.match(r'^https?://[^/]+\.html$', src):
                element['src'] = src.split('://')[-1]

        for element in soup.find_all(action=True):
            if element['action'].startswith('//'):
                element['action'] = 'https:' + element['action']

        for element in soup.find_all(data=True):
            if element['data'].startswith('//'):
                element['data'] = 'https:' + element['data']

        for element in soup.find_all(poster=True):
            if element['poster'].startswith('//'):
                element['poster'] = 'https:' + element['poster']

        # Convert all absolute paths starting with / to relative paths
        # Handle src attributes
        for element in soup.find_all(src=True):
            src = element['src']
            if src.startswith('/') and not src.startswith('//'):
                absolute_path = self.output_dir / src.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                element['src'] = relative

        # Handle action attributes (forms)
        for element in soup.find_all(action=True):
            action = element['action']
            if action.startswith('/') and not action.startswith('//'):
                absolute_path = self.output_dir / action.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                element['action'] = relative

        # Handle data attributes (object tags)
        for element in soup.find_all(data=True):
            data = element['data']
            if data.startswith('/') and not data.startswith('//'):
                absolute_path = self.output_dir / data.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                element['data'] = relative

        # Handle poster attributes (video tags)
        for element in soup.find_all(poster=True):
            poster = element['poster']
            if poster.startswith('/') and not poster.startswith('//'):
                absolute_path = self.output_dir / poster.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                element['poster'] = relative

        # Handle srcset attributes
        for element in soup.find_all(srcset=True):
            srcset = element['srcset']
            new_parts = []
            for part in srcset.split(','):
                parts = part.strip().split()
                if parts:
                    # Convert // to https://
                    if parts[0].startswith('//'):
                        parts[0] = 'https:' + parts[0]
                    # Convert absolute paths to relative
                    elif parts[0].startswith('/'):
                        absolute_path = self.output_dir / parts[0].lstrip('/')
                        relative = os.path.relpath(absolute_path, page_path.parent)
                        parts[0] = relative
                new_parts.append(' '.join(parts))
            element['srcset'] = ', '.join(new_parts)

        # Clean inline styles
        css_url_pattern = re.compile(r'url\(["\']?([^)"\']+)["\']?\)')

        def replace_css_url(match):
            url = match.group(1)
            # Handle absolute paths starting with /
            if url.startswith('/') and not url.startswith('//'):
                absolute_path = self.output_dir / url.lstrip('/')
                relative = os.path.relpath(absolute_path, page_path.parent)
                return f'url("{relative}")'
            clean = self.clean_url(url)
            if clean and clean in self.url_to_local:
                local_path = self.url_to_local[clean]
                relative = os.path.relpath(local_path, page_path.parent)
                return f'url("{relative}")'
            elif clean:
                return f'url("{clean}")'
            return match.group(0)

        for element in soup.find_all(style=True):
            element['style'] = css_url_pattern.sub(replace_css_url, element['style'])

        # Also handle style tags
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = css_url_pattern.sub(replace_css_url, style_tag.string)

        return str(soup)

    def rewrite_css(self, css: str, css_path: Path) -> str:
        """Rewrite URLs in CSS to point to local files and remove Wayback artifacts."""
        # First clean any Wayback URLs
        css = WAYBACK_PATTERN.sub(lambda m: m.group(2) if m.group(2).startswith('http') else 'https://' + m.group(2), css)

        css_url_pattern = re.compile(r'url\(["\']?([^)"\']+)["\']?\)')

        def replace_url(match):
            url = match.group(1)
            # Handle absolute paths starting with /
            if url.startswith('/') and not url.startswith('//'):
                absolute_path = self.output_dir / url.lstrip('/')
                relative = os.path.relpath(absolute_path, css_path.parent)
                return f'url("{relative}")'
            clean = self.clean_url(url)
            if clean and clean in self.url_to_local:
                local_path = self.url_to_local[clean]
                relative = os.path.relpath(local_path, css_path.parent)
                return f'url("{relative}")'
            elif clean:
                return f'url("{clean}")'
            return match.group(0)

        return css_url_pattern.sub(replace_url, css)

    def extract_page_links(self, html: str, base_url: str) -> set[str]:
        """Extract links to other pages from HTML."""
        links = set()
        soup = BeautifulSoup(html, 'html.parser')

        parsed_base = urllib.parse.urlparse(base_url)
        base_for_relative = f"{parsed_base.scheme}://{parsed_base.netloc}"

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Skip non-page links
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#', 'data:')):
                continue

            # Clean wayback URLs
            clean = self.clean_url(href)
            if not clean:
                continue

            # Handle relative URLs
            if not clean.startswith(('http://', 'https://')):
                if clean.startswith('/'):
                    clean = base_for_relative + clean
                else:
                    clean = urllib.parse.urljoin(base_url, clean)

            # Only include pages from our domain
            if self.domain in clean or f'www.{self.domain}' in clean:
                # Skip asset files
                parsed = urllib.parse.urlparse(clean)
                ext = os.path.splitext(parsed.path)[1].lower()
                if ext not in ASSET_EXTENSIONS:
                    links.add(clean)

        return links

    def archive(self):
        """Main method to archive the site."""
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Get latest snapshot timestamp
        if not self.get_latest_snapshot_timestamp():
            print("Failed to find any snapshots. Exiting.")
            return

        # Get all pages from CDX
        pages = self.get_all_pages()

        # Always include the main snapshot URL
        main_page = (SNAPSHOT_TIMESTAMP, SNAPSHOT_URL)
        if main_page not in pages:
            pages.insert(0, main_page)

        if not pages:
            # At minimum, archive the main page
            pages = [(SNAPSHOT_TIMESTAMP, SNAPSHOT_URL)]

        # Convert to dict for easy lookup and updates
        pages_to_download = {url: ts for ts, url in pages}

        # Track HTML pages and all discovered URLs
        html_pages = {}  # local_path -> (html_content, original_url)
        all_asset_urls = set()
        downloaded_pages = set()
        main_page_local_path = None

        print("\nDownloading pages and discovering subpages...")

        # Use a queue-based approach to discover and download subpages
        pages_queue = list(pages_to_download.items())
        max_pages = 500  # Limit to prevent infinite crawling
        page_count = 0

        while pages_queue and page_count < max_pages:
            original_url, timestamp = pages_queue.pop(0)

            # Skip if already downloaded
            if original_url in downloaded_pages:
                continue

            # Only download pages from our domain (handle www and non-www)
            if self.domain not in original_url and f'www.{self.domain}' not in original_url:
                continue

            html = self.download_content(timestamp, original_url, is_binary=False)
            if html:
                downloaded_pages.add(original_url)
                page_count += 1

                # Strip Wayback artifacts immediately
                html = self.strip_wayback_artifacts(html)

                local_path = self.url_to_local_path(original_url)
                html_pages[local_path] = (html, original_url)
                self.url_to_local[original_url] = local_path

                # Track the main page path (handle variations)
                normalized_orig = original_url.rstrip('/').replace('http://', '').replace('https://', '').replace('www.', '')
                normalized_snap = SNAPSHOT_URL.rstrip('/').replace('http://', '').replace('https://', '').replace('www.', '')
                if normalized_orig == normalized_snap:
                    main_page_local_path = local_path

                # Extract asset URLs
                assets = self.extract_and_clean_urls(html, original_url)
                all_asset_urls.update(assets)

                # Extract links to subpages and add to queue
                subpage_links = self.extract_page_links(html, original_url)
                for link in subpage_links:
                    if link not in downloaded_pages and link not in pages_to_download:
                        pages_to_download[link] = SNAPSHOT_TIMESTAMP
                        pages_queue.append((link, SNAPSHOT_TIMESTAMP))

                print(f"  Downloaded: {original_url}")

        # Filter assets to download
        assets_to_download = []
        for url in all_asset_urls:
            if url in self.url_to_local:
                continue

            # Skip archive.org URLs
            if 'archive.org' in url:
                continue

            parsed = urllib.parse.urlparse(url)
            ext = os.path.splitext(parsed.path)[1].lower()

            # Download if it's an asset type or from our domain
            if ext in ASSET_EXTENSIONS or self.domain in url or f'www.{self.domain}' in url:
                assets_to_download.append(url)

        print(f"\nDownloading {len(assets_to_download)} assets...")

        # Download assets with thread pool
        def download_asset(url):
            content = self.download_content(self.snapshot_timestamp, url, is_binary=True)
            return (url, content)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(download_asset, url) for url in assets_to_download]

            for future in as_completed(futures):
                url, content = future.result()
                if content:
                    local_path = self.url_to_local_path(url)
                    self.url_to_local[url] = local_path

                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(content)
                    print(f"  Saved: {local_path.relative_to(self.output_dir)}")

        # Rewrite and save HTML pages
        print("\nRewriting and saving HTML pages...")
        for local_path, (html, original_url) in html_pages.items():
            rewritten_html = self.rewrite_html_links(html, local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(rewritten_html, encoding='utf-8')
            print(f"  Saved: {local_path.relative_to(self.output_dir)}")

        # Rewrite CSS files
        print("\nRewriting CSS files...")
        for local_path in self.output_dir.rglob('*.css'):
            try:
                css = local_path.read_text(encoding='utf-8')
                rewritten_css = self.rewrite_css(css, local_path)
                local_path.write_text(rewritten_css, encoding='utf-8')
                print(f"  Rewritten: {local_path.relative_to(self.output_dir)}")
            except Exception as e:
                print(f"  Error rewriting {local_path}: {e}")

        # Rewrite JS files to clean any Wayback URLs
        print("\nCleaning JS files...")
        for local_path in self.output_dir.rglob('*.js'):
            try:
                js = local_path.read_text(encoding='utf-8')
                # Clean Wayback URLs from JS
                cleaned_js = WAYBACK_PATTERN.sub(
                    lambda m: m.group(2) if m.group(2).startswith('http') else 'https://' + m.group(2),
                    js
                )
                if cleaned_js != js:
                    local_path.write_text(cleaned_js, encoding='utf-8')
                    print(f"  Cleaned: {local_path.relative_to(self.output_dir)}")
            except Exception as e:
                pass  # Binary or encoding issues, skip

        # Create index.html that redirects/links to the main page
        print("\nCreating index.html...")
        index_path = self.output_dir / 'index.html'

        if main_page_local_path and main_page_local_path != index_path:
            # Calculate relative path from index.html to main page
            relative_main = os.path.relpath(main_page_local_path, self.output_dir)

            # Create a redirect page
            index_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url={relative_main}">
    <title>Redirecting to CCSpace.org Archive</title>
</head>
<body>
    <p>Redirecting to <a href="{relative_main}">{relative_main}</a>...</p>
</body>
</html>
'''
            index_path.write_text(index_html, encoding='utf-8')
            print(f"  Created index.html -> {relative_main}")
        elif not index_path.exists():
            # If main page is already index.html or not found, check what we have
            possible_mains = [
                self.output_dir / 'index.html',
                self.output_dir / 'home.html',
                self.output_dir / 'main.html',
            ]
            for p in possible_mains:
                if p.exists() and p != index_path:
                    relative_main = os.path.relpath(p, self.output_dir)
                    index_html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url={relative_main}">
    <title>Redirecting to CCSpace.org Archive</title>
</head>
<body>
    <p>Redirecting to <a href="{relative_main}">{relative_main}</a>...</p>
</body>
</html>
'''
                    index_path.write_text(index_html, encoding='utf-8')
                    print(f"  Created index.html -> {relative_main}")
                    break

        print(f"\n{'='*50}")
        print(f"Archive complete!")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Total pages: {len(html_pages)}")
        print(f"Total assets: {len(self.url_to_local) - len(html_pages)}")
        print(f"PHP to HTML mappings: {len(self.php_to_html)}")
        print(f"{'='*50}")


def main():
    archiver = WaybackArchiver(DOMAIN, ARCHIVE_DIR)
    archiver.archive()


if __name__ == "__main__":
    main()
