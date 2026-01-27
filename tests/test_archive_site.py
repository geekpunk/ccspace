"""Comprehensive unit tests for archive_site.py WaybackArchiver."""

import hashlib
import os
import re
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Comment

# Allow importing from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from archive_site import WaybackArchiver, WAYBACK_PATTERN, CSS_URL_PATTERN, PHP_ACTION_PATTERN


@pytest.fixture
def archiver(tmp_path):
    """Create a WaybackArchiver instance for testing."""
    return WaybackArchiver("ccspace.org", str(tmp_path / "archive"))


# ---------------------------------------------------------------------------
# is_our_domain
# ---------------------------------------------------------------------------
class TestIsOurDomain:
    def test_http_url(self, archiver):
        assert archiver.is_our_domain("http://www.ccspace.org/page") is True

    def test_https_url(self, archiver):
        assert archiver.is_our_domain("https://ccspace.org/page") is True

    def test_subdomain(self, archiver):
        assert archiver.is_our_domain("http://sub.ccspace.org/") is True

    def test_different_domain(self, archiver):
        assert archiver.is_our_domain("http://example.com/page") is False

    def test_domain_in_path(self, archiver):
        # The implementation is simply `self.domain in url`
        assert archiver.is_our_domain("http://example.com/ccspace.org") is True

    def test_empty_string(self, archiver):
        assert archiver.is_our_domain("") is False

    def test_bare_domain(self, archiver):
        assert archiver.is_our_domain("ccspace.org") is True


# ---------------------------------------------------------------------------
# clean_url
# ---------------------------------------------------------------------------
class TestCleanUrl:
    def test_empty_string(self, archiver):
        assert archiver.clean_url("") is None

    def test_data_url(self, archiver):
        assert archiver.clean_url("data:image/png;base64,abc") is None

    def test_javascript_url(self, archiver):
        assert archiver.clean_url("javascript:void(0)") is None

    def test_mailto_url(self, archiver):
        assert archiver.clean_url("mailto:test@example.com") is None

    def test_tel_url(self, archiver):
        assert archiver.clean_url("tel:+1234567890") is None

    def test_hash_url(self, archiver):
        assert archiver.clean_url("#section") is None

    def test_about_url(self, archiver):
        assert archiver.clean_url("about:blank") is None

    def test_wayback_url_with_http(self, archiver):
        url = "https://web.archive.org/web/20170509211847/http://www.ccspace.org/page.html"
        assert archiver.clean_url(url) == "http://www.ccspace.org/page.html"

    def test_wayback_url_with_https(self, archiver):
        url = "https://web.archive.org/web/20170509211847/https://www.ccspace.org/page.html"
        assert archiver.clean_url(url) == "https://www.ccspace.org/page.html"

    def test_wayback_url_protocol_relative(self, archiver):
        url = "//web.archive.org/web/20170509211847/http://www.ccspace.org/page.html"
        assert archiver.clean_url(url) == "http://www.ccspace.org/page.html"

    def test_wayback_url_with_modifier(self, archiver):
        url = "https://web.archive.org/web/20170509211847cs_/http://www.ccspace.org/style.css"
        assert archiver.clean_url(url) == "http://www.ccspace.org/style.css"

    def test_wayback_url_with_id_modifier(self, archiver):
        url = "https://web.archive.org/web/20170509211847id_/http://www.ccspace.org/img.png"
        assert archiver.clean_url(url) == "http://www.ccspace.org/img.png"

    def test_wayback_url_non_http_original(self, archiver):
        # When group(2) does NOT start with 'http', 'https://' is prepended
        url = "https://web.archive.org/web/20170509211847/www.ccspace.org/page.html"
        assert archiver.clean_url(url) == "https://www.ccspace.org/page.html"

    def test_protocol_relative_url(self, archiver):
        url = "//cdn.example.com/script.js"
        assert archiver.clean_url(url) == "https://cdn.example.com/script.js"

    def test_regular_http_url(self, archiver):
        url = "http://www.ccspace.org/page.html"
        assert archiver.clean_url(url) == "http://www.ccspace.org/page.html"

    def test_relative_url(self, archiver):
        url = "images/logo.png"
        assert archiver.clean_url(url) == "images/logo.png"

    def test_absolute_path(self, archiver):
        url = "/images/logo.png"
        assert archiver.clean_url(url) == "/images/logo.png"


