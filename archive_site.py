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

# CSS url() pattern
CSS_URL_PATTERN = re.compile(r'url\(["\']?([^)"\']+)["\']?\)')


class WaybackArchiver:
    def __init__(self, domain: str, output_dir: str):
        self.domain = domain
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.downloaded_urls = set()
        self.url_to_local = {}
        self.php_to_html = {}
        self.snapshot_timestamp = SNAPSHOT_TIMESTAMP

    def is_our_domain(self, url: str) -> bool:
        """Check if URL belongs to our domain."""
        return self.domain in url

    def resolve_url(self, url: str, base_url: str) -> str | None:
        """Clean a URL, resolve relative paths, and return absolute URL or None."""
        clean = self.clean_url(url)
        if not clean:
            return None
        if not clean.startswith(('http://', 'https://')):
            parsed_base = urllib.parse.urlparse(base_url)
            if clean.startswith('/'):
                clean = f"{parsed_base.scheme}://{parsed_base.netloc}{clean}"
            else:
                clean = urllib.parse.urljoin(base_url, clean)
        return clean

    def _query_cdx(self, search_url: str, date_from: str, date_to: str) -> dict[str, str]:
        """Query CDX API and return {url: closest_timestamp} for HTML pages."""
        response = self.session.get(
            WAYBACK_CDX_API,
            params={
                'url': search_url,
                'output': 'json',
                'filter': 'statuscode:200',
                'fl': 'original,timestamp,mimetype',
                'from': date_from,
                'to': date_to,
            }
        )

        url_data = {}
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1:
                for row in data[1:]:
                    original_url, timestamp = row[0], row[1]
                    mimetype = row[2] if len(row) > 2 else ''

                    if 'text/html' in mimetype or not mimetype:
                        if original_url not in url_data or \
                           abs(int(timestamp) - int(SNAPSHOT_TIMESTAMP)) < abs(int(url_data[original_url]) - int(SNAPSHOT_TIMESTAMP)):
                            url_data[original_url] = timestamp
        return url_data

    def get_all_pages(self) -> list[tuple[str, str]]:
        """Get all archived pages for the domain around the snapshot timestamp."""
        print("Fetching list of all archived pages...")

        search_urls = [f'www.{self.domain}/*', f'{self.domain}/*']
        url_data = {}

        # Try exact date first, then broader range
        for date_from, date_to in [(SNAPSHOT_TIMESTAMP[:8], SNAPSHOT_TIMESTAMP[:8]), ('2017', '2017')]:
            for search_url in search_urls:
                url_data.update(self._query_cdx(search_url, date_from, date_to))
            if url_data:
                break
            print("No pages found for exact date, searching broader range...")

        pages = [(ts, url) for url, ts in url_data.items()]
        print(f"Found {len(pages)} pages")
        return pages

    def download_content(self, timestamp: str, original_url: str, is_binary: bool = False) -> bytes | str | None:
        """Download content from the Wayback Machine using id_ modifier."""
        cache_key = f"{timestamp}/{original_url}"
        if cache_key in self.downloaded_urls:
            return None

        wayback_url = f"https://web.archive.org/web/{timestamp}id_/{original_url}"
        try:
            response = self.session.get(wayback_url, timeout=30)
            if response.status_code == 200:
                self.downloaded_urls.add(cache_key)
                return response.content if is_binary else response.text
            else:
                print(f"  HTTP {response.status_code} for {original_url}")
        except Exception as e:
            print(f"  Error downloading {original_url}: {e}")
        return None

    def clean_url(self, url: str) -> str | None:
        """Extract original URL from a potentially Wayback-wrapped URL."""
        if not url or url.startswith(('data:', 'javascript:', 'mailto:', 'tel:', '#', 'about:')):
            return None

        match = WAYBACK_PATTERN.match(url)
        if match:
            original = match.group(2)
            return original if original.startswith('http') else 'https://' + original

        if url.startswith('//'):
            return 'https:' + url

        return url

    def url_to_local_path(self, url: str) -> Path:
        """Convert a URL to a local file path. PHP files are converted to HTML."""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')

        if not path:
            path = 'index.html'
        elif path.endswith('/'):
            path += 'index.html'
        elif '.' not in path.split('/')[-1]:
            path += '/index.html'

        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'action' in query_params and path.endswith('.php'):
                action_clean = re.sub(r'[^\w\-]', '_', query_params['action'][0])
                base_dir = os.path.dirname(path)
                path = f"{base_dir}/{action_clean}.html" if base_dir else f"{action_clean}.html"
                self.php_to_html[f"{parsed.path}?action={query_params['action'][0]}"] = path
            else:
                query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
                base, ext = os.path.splitext(path)
                path = f"{base}_{query_hash}{ext}"

        if path.endswith('.php'):
            path = path[:-4] + '.html'

        return self.output_dir / path

    def convert_php_url_to_html_path(self, url: str) -> str | None:
        """Convert a PHP URL to its local HTML path."""
        if not url:
            return None

        parsed = urllib.parse.urlparse(url)
        if parsed.query and parsed.path.endswith('.php'):
            query_params = urllib.parse.parse_qs(parsed.query)
            if 'action' in query_params:
                action = query_params['action'][0]
                php_pattern = f"{parsed.path}?action={action}"
                if php_pattern in self.php_to_html:
                    return self.php_to_html[php_pattern]
                action_clean = re.sub(r'[^\w\-]', '_', action)
                base_dir = os.path.dirname(parsed.path.strip('/'))
                return f"{base_dir}/{action_clean}.html" if base_dir else f"{action_clean}.html"

        if parsed.path.endswith('.php'):
            return parsed.path[:-4] + '.html'

        return None

    def strip_wayback_artifacts(self, html: str) -> str:
        """Remove all Wayback Machine artifacts from HTML using regex."""
        # Remove Wayback toolbar
        html = re.sub(
            r'<!--\s*BEGIN WAYBACK TOOLBAR INSERT\s*-->.*?<!--\s*END WAYBACK TOOLBAR INSERT\s*-->',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove archive.org scripts (external and inline)
        html = re.sub(
            r'<script[^>]*src=["\'][^"\']*(?:archive\.org|wombat)[^"\']*["\'][^>]*>.*?</script>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )
        html = re.sub(
            r'<script[^>]*>(?:(?!</script>).)*(?:__wm\.|wombat|archive\.org|WB_wombat)(?:(?!</script>).)*</script>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove archive.org stylesheets and style blocks
        html = re.sub(
            r'<link[^>]*href=["\'][^"\']*archive\.org[^"\']*["\'][^>]*>',
            '', html, flags=re.IGNORECASE
        )
        html = re.sub(
            r'<style[^>]*>(?:(?!</style>).)*archive\.org(?:(?!</style>).)*</style>',
            '', html, flags=re.DOTALL | re.IGNORECASE
        )
        # Replace Wayback URLs with originals
        html = WAYBACK_PATTERN.sub(
            lambda m: m.group(2) if m.group(2).startswith('http') else 'https://' + m.group(2),
            html
        )
        return html

    def _remove_wayback_dom_elements(self, soup: BeautifulSoup) -> None:
        """Remove Wayback Machine injected DOM elements."""
        for element in soup.find_all(id=re.compile(r'^wm-|^playback|^donato', re.IGNORECASE)):
            element.decompose()
        for element in soup.find_all(class_=re.compile(r'^wm-|^wb-', re.IGNORECASE)):
            element.decompose()
        for script in soup.find_all('script'):
            src = script.get('src', '')
            content = script.string or ''
            if any(s in src or s in content for s in ['archive.org', 'wombat', '__wm']):
                script.decompose()
        for link in soup.find_all('link'):
            if 'archive.org' in link.get('href', ''):
                link.decompose()
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    def extract_urls_and_links(self, html: str, base_url: str) -> tuple[set[str], set[str]]:
        """Extract asset URLs and page links from HTML. Returns (assets, page_links)."""
        assets = set()
        page_links = set()
        soup = BeautifulSoup(html, 'html.parser')
        self._remove_wayback_dom_elements(soup)

        url_attrs = [
            ('a', 'href'), ('link', 'href'), ('script', 'src'),
            ('img', 'src'), ('source', 'src'), ('video', 'src'),
            ('video', 'poster'), ('audio', 'src'), ('iframe', 'src'),
            ('object', 'data'), ('embed', 'src'), ('form', 'action'),
        ]

        for tag, attr in url_attrs:
            for element in soup.find_all(tag):
                value = element.get(attr)
                if not value:
                    continue
                resolved = self.resolve_url(value, base_url)
                if resolved:
                    assets.add(resolved)
                    # Also track as page link if it's on our domain and not an asset
                    if tag == 'a' and self.is_our_domain(resolved):
                        ext = os.path.splitext(urllib.parse.urlparse(resolved).path)[1].lower()
                        if ext not in ASSET_EXTENSIONS:
                            page_links.add(resolved)

        # Handle srcset
        for element in soup.find_all(srcset=True):
            for part in element['srcset'].split(','):
                url = part.strip().split()[0] if part.strip() else ''
                if url:
                    resolved = self.resolve_url(url, base_url)
                    if resolved:
                        assets.add(resolved)

        # Extract from CSS
        for style in soup.find_all('style'):
            if style.string:
                for match in CSS_URL_PATTERN.finditer(style.string):
                    resolved = self.resolve_url(match.group(1), base_url)
                    if resolved:
                        assets.add(resolved)

        for element in soup.find_all(style=True):
            for match in CSS_URL_PATTERN.finditer(element['style']):
                resolved = self.resolve_url(match.group(1), base_url)
                if resolved:
                    assets.add(resolved)

        return assets, page_links

    def _fix_protocol_and_local_links(self, attr_value: str) -> str:
        """Fix // prefixed links and https://file.html malformed links."""
        if attr_value.startswith('//'):
            remainder = attr_value[2:]
            if remainder.endswith('.html') or '.html?' in remainder or '.html#' in remainder:
                return remainder
            if '.' not in remainder.split('/')[0]:
                return remainder
            return 'https:' + attr_value

        if re.match(r'^https?://[^/]+\.html(\?|#|$)', attr_value):
            return attr_value.split('://')[-1]

        return attr_value

    def _convert_php_link(self, href: str) -> str:
        """Convert PHP links to HTML equivalents."""
        match = PHP_ACTION_PATTERN.search(href)
        if match:
            action_clean = re.sub(r'[^\w\-]', '_', match.group(1))
            php_path = href.split('?')[0]
            base_dir = os.path.dirname(php_path)
            return f"{base_dir}/{action_clean}.html" if base_dir and base_dir != '.' else f"{action_clean}.html"
        if href.endswith('.php'):
            return href[:-4] + '.html'
        if '.php?' in href:
            php_part, query_part = href.split('?', 1)
            query_hash = hashlib.md5(query_part.encode()).hexdigest()[:8]
            return f"{php_part[:-4]}_{query_hash}.html"
        return href

    def _to_relative(self, target_path, from_dir) -> str:
        """Convert a path to relative from a directory."""
        return os.path.relpath(target_path, from_dir)

    def _make_css_replacer(self, page_path: Path):
        """Create a CSS url() replacer function for a given page context."""
        def replace_css_url(match):
            url = match.group(1)
            if url.startswith('/') and not url.startswith('//'):
                return f'url("{self._to_relative(self.output_dir / url.lstrip("/"), page_path.parent)}")'
            clean = self.clean_url(url)
            if clean and clean in self.url_to_local:
                return f'url("{self._to_relative(self.url_to_local[clean], page_path.parent)}")'
            if clean:
                return f'url("{clean}")'
            return match.group(0)
        return replace_css_url

    def rewrite_html_links(self, html: str, page_path: Path) -> str:
        """Rewrite all URLs in HTML to point to local files."""
        soup = BeautifulSoup(html, 'html.parser')
        self._remove_wayback_dom_elements(soup)

        # Rewrite known URL attributes
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

                clean = self.clean_url(value)
                if not clean:
                    continue

                if clean in self.url_to_local:
                    element[attr] = self._to_relative(self.url_to_local[clean], page_path.parent)
                elif self.is_our_domain(clean):
                    html_path = self.convert_php_url_to_html_path(clean)
                    if html_path:
                        element[attr] = self._to_relative(self.output_dir / html_path.lstrip('/'), page_path.parent)
                    else:
                        element[attr] = urllib.parse.urlparse(clean).path or '/'
                else:
                    element[attr] = clean

        # Rewrite srcset
        for element in soup.find_all(srcset=True):
            new_parts = []
            for part in element['srcset'].split(','):
                parts = part.strip().split()
                if parts:
                    clean = self.clean_url(parts[0])
                    if clean and clean in self.url_to_local:
                        parts[0] = self._to_relative(self.url_to_local[clean], page_path.parent)
                    elif clean:
                        parts[0] = clean
                    new_parts.append(' '.join(parts))
            element['srcset'] = ', '.join(new_parts)

        # Fix PHP links, // links, and malformed local links in all href/src attributes
        for attr_name in ['href', 'src', 'action']:
            for element in soup.find_all(**{attr_name: True}):
                value = element[attr_name]

                # Skip already-processed external URLs
                if value.startswith(('http://', 'https://', '#', 'mailto:', 'tel:', 'javascript:')):
                    element[attr_name] = self._fix_protocol_and_local_links(value)
                    continue

                # Convert PHP links
                if '.php' in value:
                    element[attr_name] = self._convert_php_link(value)
                    value = element[attr_name]

                # Convert absolute paths to relative
                if value.startswith('/') and not value.startswith('//'):
                    element[attr_name] = self._to_relative(self.output_dir / value.lstrip('/'), page_path.parent)
                elif value.startswith('//'):
                    element[attr_name] = self._fix_protocol_and_local_links(value)

        # Handle srcset absolute paths
        for element in soup.find_all(srcset=True):
            new_parts = []
            for part in element['srcset'].split(','):
                parts = part.strip().split()
                if parts:
                    if parts[0].startswith('//'):
                        parts[0] = self._fix_protocol_and_local_links(parts[0])
                    elif parts[0].startswith('/'):
                        parts[0] = self._to_relative(self.output_dir / parts[0].lstrip('/'), page_path.parent)
                new_parts.append(' '.join(parts))
            element['srcset'] = ', '.join(new_parts)

        # Clean CSS url() in inline styles and style tags
        replacer = self._make_css_replacer(page_path)
        for element in soup.find_all(style=True):
            element['style'] = CSS_URL_PATTERN.sub(replacer, element['style'])
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                style_tag.string = CSS_URL_PATTERN.sub(replacer, style_tag.string)

        return str(soup)

    def rewrite_css(self, css: str, css_path: Path) -> str:
        """Rewrite URLs in CSS to point to local files and remove Wayback artifacts."""
        css = WAYBACK_PATTERN.sub(
            lambda m: m.group(2) if m.group(2).startswith('http') else 'https://' + m.group(2),
            css
        )
        return CSS_URL_PATTERN.sub(self._make_css_replacer(css_path), css)

    def _create_redirect_html(self, target_path: str) -> str:
        """Create a redirect HTML page."""
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url={target_path}">
    <title>Redirecting to CCSpace.org Archive</title>
</head>
<body>
    <p>Redirecting to <a href="{target_path}">{target_path}</a>...</p>
</body>
</html>
'''

    def archive(self):
        """Main method to archive the site."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"Using snapshot from {SNAPSHOT_TIMESTAMP}")
        print(f"Snapshot URL: https://web.archive.org/web/{SNAPSHOT_TIMESTAMP}/{SNAPSHOT_URL}")

        pages = self.get_all_pages()

        # Always include the main snapshot URL
        main_page = (SNAPSHOT_TIMESTAMP, SNAPSHOT_URL)
        if main_page not in pages:
            pages.insert(0, main_page)

        pages_to_download = {url: ts for ts, url in pages}
        html_pages = {}
        all_asset_urls = set()
        downloaded_pages = set()
        main_page_local_path = None

        print("\nDownloading pages and discovering subpages...")
        pages_queue = list(pages_to_download.items())
        max_pages = 500
        page_count = 0

        normalized_snap = SNAPSHOT_URL.rstrip('/').replace('http://', '').replace('https://', '').replace('www.', '')

        while pages_queue and page_count < max_pages:
            original_url, timestamp = pages_queue.pop(0)

            if original_url in downloaded_pages or not self.is_our_domain(original_url):
                continue

            html = self.download_content(timestamp, original_url, is_binary=False)
            if not html:
                continue

            downloaded_pages.add(original_url)
            page_count += 1
            html = self.strip_wayback_artifacts(html)

            local_path = self.url_to_local_path(original_url)
            html_pages[local_path] = (html, original_url)
            self.url_to_local[original_url] = local_path

            normalized_orig = original_url.rstrip('/').replace('http://', '').replace('https://', '').replace('www.', '')
            if normalized_orig == normalized_snap:
                main_page_local_path = local_path

            assets, subpage_links = self.extract_urls_and_links(html, original_url)
            all_asset_urls.update(assets)

            for link in subpage_links:
                if link not in downloaded_pages and link not in pages_to_download:
                    pages_to_download[link] = SNAPSHOT_TIMESTAMP
                    pages_queue.append((link, SNAPSHOT_TIMESTAMP))

            print(f"  Downloaded: {original_url}")

        # Filter and download assets
        assets_to_download = [
            url for url in all_asset_urls
            if url not in self.url_to_local
            and 'archive.org' not in url
            and (os.path.splitext(urllib.parse.urlparse(url).path)[1].lower() in ASSET_EXTENSIONS
                 or self.is_our_domain(url))
        ]

        print(f"\nDownloading {len(assets_to_download)} assets...")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.download_content, self.snapshot_timestamp, url, True): url
                for url in assets_to_download
            }
            for future in as_completed(futures):
                url = futures[future]
                content = future.result()
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
                rewritten = self.rewrite_css(css, local_path)
                local_path.write_text(rewritten, encoding='utf-8')
                print(f"  Rewritten: {local_path.relative_to(self.output_dir)}")
            except Exception as e:
                print(f"  Error rewriting {local_path}: {e}")

        # Clean JS files
        print("\nCleaning JS files...")
        for local_path in self.output_dir.rglob('*.js'):
            try:
                js = local_path.read_text(encoding='utf-8')
                cleaned = WAYBACK_PATTERN.sub(
                    lambda m: m.group(2) if m.group(2).startswith('http') else 'https://' + m.group(2), js
                )
                if cleaned != js:
                    local_path.write_text(cleaned, encoding='utf-8')
                    print(f"  Cleaned: {local_path.relative_to(self.output_dir)}")
            except Exception:
                pass

        # Create index.html redirect
        print("\nCreating index.html...")
        index_path = self.output_dir / 'index.html'
        if main_page_local_path and main_page_local_path != index_path:
            relative_main = os.path.relpath(main_page_local_path, self.output_dir)
            index_path.write_text(self._create_redirect_html(relative_main), encoding='utf-8')
            print(f"  Created index.html -> {relative_main}")
        elif not index_path.exists():
            for name in ['home.html', 'main.html']:
                p = self.output_dir / name
                if p.exists():
                    relative_main = os.path.relpath(p, self.output_dir)
                    index_path.write_text(self._create_redirect_html(relative_main), encoding='utf-8')
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
