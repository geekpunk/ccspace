"""Comprehensive unit tests for edit_archive.py."""

import sys
import os
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

# Allow importing edit_archive from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import edit_archive


# ---------------------------------------------------------------------------
# TestRemovePaypalLinks
# ---------------------------------------------------------------------------

class TestRemovePaypalLinks:
    """Tests for remove_paypal_links()."""

    def test_removes_paypal_link(self, make_soup):
        soup = make_soup('<a href="https://www.paypal.com/donate">Donate</a>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_donate_link(self, make_soup):
        soup = make_soup('<a href="https://example.com/donate">Give</a>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_paypal_form(self, make_soup):
        soup = make_soup(
            '<form action="https://www.paypal.com/cgi-bin/webscr" method="post">'
            '<input type="hidden" name="cmd" value="_s-xclick"/>'
            '</form>'
        )
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('form') is None

    def test_removes_paypal_image(self, make_soup):
        soup = make_soup('<img src="https://www.paypalobjects.com/btn.gif" alt="button"/>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('img') is None

    def test_removes_paypal_image_with_parent_link(self, make_soup):
        soup = make_soup(
            '<div><a href="somewhere"><img src="https://www.paypalobjects.com/btn.gif" alt="button"/></a></div>'
        )
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        # The parent <a> should be decomposed too
        assert soup.find('a') is None

    def test_removes_donate_alt_image(self, make_soup):
        soup = make_soup('<img src="images/btn.gif" alt="PayPal Donate"/>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('img') is None

    def test_removes_element_with_paypal_class(self, make_soup):
        soup = make_soup('<div class="paypal-button">content</div>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('div', class_='paypal-button') is None

    def test_removes_element_with_donate_id(self, make_soup):
        soup = make_soup('<div id="donate-section">content</div>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find(id='donate-section') is None

    def test_removes_button_with_donate_and_paypal_text(self, make_soup):
        soup = make_soup('<button>Donate via PayPal</button>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('button') is None

    def test_does_not_remove_unrelated_link(self, make_soup):
        soup = make_soup('<a href="https://example.com">Example</a>')
        count = edit_archive.remove_paypal_links(soup)
        assert count == 0
        assert soup.find('a') is not None

    def test_returns_zero_for_no_paypal_content(self, make_soup):
        soup = make_soup('<p>Just a normal paragraph.</p>')
        count = edit_archive.remove_paypal_links(soup)
        assert count == 0

    def test_multiple_paypal_elements(self, make_soup):
        soup = make_soup(
            '<a href="https://paypal.com/pay">Pay</a>'
            '<form action="https://paypal.com/form"><input type="submit"/></form>'
            '<a href="https://example.com/donate">Donate</a>'
        )
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 3

    def test_case_insensitive_href_match(self, make_soup):
        soup = make_soup('<a href="https://www.PAYPAL.COM/donate">Donate</a>')
        count = edit_archive.remove_paypal_links(soup)
        assert count >= 1
        assert soup.find('a') is None


# ---------------------------------------------------------------------------
# TestRemoveEatsLinks
# ---------------------------------------------------------------------------

class TestRemoveEatsLinks:
    """Tests for remove_eats_links()."""

    def test_removes_eat_text_link(self, make_soup):
        soup = make_soup('<a href="eat.html">eat</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_eats_text_link(self, make_soup):
        soup = make_soup('<a href="eats.html">eats</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_parent_li(self, make_soup):
        soup = make_soup('<ul><li><a href="eat.html">eat</a></li><li><a href="index.html">home</a></li></ul>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        # The li containing eat should be gone
        items = soup.find_all('li')
        assert len(items) == 1
        assert 'home' in items[0].get_text()

    def test_removes_link_with_eats_in_href(self, make_soup):
        soup = make_soup('<a href="/eats/page">Food</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_link_with_eat_in_href(self, make_soup):
        soup = make_soup('<a href="/eat">Food</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_removes_link_with_eat_html_in_href(self, make_soup):
        soup = make_soup('<a href="eat.html">Food Info</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None

    def test_does_not_remove_unrelated_link(self, make_soup):
        soup = make_soup('<a href="events.html">events</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count == 0
        assert soup.find('a') is not None

    def test_cleans_bare_li_with_eat_text(self, make_soup):
        soup = make_soup('<ul><li>eat</li></ul>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('li') is None

    def test_cleans_bare_span_with_eats_text(self, make_soup):
        soup = make_soup('<span>eats</span>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('span') is None

    def test_returns_zero_for_no_eat_content(self, make_soup):
        soup = make_soup('<p>Nothing about food here.</p>')
        count = edit_archive.remove_eats_links(soup)
        assert count == 0

    def test_case_insensitive_text_match(self, make_soup):
        soup = make_soup('<a href="eat.html">Eat</a>')
        count = edit_archive.remove_eats_links(soup)
        assert count >= 1
        assert soup.find('a') is None


# ---------------------------------------------------------------------------
# TestReplaceTextPatterns
# ---------------------------------------------------------------------------

class TestReplaceTextPatterns:
    """Tests for replace_text_patterns()."""

    def test_replaces_is_with_was(self, make_soup):
        soup = make_soup('<p>Charm City Art Space is a great venue.</p>')
        is_was, _, _ = edit_archive.replace_text_patterns(soup)
        assert is_was == 1
        assert 'Charm City Art Space was' in soup.get_text()
        assert 'Charm City Art Space is' not in soup.get_text()

    def test_replaces_multiple_is_occurrences(self, make_soup):
        soup = make_soup(
            '<div>'
            '<p>Charm City Art Space is open.</p>'
            '<p>Charm City Art Space is welcoming.</p>'
            '</div>'
        )
        is_was, _, _ = edit_archive.replace_text_patterns(soup)
        assert is_was == 2
        text = soup.get_text()
        assert text.count('was') >= 2
        assert 'Charm City Art Space is' not in text

    def test_removes_appreciation_text(self, make_soup):
        soup = make_soup('<p>Anything you can give is appreciated. We need your help to keep us going.</p>')
        _, appreciation, _ = edit_archive.replace_text_patterns(soup)
        assert appreciation == 1
        assert 'Anything you can give' not in soup.get_text()

    def test_removes_appreciation_text_with_period(self, make_soup):
        soup = make_soup('<p>Anything you can give is appreciated. We need your help to keep us going</p>')
        _, appreciation, _ = edit_archive.replace_text_patterns(soup)
        assert appreciation == 1

    def test_removes_empty_parent_after_appreciation(self, make_soup):
        soup = make_soup('<div><p>Anything you can give is appreciated. We need your help to keep us going.</p></div>')
        _, appreciation, _ = edit_archive.replace_text_patterns(soup)
        assert appreciation == 1
        # The <p> should be gone because it became empty
        assert soup.find('p') is None

    def test_replaces_donation_text_with_undercroft(self, make_soup):
        soup = make_soup('<p>Make a general donation to CCAS</p>')
        _, _, donation = edit_archive.replace_text_patterns(soup)
        assert donation >= 1
        assert 'The Undercroft' in soup.get_text()
        assert soup.find('a', href='https://theundercroft.org/') is not None

    def test_replaces_donation_container_with_keep_us_going(self, make_soup):
        soup = make_soup(
            '<div>Make a general donation to CCAS and help keep us going.</div>'
        )
        _, _, donation = edit_archive.replace_text_patterns(soup)
        assert donation >= 1
        assert 'The Undercroft' in soup.get_text()

    def test_no_changes_on_unrelated_text(self, make_soup):
        soup = make_soup('<p>This is a normal paragraph with no keywords.</p>')
        is_was, appreciation, donation = edit_archive.replace_text_patterns(soup)
        assert is_was == 0
        assert appreciation == 0
        assert donation == 0

    def test_returns_tuple(self, make_soup):
        soup = make_soup('<p>Hello</p>')
        result = edit_archive.replace_text_patterns(soup)
        assert isinstance(result, tuple)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# TestInjectHamburgerMenu
# ---------------------------------------------------------------------------

class TestInjectHamburgerMenu:
    """Tests for inject_hamburger_menu()."""

    def test_injects_hamburger_button_into_header(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="header"><img src="header.jpg"/></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '</body></html>'
        )
        result = edit_archive.inject_hamburger_menu(soup)
        assert result is True
        btn = soup.find(id='hamburger-btn')
        assert btn is not None
        assert btn.name == 'button'
        assert btn['aria-label'] == 'Menu'
        assert btn['type'] == 'button'

    def test_hamburger_placed_inside_header(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="header"><img src="header.jpg"/></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '</body></html>'
        )
        edit_archive.inject_hamburger_menu(soup)
        header = soup.find(id='header')
        btn = soup.find(id='hamburger-btn')
        # Button should be a child of header
        assert btn.parent == header

    def test_hamburger_placed_before_menu_without_header(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '</body></html>'
        )
        result = edit_archive.inject_hamburger_menu(soup)
        assert result is True
        btn = soup.find(id='hamburger-btn')
        assert btn is not None
        # Should be a sibling before #menu
        menu = soup.find(id='menu')
        assert btn.find_next_sibling(id='menu') == menu

    def test_injects_toggle_script(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="header"></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '</body></html>'
        )
        edit_archive.inject_hamburger_menu(soup)
        script = soup.find('script')
        assert script is not None
        assert 'hamburger-btn' in script.string
        assert 'menu-open' in script.string

    def test_script_appended_to_body(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="header"></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '</body></html>'
        )
        edit_archive.inject_hamburger_menu(soup)
        body = soup.find('body')
        script = body.find('script')
        assert script is not None

    def test_returns_false_without_menu(self, make_soup):
        soup = make_soup('<html><body><div id="header"></div></body></html>')
        result = edit_archive.inject_hamburger_menu(soup)
        assert result is False

    def test_returns_false_if_already_injected(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="header"></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '<button id="hamburger-btn">X</button>'
            '</body></html>'
        )
        result = edit_archive.inject_hamburger_menu(soup)
        assert result is False

    def test_script_appended_to_soup_without_body(self, make_soup):
        soup = make_soup(
            '<div id="header"></div>'
            '<div id="menu"><a href="index.html">home</a></div>'
        )
        result = edit_archive.inject_hamburger_menu(soup)
        assert result is True
        script = soup.find('script')
        assert script is not None


# ---------------------------------------------------------------------------
# TestInjectMobileBanner
# ---------------------------------------------------------------------------

class TestInjectMobileBanner:
    """Tests for inject_mobile_banner()."""

    def test_injects_banner_after_menu(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '<div id="content"></div>'
            '</body></html>'
        )
        result = edit_archive.inject_mobile_banner(soup)
        assert result is True
        banner = soup.find(id='mobile-banner')
        assert banner is not None
        assert banner.name == 'div'

    def test_banner_contains_undercroft_link(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"></div>'
            '</body></html>'
        )
        edit_archive.inject_mobile_banner(soup)
        banner = soup.find(id='mobile-banner')
        assert 'The Undercroft' in banner.get_text()
        link = banner.find('a', href='https://theundercroft.org/')
        assert link is not None

    def test_banner_placed_after_menu(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"><a href="index.html">home</a></div>'
            '<div id="content">Main</div>'
            '</body></html>'
        )
        edit_archive.inject_mobile_banner(soup)
        menu = soup.find(id='menu')
        # The next sibling element should be the banner
        next_sib = menu.find_next_sibling()
        assert next_sib is not None
        assert next_sib.get('id') == 'mobile-banner'

    def test_returns_false_without_menu(self, make_soup):
        soup = make_soup('<html><body><div id="content"></div></body></html>')
        result = edit_archive.inject_mobile_banner(soup)
        assert result is False

    def test_returns_false_if_already_injected(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"></div>'
            '<div id="mobile-banner">Already here</div>'
            '</body></html>'
        )
        result = edit_archive.inject_mobile_banner(soup)
        assert result is False

    def test_banner_contains_closing_message(self, make_soup):
        soup = make_soup(
            '<html><body>'
            '<div id="menu"></div>'
            '</body></html>'
        )
        edit_archive.inject_mobile_banner(soup)
        banner = soup.find(id='mobile-banner')
        text = banner.get_text()
        assert 'last show in November of 2015' in text


# ---------------------------------------------------------------------------
# TestInjectResponsive
# ---------------------------------------------------------------------------

class TestInjectResponsive:
    """Tests for inject_responsive()."""

    def test_injects_viewport_meta(self, make_soup):
        soup = make_soup('<html><head><title>Test</title></head><body></body></html>')
        result = edit_archive.inject_responsive(soup, 'responsive.css')
        assert result is True
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        assert viewport is not None
        assert 'width=device-width' in viewport['content']

    def test_injects_css_link(self, make_soup):
        soup = make_soup('<html><head><title>Test</title></head><body></body></html>')
        edit_archive.inject_responsive(soup, 'css/responsive.css')
        link = soup.find('link', href='css/responsive.css')
        assert link is not None
        assert link['rel'] == 'stylesheet'

    def test_creates_head_if_missing(self, make_soup):
        soup = make_soup('<html><body><p>Hello</p></body></html>')
        result = edit_archive.inject_responsive(soup, 'responsive.css')
        assert result is True
        head = soup.find('head')
        assert head is not None
        assert soup.find('meta', attrs={'name': 'viewport'}) is not None

    def test_returns_false_without_html_or_head(self, make_soup):
        soup = make_soup('<p>Just text</p>')
        result = edit_archive.inject_responsive(soup, 'responsive.css')
        assert result is False

    def test_does_not_duplicate_viewport(self, make_soup):
        soup = make_soup(
            '<html><head>'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
            '</head><body></body></html>'
        )
        edit_archive.inject_responsive(soup, 'responsive.css')
        viewports = soup.find_all('meta', attrs={'name': 'viewport'})
        assert len(viewports) == 1

    def test_does_not_duplicate_css_link(self, make_soup):
        soup = make_soup(
            '<html><head>'
            '<link rel="stylesheet" href="responsive.css"/>'
            '</head><body></body></html>'
        )
        edit_archive.inject_responsive(soup, 'responsive.css')
        links = soup.find_all('link', href=lambda h: h and 'responsive.css' in h)
        assert len(links) == 1

    def test_returns_false_when_both_already_present(self, make_soup):
        soup = make_soup(
            '<html><head>'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0"/>'
            '<link rel="stylesheet" href="responsive.css"/>'
            '</head><body></body></html>'
        )
        result = edit_archive.inject_responsive(soup, 'responsive.css')
        assert result is False

    def test_viewport_inserted_first_in_head(self, make_soup):
        soup = make_soup('<html><head><title>Page</title></head><body></body></html>')
        edit_archive.inject_responsive(soup, 'responsive.css')
        head = soup.find('head')
        first_child = list(head.children)[0]
        assert first_child.name == 'meta'
        assert first_child.get('name') == 'viewport'


# ---------------------------------------------------------------------------
# TestProcessHtmlFile
# ---------------------------------------------------------------------------

class TestProcessHtmlFile:
    """Tests for process_html_file()."""

    def test_processes_full_page(self, tmp_path, sample_page_html):
        html_file = tmp_path / 'test.html'
        html_file.write_text(sample_page_html, encoding='utf-8')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        assert isinstance(counts, dict)
        assert counts['paypal'] >= 1
        assert counts['eats'] >= 1
        assert counts['is_was'] >= 1
        assert counts['responsive'] == 1
        assert counts['hamburger'] == 1
        assert counts['banner'] == 1

    def test_writes_modified_file(self, tmp_path, sample_page_html):
        html_file = tmp_path / 'test.html'
        html_file.write_text(sample_page_html, encoding='utf-8')

        edit_archive.process_html_file(html_file, tmp_path)

        result = html_file.read_text(encoding='utf-8')
        assert 'paypal' not in result.lower() or 'paypalobjects' not in result.lower()
        assert 'Charm City Art Space was' in result

    def test_does_not_write_if_no_changes(self, tmp_path):
        # A minimal page with nothing to change and no head/html tags for responsive
        html_file = tmp_path / 'plain.html'
        content = '<p>Nothing to change here.</p>'
        html_file.write_text(content, encoding='utf-8')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        assert all(v == 0 for v in counts.values())
        # File should not have been rewritten
        assert html_file.read_text(encoding='utf-8') == content

    def test_returns_dict_with_expected_keys(self, tmp_path):
        html_file = tmp_path / 'test.html'
        html_file.write_text('<html><head></head><body></body></html>', encoding='utf-8')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        expected_keys = {'paypal', 'eats', 'is_was', 'appreciation', 'donation', 'responsive', 'hamburger', 'banner'}
        assert set(counts.keys()) == expected_keys

    def test_handles_latin1_encoding(self, tmp_path):
        html_file = tmp_path / 'latin.html'
        content = '<html><head></head><body><div id="menu"><a href="index.html">home</a></div><p>caf\xe9</p></body></html>'
        html_file.write_text(content, encoding='latin-1')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        # Should not crash, and responsive should be injected
        assert counts['responsive'] == 1

    def test_responsive_css_path_relative(self, tmp_path):
        subdir = tmp_path / 'sub'
        subdir.mkdir()
        html_file = subdir / 'page.html'
        html_file.write_text(
            '<html><head></head><body><div id="menu"><a href="index.html">home</a></div></body></html>',
            encoding='utf-8'
        )

        edit_archive.process_html_file(html_file, tmp_path)

        result = html_file.read_text(encoding='utf-8')
        soup = BeautifulSoup(result, 'html.parser')
        link = soup.find('link', href=lambda h: h and 'responsive.css' in h)
        assert link is not None
        # Path should go up one level from subdir to tmp_path
        assert link['href'] == os.path.relpath(tmp_path / 'responsive.css', subdir)


# ---------------------------------------------------------------------------
# TestCreateResponsiveCss
# ---------------------------------------------------------------------------

class TestCreateResponsiveCss:
    """Tests for create_responsive_css()."""

    def test_creates_css_file(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css_file = tmp_path / 'responsive.css'
        assert css_file.exists()

    def test_css_contains_hamburger_rules(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css = (tmp_path / 'responsive.css').read_text(encoding='utf-8')
        assert '#hamburger-btn' in css

    def test_css_contains_mobile_banner_rules(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css = (tmp_path / 'responsive.css').read_text(encoding='utf-8')
        assert '#mobile-banner' in css

    def test_css_contains_media_query(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css = (tmp_path / 'responsive.css').read_text(encoding='utf-8')
        assert '@media screen and (max-width: 768px)' in css

    def test_css_contains_small_phone_query(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css = (tmp_path / 'responsive.css').read_text(encoding='utf-8')
        assert '@media screen and (max-width: 480px)' in css

    def test_css_hides_hamburger_on_desktop(self, tmp_path):
        edit_archive.create_responsive_css(tmp_path)
        css = (tmp_path / 'responsive.css').read_text(encoding='utf-8')
        # The first rule outside media queries should hide the hamburger
        assert 'display: none;' in css

    def test_overwrites_existing_file(self, tmp_path):
        css_file = tmp_path / 'responsive.css'
        css_file.write_text('old content', encoding='utf-8')
        edit_archive.create_responsive_css(tmp_path)
        css = css_file.read_text(encoding='utf-8')
        assert 'old content' not in css
        assert '#hamburger-btn' in css


# ---------------------------------------------------------------------------
# TestMoveLastShowToPastEvents
# ---------------------------------------------------------------------------

class TestMoveLastShowToPastEvents:
    """Tests for move_last_show_to_past_events()."""

    @pytest.fixture
    def events_html(self):
        return '''<html><body>
<div class="text">
<p><b>Wednesday, November 11th 7pm</b><br>
LAST SHOW AT 1731 MARYAND AVE<br>
Eze Jackson<br>
Dylijens<br>
Cornelius the Third<br>
Kahlil Ali<br>
Jumbled</p>
<p><a href="past.html">Past Events</a></p>
</div>
</body></html>'''

    @pytest.fixture
    def past_html(self):
        return '''<html><body>
<div class="text">
<p>
1. <b>Friday, January 5th</b><br>Some Band</p>
<p>
2. <b>Saturday, January 6th</b><br>Another Band</p>
<p>NOTICE: DUE TO UNFORSEEN circumstances...</p>
</div>
</body></html>'''

    def test_moves_show_from_events_to_past(self, tmp_path, events_html, past_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')

        result = edit_archive.move_last_show_to_past_events(tmp_path)

        assert result is True
        events_content = (tmp_path / 'events.html').read_text(encoding='utf-8')
        assert 'LAST SHOW AT 1731 MARYAND AVE' not in events_content

    def test_adds_show_to_past_with_correct_number(self, tmp_path, events_html, past_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')

        edit_archive.move_last_show_to_past_events(tmp_path)

        past_content = (tmp_path / 'past.html').read_text(encoding='utf-8')
        assert 'LAST SHOW AT 1731 MARYAND AVE' in past_content
        # Should be show #3 since last was #2
        assert '3.' in past_content

    def test_returns_false_if_events_missing(self, tmp_path, past_html):
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')
        result = edit_archive.move_last_show_to_past_events(tmp_path)
        assert result is False

    def test_returns_false_if_past_missing(self, tmp_path, events_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        result = edit_archive.move_last_show_to_past_events(tmp_path)
        assert result is False

    def test_returns_false_if_marker_not_in_events(self, tmp_path, past_html):
        (tmp_path / 'events.html').write_text('<html><body><p>No shows</p></body></html>', encoding='utf-8')
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')
        result = edit_archive.move_last_show_to_past_events(tmp_path)
        assert result is False

    def test_returns_true_if_already_on_past_page(self, tmp_path, events_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        past_with_show = '''<html><body>
<div class="text">
<p>1. <b>Friday, January 5th</b><br>Some Band</p>
<p>3. <b>Wednesday, November 11th</b><br>LAST SHOW AT 1731 MARYAND AVE<br>Jumbled</p>
</div>
</body></html>'''
        (tmp_path / 'past.html').write_text(past_with_show, encoding='utf-8')

        result = edit_archive.move_last_show_to_past_events(tmp_path)
        assert result is True

    def test_inserts_before_notice(self, tmp_path, events_html, past_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')

        edit_archive.move_last_show_to_past_events(tmp_path)

        past_content = (tmp_path / 'past.html').read_text(encoding='utf-8')
        show_pos = past_content.find('LAST SHOW AT 1731 MARYAND AVE')
        notice_pos = past_content.find('NOTICE: DUE TO UNFORSEEN')
        assert show_pos < notice_pos

    def test_fallback_insert_without_notice(self, tmp_path, events_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        past_no_notice = '''<html><body>
<div class="text">
<p>
1. <b>Friday, January 5th</b><br>Some Band</p>
<p>
2. <b>Saturday, January 6th</b><br>Another Band</p>
</div>
</body></html>'''
        (tmp_path / 'past.html').write_text(past_no_notice, encoding='utf-8')

        result = edit_archive.move_last_show_to_past_events(tmp_path)
        assert result is True

        past_content = (tmp_path / 'past.html').read_text(encoding='utf-8')
        assert 'LAST SHOW AT 1731 MARYAND AVE' in past_content
        assert '3.' in past_content

    def test_show_entry_includes_all_bands(self, tmp_path, events_html, past_html):
        (tmp_path / 'events.html').write_text(events_html, encoding='utf-8')
        (tmp_path / 'past.html').write_text(past_html, encoding='utf-8')

        edit_archive.move_last_show_to_past_events(tmp_path)

        past_content = (tmp_path / 'past.html').read_text(encoding='utf-8')
        for band in ['Eze Jackson', 'Dylijens', 'Cornelius the Third', 'Kahlil Ali', 'Jumbled']:
            assert band in past_content


# ---------------------------------------------------------------------------
# TestLoadConfig
# ---------------------------------------------------------------------------

class TestLoadConfig:
    """Tests for load_config()."""

    def test_loads_yaml_config(self, tmp_path, monkeypatch):
        config_file = tmp_path / 'config.yaml'
        config_file.write_text('archive_dir: my_archive\npublish_dir: my_docs\n', encoding='utf-8')
        monkeypatch.setattr(edit_archive, 'CONFIG_FILE', str(config_file))

        result = edit_archive.load_config()

        assert result == {'archive_dir': 'my_archive', 'publish_dir': 'my_docs'}

    def test_returns_empty_dict_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(edit_archive, 'CONFIG_FILE', str(tmp_path / 'nonexistent.yaml'))
        result = edit_archive.load_config()
        assert result == {}

    def test_returns_dict(self, tmp_path, monkeypatch):
        config_file = tmp_path / 'config.yaml'
        config_file.write_text('key: value\n', encoding='utf-8')
        monkeypatch.setattr(edit_archive, 'CONFIG_FILE', str(config_file))

        result = edit_archive.load_config()
        assert isinstance(result, dict)

    def test_handles_empty_yaml(self, tmp_path, monkeypatch):
        config_file = tmp_path / 'config.yaml'
        config_file.write_text('', encoding='utf-8')
        monkeypatch.setattr(edit_archive, 'CONFIG_FILE', str(config_file))

        result = edit_archive.load_config()
        # yaml.safe_load returns None for empty file; load_config returns that
        # The function does not guard against None, so it returns None
        assert result is None or result == {}


# ---------------------------------------------------------------------------
# Integration-style test with sample_page_html fixture
# ---------------------------------------------------------------------------

class TestSamplePageIntegration:
    """Integration tests using the sample_page_html fixture."""

    def test_full_pipeline_on_sample_page(self, tmp_path, sample_page_html):
        """Run the full process_html_file pipeline on sample_page_html."""
        html_file = tmp_path / 'index.html'
        html_file.write_text(sample_page_html, encoding='utf-8')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        result_html = html_file.read_text(encoding='utf-8')
        soup = BeautifulSoup(result_html, 'html.parser')

        # PayPal form should be gone
        assert soup.find('form', action=lambda a: a and 'paypal' in a.lower()) is None

        # Eat link should be gone
        eat_links = [a for a in soup.find_all('a') if a.get_text().strip().lower() in ('eat', 'eats')]
        assert len(eat_links) == 0

        # "is" should be replaced with "was"
        assert 'Charm City Art Space was' in soup.get_text()

        # Viewport meta should be present
        assert soup.find('meta', attrs={'name': 'viewport'}) is not None

        # Hamburger button should be present
        assert soup.find(id='hamburger-btn') is not None

        # Mobile banner should be present
        assert soup.find(id='mobile-banner') is not None

        # CSS link should be present
        assert soup.find('link', href=lambda h: h and 'responsive.css' in h) is not None

    def test_sample_page_counts_are_positive(self, tmp_path, sample_page_html):
        html_file = tmp_path / 'index.html'
        html_file.write_text(sample_page_html, encoding='utf-8')

        counts = edit_archive.process_html_file(html_file, tmp_path)

        assert counts['paypal'] > 0
        assert counts['eats'] > 0
        assert counts['is_was'] > 0
        assert counts['responsive'] == 1
        assert counts['hamburger'] == 1
        assert counts['banner'] == 1

# ---------------------------------------------------------------------------
# TestAddContentDivs
# ---------------------------------------------------------------------------

class TestAddContentDivs:
    """Tests for add_content_divs()."""

    def test_adds_content_div_to_index(self, tmp_path):
        """Test adding content div to index.html after blurb paragraph."""
        index_file = tmp_path / 'index.html'
        index_file.write_text(
            '<html><body>'
            '<div class="blurb">from all over to showcase their work in our fine city.<br/>\n</div>'
            '<p>Other content</p>'
            '</body></html>'
        )

        result = edit_archive.add_content_divs(tmp_path)

        assert result['index'] is True
        html = index_file.read_text()
        assert '<div id="newContent"></div>' in html
        assert html.index('<div id="newContent"></div>') > html.index('showcase their work')

    def test_adds_content_div_to_events(self, tmp_path):
        """Test adding content div to events.html after blurb paragraph."""
        events_file = tmp_path / 'events.html'
        events_file.write_text(
            '<html><body>'
            '<div class="blurb">CCAS is dedicated to promoting independent arts of all mediums in Baltimore City.  Click the link below to find out about  our  gallery schedule.</div>'
            '<p>Other content</p>'
            '</body></html>'
        )

        result = edit_archive.add_content_divs(tmp_path)

        assert result['events'] is True
        html = events_file.read_text()
        assert '<div id="newContent"></div>' in html
        assert html.index('<div id="newContent"></div>') > html.index('gallery schedule')

    def test_does_not_add_duplicate_content_div(self, tmp_path):
        """Test that newContent div is not added if already present at the location."""
        index_file = tmp_path / 'index.html'
        index_file.write_text(
            '<html><body>'
            '<div class="blurb">from all over to showcase their work in our fine city.<br/>\n</div>\n'
            '<div id="newContent"></div>'
            '<p>Other content</p>'
            '</body></html>'
        )

        result = edit_archive.add_content_divs(tmp_path)

        assert result['index'] is False
        html = index_file.read_text()
        # Should only have one occurrence of the div at this location
        assert html.count('<div id="newContent"></div>') == 1

    def test_handles_missing_files(self, tmp_path):
        """Test that function handles missing files gracefully."""
        result = edit_archive.add_content_divs(tmp_path)

        assert result['index'] is False
        assert result['events'] is False

    def test_handles_missing_markers(self, tmp_path):
        """Test that function handles missing marker text gracefully."""
        index_file = tmp_path / 'index.html'
        index_file.write_text('<html><body><p>No blurb paragraph here</p></body></html>')

        result = edit_archive.add_content_divs(tmp_path)

        assert result['index'] is False
        html = index_file.read_text()
        assert '<div id="newContent"></div>' not in html