# ---------------------------------------------------------------------------
# url_to_local_path
# ---------------------------------------------------------------------------
class TestUrlToLocalPath:
    def test_simple_html_page(self, archiver):
        url = "http://www.ccspace.org/page.html"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "page.html"

    def test_root_url(self, archiver):
        url = "http://www.ccspace.org/"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "index.html"

    def test_root_url_no_trailing_slash(self, archiver):
        url = "http://www.ccspace.org"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "index.html"

    def test_directory_path(self, archiver):
        url = "http://www.ccspace.org/about/"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "about" / "index.html"

    def test_extensionless_path(self, archiver):
        url = "http://www.ccspace.org/about"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "about" / "index.html"

    def test_php_file_converted_to_html(self, archiver):
        url = "http://www.ccspace.org/page.php"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "page.html"

    def test_php_with_action_query(self, archiver):
        url = "http://www.ccspace.org/index.php?action=events"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "events.html"
        # Also check that php_to_html mapping was recorded
        assert archiver.php_to_html["/index.php?action=events"] == "events.html"

    def test_php_with_action_query_with_base_dir(self, archiver):
        url = "http://www.ccspace.org/sub/index.php?action=events"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "sub" / "events.html"
        assert archiver.php_to_html["/sub/index.php?action=events"] == "sub/events.html"

    def test_query_without_action_adds_hash(self, archiver):
        url = "http://www.ccspace.org/page.html?foo=bar"
        query_hash = hashlib.md5(b"foo=bar").hexdigest()[:8]
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / f"page_{query_hash}.html"

    def test_query_on_php_without_action(self, archiver):
        url = "http://www.ccspace.org/page.php?foo=bar"
        query_hash = hashlib.md5(b"foo=bar").hexdigest()[:8]
        result = archiver.url_to_local_path(url)
        # query hash is added first, then .php -> .html happens
        assert result == archiver.output_dir / f"page_{query_hash}.html"

    def test_nested_path(self, archiver):
        url = "http://www.ccspace.org/assets/css/style.css"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "assets" / "css" / "style.css"

    def test_action_with_special_chars(self, archiver):
        url = "http://www.ccspace.org/index.php?action=my-event"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "my-event.html"

    def test_action_with_non_word_chars(self, archiver):
        url = "http://www.ccspace.org/index.php?action=foo%20bar"
        result = archiver.url_to_local_path(url)
        # %20 gets decoded to space by parse_qs, then re.sub replaces non-\w\- with _
        assert result == archiver.output_dir / "foo_bar.html"

    def test_image_asset(self, archiver):
        url = "http://www.ccspace.org/images/logo.png"
        result = archiver.url_to_local_path(url)
        assert result == archiver.output_dir / "images" / "logo.png"


# ---------------------------------------------------------------------------
# convert_php_url_to_html_path
# ---------------------------------------------------------------------------
class TestConvertPhpUrlToHtmlPath:
    def test_empty_url(self, archiver):
        assert archiver.convert_php_url_to_html_path("") is None

    def test_none_url(self, archiver):
        assert archiver.convert_php_url_to_html_path(None) is None

    def test_php_with_action_cached(self, archiver):
        archiver.php_to_html["/index.php?action=events"] = "events.html"
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/index.php?action=events")
        assert result == "events.html"

    def test_php_with_action_not_cached(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/index.php?action=about")
        assert result == "about.html"

    def test_php_with_action_and_base_dir(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/sub/index.php?action=about")
        assert result == "sub/about.html"

    def test_plain_php_file(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/contact.php")
        assert result == "/contact.html"

    def test_php_in_subdir(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/pages/info.php")
        assert result == "/pages/info.html"

    def test_non_php_url(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/page.html")
        assert result is None

    def test_url_without_path(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/")
        assert result is None

    def test_action_with_special_chars(self, archiver):
        result = archiver.convert_php_url_to_html_path("http://www.ccspace.org/index.php?action=my-event")
        assert result == "my-event.html"


# ---------------------------------------------------------------------------
# strip_wayback_artifacts
# ---------------------------------------------------------------------------
class TestStripWaybackArtifacts:
    def test_removes_wayback_toolbar(self, archiver):
        html = (
            "<html><body>"
            "<!-- BEGIN WAYBACK TOOLBAR INSERT -->"
            "<div id='toolbar'>Toolbar content</div>"
            "<!-- END WAYBACK TOOLBAR INSERT -->"
            "<p>Real content</p></body></html>"
        )
        result = archiver.strip_wayback_artifacts(html)
        assert "Toolbar content" not in result
        assert "Real content" in result

    def test_removes_wayback_toolbar_case_insensitive(self, archiver):
        html = (
            "<!-- begin wayback toolbar insert -->"
            "<div>toolbar</div>"
            "<!-- end wayback toolbar insert -->"
            "<p>content</p>"
        )
        result = archiver.strip_wayback_artifacts(html)
        assert "toolbar" not in result
        assert "content" in result

    def test_removes_archive_org_script_external(self, archiver):
        html = '<script src="https://web.archive.org/static/js/wombat.js"></script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "wombat.js" not in result
        assert "keep" in result

    def test_removes_wombat_script_external(self, archiver):
        html = '<script src="https://example.com/wombat-handler.js"></script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "wombat-handler" not in result
        assert "keep" in result

    def test_removes_inline_wm_script(self, archiver):
        html = '<script>var __wm = {}; __wm.init();</script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "__wm" not in result
        assert "keep" in result

    def test_removes_inline_wombat_script(self, archiver):
        html = '<script>wombat.init();</script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "wombat" not in result
        assert "keep" in result

    def test_removes_inline_archive_org_script(self, archiver):
        html = '<script>var x = "archive.org";</script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert 'archive.org' not in result
        assert "keep" in result

    def test_removes_inline_wb_wombat_script(self, archiver):
        html = '<script>WB_wombat_init();</script><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "WB_wombat" not in result
        assert "keep" in result

    def test_removes_archive_org_stylesheet(self, archiver):
        html = '<link href="https://web.archive.org/static/css/toolbar.css" rel="stylesheet"><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "toolbar.css" not in result
        assert "keep" in result

    def test_removes_archive_org_style_block(self, archiver):
        html = '<style>.toolbar { background: url(https://archive.org/img.png); }</style><p>keep</p>'
        result = archiver.strip_wayback_artifacts(html)
        assert "archive.org" not in result
        assert "keep" in result

    def test_replaces_wayback_urls(self, archiver):
        html = '<img src="https://web.archive.org/web/20170509211847/http://www.ccspace.org/logo.png">'
        result = archiver.strip_wayback_artifacts(html)
        assert "http://www.ccspace.org/logo.png" in result
        assert "web.archive.org" not in result

    def test_replaces_wayback_url_non_http_original(self, archiver):
        html = '<img src="https://web.archive.org/web/20170509211847/www.ccspace.org/logo.png">'
        result = archiver.strip_wayback_artifacts(html)
        assert "https://www.ccspace.org/logo.png" in result

    def test_keeps_normal_script(self, archiver):
        html = '<script src="https://www.ccspace.org/app.js"></script>'
        result = archiver.strip_wayback_artifacts(html)
        assert "app.js" in result

    def test_keeps_normal_content(self, archiver):
        html = "<html><body><p>Hello world</p></body></html>"
        result = archiver.strip_wayback_artifacts(html)
        assert result == html


# ---------------------------------------------------------------------------
# _remove_wayback_dom_elements
# ---------------------------------------------------------------------------
class TestRemoveWaybackDomElements:
    def _make_soup(self, html):
        return BeautifulSoup(html, "html.parser")

    def test_removes_wm_id_elements(self, archiver):
        soup = self._make_soup('<div id="wm-toolbar">toolbar</div><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        assert soup.find(id="wm-toolbar") is None
        assert soup.find("p").text == "keep"

    def test_removes_playback_id_elements(self, archiver):
        soup = self._make_soup('<div id="playback">player</div><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        assert soup.find(id="playback") is None

    def test_removes_donato_id_elements(self, archiver):
        soup = self._make_soup('<div id="donato">donate</div><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        assert soup.find(id="donato") is None

    def test_removes_wm_class_elements(self, archiver):
        soup = self._make_soup('<div class="wm-header">header</div><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        assert soup.find(class_="wm-header") is None

    def test_removes_wb_class_elements(self, archiver):
        soup = self._make_soup('<div class="wb-overlay">overlay</div><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        assert soup.find(class_="wb-overlay") is None

    def test_removes_archive_org_scripts(self, archiver):
        soup = self._make_soup('<script src="https://web.archive.org/js/main.js"></script><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        scripts = soup.find_all("script")
        assert len(scripts) == 0

    def test_removes_inline_wombat_scripts(self, archiver):
        soup = self._make_soup('<script>wombat.init()</script><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        scripts = soup.find_all("script")
        assert len(scripts) == 0

    def test_removes_inline_wm_scripts(self, archiver):
        soup = self._make_soup('<script>__wm.init()</script><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        scripts = soup.find_all("script")
        assert len(scripts) == 0

    def test_keeps_normal_scripts(self, archiver):
        soup = self._make_soup('<script src="https://www.ccspace.org/app.js"></script>')
        archiver._remove_wayback_dom_elements(soup)
        scripts = soup.find_all("script")
        assert len(scripts) == 1

    def test_removes_archive_org_links(self, archiver):
        soup = self._make_soup('<link href="https://web.archive.org/css/style.css" rel="stylesheet"><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        links = soup.find_all("link")
        assert len(links) == 0

    def test_keeps_normal_links(self, archiver):
        soup = self._make_soup('<link href="https://www.ccspace.org/style.css" rel="stylesheet">')
        archiver._remove_wayback_dom_elements(soup)
        links = soup.find_all("link")
        assert len(links) == 1

    def test_removes_html_comments(self, archiver):
        soup = self._make_soup('<!-- A comment --><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        assert len(comments) == 0
        assert soup.find("p").text == "keep"

    def test_removes_multiple_comments(self, archiver):
        soup = self._make_soup('<!-- first --><!-- second --><p>keep</p>')
        archiver._remove_wayback_dom_elements(soup)
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        assert len(comments) == 0


# ---------------------------------------------------------------------------
# extract_urls_and_links
# ---------------------------------------------------------------------------
class TestExtractUrlsAndLinks:
    def test_extract_anchor_links(self, archiver):
        html = '<a href="http://www.ccspace.org/about">About</a>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/about" in assets
        assert "http://www.ccspace.org/about" in page_links

    def test_extract_external_anchor(self, archiver):
        html = '<a href="http://www.example.com/page">External</a>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.example.com/page" in assets
        assert "http://www.example.com/page" not in page_links

    def test_extract_img_src(self, archiver):
        html = '<img src="http://www.ccspace.org/images/logo.png">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/images/logo.png" in assets

    def test_extract_script_src(self, archiver):
        html = '<script src="http://www.ccspace.org/js/app.js"></script>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/js/app.js" in assets

    def test_extract_link_href(self, archiver):
        html = '<link href="http://www.ccspace.org/css/style.css" rel="stylesheet">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/css/style.css" in assets

    def test_extract_relative_url(self, archiver):
        html = '<img src="images/logo.png">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/page/")
        assert "http://www.ccspace.org/page/images/logo.png" in assets

    def test_extract_absolute_path_url(self, archiver):
        html = '<img src="/images/logo.png">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/page/")
        assert "http://www.ccspace.org/images/logo.png" in assets

    def test_skips_data_urls(self, archiver):
        html = '<img src="data:image/png;base64,abc">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert len(assets) == 0

    def test_page_link_not_asset_extension(self, archiver):
        # An anchor linking to .css is an asset extension, NOT a page link
        html = '<a href="http://www.ccspace.org/style.css">CSS</a>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/style.css" in assets
        assert "http://www.ccspace.org/style.css" not in page_links

    def test_extract_srcset(self, archiver):
        html = '<img srcset="http://www.ccspace.org/img1.png 1x, http://www.ccspace.org/img2.png 2x">'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/img1.png" in assets
        assert "http://www.ccspace.org/img2.png" in assets

    def test_extract_css_url_in_style_tag(self, archiver):
        html = '<style>body { background: url("http://www.ccspace.org/bg.png"); }</style>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/bg.png" in assets

    def test_extract_css_url_in_style_attr(self, archiver):
        html = '<div style="background: url(http://www.ccspace.org/bg.png);">content</div>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/bg.png" in assets

    def test_removes_wayback_elements_before_extracting(self, archiver):
        html = (
            '<div id="wm-toolbar"><a href="http://archive.org/about">Archive</a></div>'
            '<a href="http://www.ccspace.org/real">Real</a>'
        )
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/real" in assets
        # archive.org link from toolbar should not be present (element decomposed)
        assert not any("archive.org/about" in u for u in assets)

    def test_extract_video_poster(self, archiver):
        html = '<video poster="http://www.ccspace.org/poster.jpg"></video>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/poster.jpg" in assets

    def test_extract_form_action(self, archiver):
        html = '<form action="http://www.ccspace.org/submit"></form>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/submit" in assets

    def test_empty_href_ignored(self, archiver):
        html = '<a href="">link</a>'
        assets, page_links = archiver.extract_urls_and_links(html, "http://www.ccspace.org/")
        # empty string -> clean_url returns None
        assert len(assets) == 0


# ---------------------------------------------------------------------------
# _fix_protocol_and_local_links
# ---------------------------------------------------------------------------
class TestFixProtocolAndLocalLinks:
    def test_double_slash_html_file(self, archiver):
        # //file.html -> file.html (local)
        assert archiver._fix_protocol_and_local_links("//file.html") == "file.html"

    def test_double_slash_html_with_query(self, archiver):
        assert archiver._fix_protocol_and_local_links("//file.html?foo=bar") == "file.html?foo=bar"

    def test_double_slash_html_with_hash(self, archiver):
        assert archiver._fix_protocol_and_local_links("//file.html#section") == "file.html#section"

    def test_double_slash_external_domain(self, archiver):
        # //cdn.example.com/script.js has a dot in first segment -> external
        assert archiver._fix_protocol_and_local_links("//cdn.example.com/script.js") == "https://cdn.example.com/script.js"

    def test_double_slash_local_path_no_dot(self, archiver):
        # //somepath/page has no dot in first segment -> local
        assert archiver._fix_protocol_and_local_links("//somepath/page") == "somepath/page"

    def test_https_malformed_html(self, archiver):
        # https://file.html -> file.html
        assert archiver._fix_protocol_and_local_links("https://file.html") == "file.html"

    def test_http_malformed_html(self, archiver):
        assert archiver._fix_protocol_and_local_links("http://page.html") == "page.html"

    def test_https_malformed_html_with_query(self, archiver):
        assert archiver._fix_protocol_and_local_links("https://page.html?a=1") == "page.html?a=1"

    def test_https_malformed_html_with_hash(self, archiver):
        assert archiver._fix_protocol_and_local_links("https://page.html#sec") == "page.html#sec"

    def test_normal_https_url_preserved(self, archiver):
        url = "https://www.example.com/page"
        assert archiver._fix_protocol_and_local_links(url) == url

    def test_normal_value_passthrough(self, archiver):
        assert archiver._fix_protocol_and_local_links("images/logo.png") == "images/logo.png"

    def test_normal_absolute_path(self, archiver):
        assert archiver._fix_protocol_and_local_links("/images/logo.png") == "/images/logo.png"


# ---------------------------------------------------------------------------
# _convert_php_link
# ---------------------------------------------------------------------------
class TestConvertPhpLink:
    def test_index_php_action(self, archiver):
        assert archiver._convert_php_link("index.php?action=events") == "events.html"

    def test_index_php_action_with_dir(self, archiver):
        result = archiver._convert_php_link("sub/index.php?action=events")
        assert result == "sub/events.html"

    def test_plain_php_file(self, archiver):
        assert archiver._convert_php_link("contact.php") == "contact.html"

    def test_php_with_path(self, archiver):
        assert archiver._convert_php_link("pages/info.php") == "pages/info.html"

    def test_php_with_non_action_query(self, archiver):
        href = "page.php?foo=bar"
        query_hash = hashlib.md5(b"foo=bar").hexdigest()[:8]
        result = archiver._convert_php_link(href)
        assert result == f"page_{query_hash}.html"

    def test_non_php_passthrough(self, archiver):
        assert archiver._convert_php_link("page.html") == "page.html"

    def test_action_with_special_chars(self, archiver):
        result = archiver._convert_php_link("index.php?action=my-event")
        assert result == "my-event.html"

    def test_action_with_spaces_encoded(self, archiver):
        # The PHP_ACTION_PATTERN captures the action value from the raw href
        result = archiver._convert_php_link("index.php?action=foo+bar")
        # + is not in [\w\-], so it becomes _
        assert result == "foo_bar.html"

    def test_current_dir_base(self, archiver):
        # When the base_dir is '.' (i.e., dirname of 'index.php' is ''), return action.html
        result = archiver._convert_php_link("index.php?action=test")
        assert result == "test.html"

    def test_dot_dir_base(self, archiver):
        # dirname of "./index.php" is "."
        result = archiver._convert_php_link("./index.php?action=test")
        assert result == "test.html"


# ---------------------------------------------------------------------------
# resolve_url
# ---------------------------------------------------------------------------
class TestResolveUrl:
    def test_absolute_http_url(self, archiver):
        result = archiver.resolve_url("http://www.ccspace.org/page.html", "http://www.ccspace.org/")
        assert result == "http://www.ccspace.org/page.html"

    def test_absolute_https_url(self, archiver):
        result = archiver.resolve_url("https://www.ccspace.org/page.html", "http://www.ccspace.org/")
        assert result == "https://www.ccspace.org/page.html"

    def test_absolute_path(self, archiver):
        result = archiver.resolve_url("/images/logo.png", "http://www.ccspace.org/page/sub/")
        assert result == "http://www.ccspace.org/images/logo.png"

    def test_relative_path(self, archiver):
        result = archiver.resolve_url("images/logo.png", "http://www.ccspace.org/page/")
        assert result == "http://www.ccspace.org/page/images/logo.png"

    def test_none_for_invalid_urls(self, archiver):
        assert archiver.resolve_url("", "http://www.ccspace.org/") is None
        assert archiver.resolve_url("#section", "http://www.ccspace.org/") is None
        assert archiver.resolve_url("javascript:void(0)", "http://www.ccspace.org/") is None
        assert archiver.resolve_url("data:image/png;base64,abc", "http://www.ccspace.org/") is None

    def test_wayback_url_cleaned(self, archiver):
        url = "https://web.archive.org/web/20170509211847/http://www.ccspace.org/img.png"
        result = archiver.resolve_url(url, "http://www.ccspace.org/")
        assert result == "http://www.ccspace.org/img.png"

    def test_protocol_relative_url(self, archiver):
        result = archiver.resolve_url("//cdn.example.com/lib.js", "http://www.ccspace.org/")
        assert result == "https://cdn.example.com/lib.js"

    def test_relative_with_parent_dir(self, archiver):
        result = archiver.resolve_url("../images/logo.png", "http://www.ccspace.org/page/sub/")
        assert result == "http://www.ccspace.org/page/images/logo.png"


# ---------------------------------------------------------------------------
# rewrite_html_links
# ---------------------------------------------------------------------------
class TestRewriteHtmlLinks:
    def test_rewrites_known_url_to_relative(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/images/logo.png"
        local = archive_dir / "images" / "logo.png"
        archiver.url_to_local[url] = local

        html = f'<img src="{url}">'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert 'src="images/logo.png"' in result

    def test_rewrites_anchor_to_relative(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/about.html"
        local = archive_dir / "about.html"
        archiver.url_to_local[url] = local

        html = f'<a href="{url}">About</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert 'href="about.html"' in result

    def test_our_domain_php_converted(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        archiver.php_to_html["/index.php?action=events"] = "events.html"

        html = '<a href="http://www.ccspace.org/index.php?action=events">Events</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "events.html" in result

    def test_external_url_kept(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        html = '<a href="http://www.example.com/page">External</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "http://www.example.com/page" in result

    def test_removes_wayback_dom_elements(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        html = '<div id="wm-toolbar">toolbar</div><p>content</p>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "wm-toolbar" not in result
        assert "content" in result

    def test_rewrites_srcset(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url1 = "http://www.ccspace.org/img1.png"
        url2 = "http://www.ccspace.org/img2.png"
        archiver.url_to_local[url1] = archive_dir / "img1.png"
        archiver.url_to_local[url2] = archive_dir / "img2.png"

        html = f'<img srcset="{url1} 1x, {url2} 2x">'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "img1.png 1x" in result
        assert "img2.png 2x" in result

    def test_converts_php_links_in_href(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        html = '<a href="contact.php">Contact</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "contact.html" in result
        assert ".php" not in result

    def test_converts_absolute_path_to_relative(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        html = '<img src="/images/logo.png">'
        page_path = archive_dir / "sub" / "page.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert os.path.join("..", "images", "logo.png") in result

    def test_rewrites_inline_style_css_url(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/bg.png"
        archiver.url_to_local[url] = archive_dir / "bg.png"

        html = f'<div style="background: url({url});">content</div>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert 'url("bg.png")' in result

    def test_rewrites_style_tag_css_url(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/bg.png"
        archiver.url_to_local[url] = archive_dir / "bg.png"

        html = f'<style>body {{ background: url({url}); }}</style>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert 'url("bg.png")' in result

    def test_our_domain_no_php_uses_path(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        # An unknown our-domain URL not in url_to_local and not PHP:
        # First pass sets href to parsed path "/unknown/page".
        # Second pass converts absolute "/unknown/page" to relative from page_path.
        html = '<a href="http://www.ccspace.org/unknown/page">Link</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        # The absolute path /unknown/page is converted to relative from archive_dir
        expected_rel = os.path.relpath(str(archive_dir / "unknown/page"), str(archive_dir))
        assert expected_rel in result


# ---------------------------------------------------------------------------
# rewrite_css
# ---------------------------------------------------------------------------
class TestRewriteCss:
    def test_replaces_wayback_urls_in_css(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        css = 'body { background: url("https://web.archive.org/web/20170509211847/http://www.ccspace.org/bg.png"); }'
        css_path = archive_dir / "style.css"
        result = archiver.rewrite_css(css, css_path)
        assert "web.archive.org" not in result

    def test_rewrites_known_url(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/images/bg.png"
        archiver.url_to_local[url] = archive_dir / "images" / "bg.png"

        css = f'body {{ background: url("{url}"); }}'
        css_path = archive_dir / "style.css"
        result = archiver.rewrite_css(css, css_path)
        assert 'url("images/bg.png")' in result

    def test_rewrites_absolute_path_url(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        css = 'body { background: url("/images/bg.png"); }'
        css_path = archive_dir / "css" / "style.css"
        result = archiver.rewrite_css(css, css_path)
        assert os.path.join("..", "images", "bg.png") in result

    def test_unknown_url_cleaned(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        css = 'body { background: url("http://www.example.com/bg.png"); }'
        css_path = archive_dir / "style.css"
        result = archiver.rewrite_css(css, css_path)
        assert 'url("http://www.example.com/bg.png")' in result

    def test_data_url_preserved(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        css = 'body { background: url("data:image/png;base64,abc"); }'
        css_path = archive_dir / "style.css"
        result = archiver.rewrite_css(css, css_path)
        # data: URLs return None from clean_url, so match.group(0) is returned unchanged
        assert "data:image/png;base64,abc" in result

    def test_multiple_urls(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url1 = "http://www.ccspace.org/img1.png"
        url2 = "http://www.ccspace.org/img2.png"
        archiver.url_to_local[url1] = archive_dir / "img1.png"
        archiver.url_to_local[url2] = archive_dir / "img2.png"

        css = f'.a {{ background: url("{url1}"); }} .b {{ background: url("{url2}"); }}'
        css_path = archive_dir / "style.css"
        result = archiver.rewrite_css(css, css_path)
        assert 'url("img1.png")' in result
        assert 'url("img2.png")' in result


# ---------------------------------------------------------------------------
# _create_redirect_html
# ---------------------------------------------------------------------------
class TestCreateRedirectHtml:
    def test_contains_meta_refresh(self, archiver):
        result = archiver._create_redirect_html("www/index.html")
        assert '<meta http-equiv="refresh" content="0; url=www/index.html">' in result

    def test_contains_link(self, archiver):
        result = archiver._create_redirect_html("www/index.html")
        assert '<a href="www/index.html">www/index.html</a>' in result

    def test_contains_doctype(self, archiver):
        result = archiver._create_redirect_html("target.html")
        assert "<!DOCTYPE html>" in result

    def test_contains_title(self, archiver):
        result = archiver._create_redirect_html("target.html")
        assert "<title>Redirecting to CCSpace.org Archive</title>" in result

    def test_contains_charset(self, archiver):
        result = archiver._create_redirect_html("target.html")
        assert '<meta charset="UTF-8">' in result

    def test_target_in_body_text(self, archiver):
        result = archiver._create_redirect_html("sub/page.html")
        assert "Redirecting to" in result
        assert "sub/page.html" in result


# ---------------------------------------------------------------------------
# Regex pattern tests
# ---------------------------------------------------------------------------
class TestPatterns:
    def test_wayback_pattern_matches_standard(self):
        url = "https://web.archive.org/web/20170509211847/http://www.ccspace.org/page.html"
        m = WAYBACK_PATTERN.match(url)
        assert m is not None
        assert m.group(1) == "20170509211847"
        assert m.group(2) == "http://www.ccspace.org/page.html"

    def test_wayback_pattern_matches_modifier(self):
        url = "https://web.archive.org/web/20170509211847cs_/http://www.ccspace.org/style.css"
        m = WAYBACK_PATTERN.match(url)
        assert m is not None
        assert m.group(2) == "http://www.ccspace.org/style.css"

    def test_wayback_pattern_matches_id_modifier(self):
        url = "https://web.archive.org/web/20170509211847id_/http://example.com/img.png"
        m = WAYBACK_PATTERN.match(url)
        assert m is not None
        assert m.group(2) == "http://example.com/img.png"

    def test_wayback_pattern_protocol_relative(self):
        url = "//web.archive.org/web/20170509211847/http://example.com/page"
        m = WAYBACK_PATTERN.match(url)
        assert m is not None

    def test_php_action_pattern(self):
        m = PHP_ACTION_PATTERN.search("index.php?action=events")
        assert m is not None
        assert m.group(1) == "events"

    def test_php_action_pattern_with_extra_params(self):
        m = PHP_ACTION_PATTERN.search("index.php?action=events&page=2")
        assert m is not None
        assert m.group(1) == "events"

    def test_css_url_pattern(self):
        m = CSS_URL_PATTERN.search('url("image.png")')
        assert m is not None
        assert m.group(1) == "image.png"

    def test_css_url_pattern_single_quotes(self):
        m = CSS_URL_PATTERN.search("url('image.png')")
        assert m is not None
        assert m.group(1) == "image.png"

    def test_css_url_pattern_no_quotes(self):
        m = CSS_URL_PATTERN.search("url(image.png)")
        assert m is not None
        assert m.group(1) == "image.png"


# ---------------------------------------------------------------------------
# Integration-style tests (combining methods, no network)
# ---------------------------------------------------------------------------
class TestIntegration:
    def test_clean_then_resolve_wayback_url(self, archiver):
        wb_url = "https://web.archive.org/web/20170509211847/http://www.ccspace.org/img.png"
        result = archiver.resolve_url(wb_url, "http://www.ccspace.org/")
        assert result == "http://www.ccspace.org/img.png"

    def test_url_to_local_then_rewrite(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        url = "http://www.ccspace.org/style.css"
        local = archiver.url_to_local_path(url)
        archiver.url_to_local[url] = local

        html = f'<link href="{url}" rel="stylesheet">'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "style.css" in result
        assert url not in result

    def test_strip_artifacts_then_extract(self, archiver):
        html = (
            '<!-- BEGIN WAYBACK TOOLBAR INSERT --><div>toolbar</div><!-- END WAYBACK TOOLBAR INSERT -->'
            '<a href="http://www.ccspace.org/about">About</a>'
            '<img src="https://web.archive.org/web/20170509211847/http://www.ccspace.org/logo.png">'
        )
        cleaned = archiver.strip_wayback_artifacts(html)
        assets, page_links = archiver.extract_urls_and_links(cleaned, "http://www.ccspace.org/")
        assert "http://www.ccspace.org/about" in page_links
        assert "http://www.ccspace.org/logo.png" in assets

    def test_full_php_conversion_pipeline(self, archiver, tmp_path):
        archive_dir = tmp_path / "archive"
        # Step 1: url_to_local_path registers php_to_html mapping
        url = "http://www.ccspace.org/index.php?action=events"
        local = archiver.url_to_local_path(url)
        assert local == archive_dir / "events.html"

        # Step 2: convert_php_url_to_html_path uses the mapping
        html_path = archiver.convert_php_url_to_html_path(url)
        assert html_path == "events.html"

        # Step 3: rewrite_html_links converts PHP links
        archiver.url_to_local[url] = local
        html = f'<a href="{url}">Events</a>'
        page_path = archive_dir / "index.html"
        result = archiver.rewrite_html_links(html, page_path)
        assert "events.html" in result
