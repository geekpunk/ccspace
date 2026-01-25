#!/usr/bin/env python3
"""
Script to edit the downloaded archive site.
- Copies archive folder to publish folder
- Removes PayPal donation links
- Removes "eats" header links
- Changes "Charm City Art Space is" to "Charm City Art Space was"
- Replaces donation text with closing message and link to The Undercroft
- Moves last show from current events to past events
"""

import re
import shutil
from pathlib import Path
from bs4 import BeautifulSoup

# Configuration
ARCHIVE_DIR = "archive"
PUBLISH_DIR = "publish"


def remove_paypal_links(soup: BeautifulSoup) -> int:
    """Remove PayPal donation links and buttons."""
    removed = 0

    # Remove links containing paypal in href
    for element in soup.find_all('a', href=True):
        href = element['href'].lower()
        if 'paypal' in href or 'donate' in href:
            element.decompose()
            removed += 1

    # Remove forms pointing to paypal
    for form in soup.find_all('form', action=True):
        action = form['action'].lower()
        if 'paypal' in action:
            form.decompose()
            removed += 1

    # Remove images with paypal in src or alt
    for img in soup.find_all('img'):
        src = (img.get('src') or '').lower()
        alt = (img.get('alt') or '').lower()
        if 'paypal' in src or 'paypal' in alt or 'donate' in alt:
            # Check if it's inside a link, remove the link too
            parent = img.parent
            if parent and parent.name == 'a':
                parent.decompose()
            else:
                img.decompose()
            removed += 1

    # Remove elements with paypal-related classes or ids
    for element in soup.find_all(class_=re.compile(r'paypal|donate', re.IGNORECASE)):
        element.decompose()
        removed += 1

    for element in soup.find_all(id=re.compile(r'paypal|donate', re.IGNORECASE)):
        element.decompose()
        removed += 1

    # Remove any remaining elements containing "donate" text that look like buttons/links
    for element in soup.find_all(['a', 'button', 'input']):
        text = element.get_text().lower()
        if 'donate' in text and 'paypal' in text:
            element.decompose()
            removed += 1

    return removed


def remove_eats_links(soup: BeautifulSoup) -> int:
    """Remove 'eats' and 'eat' header links."""
    removed = 0

    # Remove links with "eats" or "eat" in the text or href
    for element in soup.find_all('a'):
        text = element.get_text().lower().strip()
        href = (element.get('href') or '').lower()

        if text in ['eats', 'eat'] or 'eats' in href or '/eat' in href or 'eat.html' in href:
            element.decompose()
            removed += 1

    # Remove list items containing eats/eat links (common in navigation)
    for li in soup.find_all('li'):
        text = li.get_text().lower().strip()
        if text in ['eats', 'eat']:
            li.decompose()
            removed += 1

    # Remove nav items with eats/eat
    for nav in soup.find_all(['nav', 'header', 'div']):
        for child in nav.find_all(['a', 'span', 'li']):
            text = child.get_text().lower().strip()
            if text in ['eats', 'eat']:
                # Try to remove parent li if exists
                parent = child.parent
                if parent and parent.name == 'li':
                    parent.decompose()
                else:
                    child.decompose()
                removed += 1

    return removed


def replace_is_with_was(soup: BeautifulSoup) -> int:
    """Replace 'Charm City Art Space is' with 'Charm City Art Space was'."""
    replaced = 0

    # Find all text nodes and replace
    for text_node in soup.find_all(string=re.compile(r'Charm City Art Space is', re.IGNORECASE)):
        original = str(text_node)
        # Handle different cases
        new_text = re.sub(r'Charm City Art Space is', 'Charm City Art Space was', original, flags=re.IGNORECASE)
        if new_text != original:
            text_node.replace_with(new_text)
            replaced += original.lower().count('charm city art space is')

    return replaced


def remove_appreciation_text(soup: BeautifulSoup) -> int:
    """Remove 'Anything you can give is appreciated. We need your help to keep us going.' text."""
    removed = 0

    # Pattern to match
    pattern = r"Anything you can give is appreciated\.?\s*We need your help to keep us going\.?"

    # Find and remove text nodes containing this text
    for text_node in soup.find_all(string=re.compile(pattern, re.IGNORECASE)):
        original = str(text_node)
        new_text = re.sub(pattern, '', original, flags=re.IGNORECASE).strip()
        if new_text != original:
            if new_text:
                text_node.replace_with(new_text)
            else:
                # If nothing left, remove the parent element if it's empty
                parent = text_node.parent
                text_node.extract()
                if parent and not parent.get_text(strip=True):
                    parent.decompose()
            removed += 1

    return removed


def replace_donation_text(soup: BeautifulSoup) -> int:
    """Replace donation request text with closing message and Undercroft link."""
    replaced = 0

    # Text patterns to find (may be split across elements)
    donation_patterns = [
        r'Make a general donation to CCAS',
        r'Anything you can give is appreciated',
        r'We need your help to keep us going',
    ]

    # New replacement HTML
    new_html = '''Charm City Art Space held its last show in November of 2015. If you would like to contribute to a community arts space in Baltimore, please consider <a href="https://theundercroft.org/">The Undercroft</a>.'''

    # Find elements containing the donation text
    for element in soup.find_all(string=re.compile(r'Make a general donation to CCAS', re.IGNORECASE)):
        # Get the parent element to replace the whole section
        parent = element.parent
        if parent:
            # Check if we can find the full donation text in this section
            parent_text = parent.get_text()
            if 'Make a general donation' in parent_text:
                # Create new content
                new_tag = BeautifulSoup(new_html, 'html.parser')
                parent.clear()
                parent.append(new_tag)
                replaced += 1
                continue

    # Also try to find and replace in container elements (like divs, p tags)
    for container in soup.find_all(['div', 'p', 'section', 'aside']):
        text = container.get_text()
        if 'Make a general donation to CCAS' in text and 'keep us going' in text:
            # This container has the full donation text, replace it
            new_tag = BeautifulSoup(f'<p>{new_html}</p>', 'html.parser')
            container.clear()
            container.append(new_tag)
            replaced += 1

    return replaced


def process_html_file(file_path: Path) -> tuple[int, int, int, int, int]:
    """Process a single HTML file and return counts of removed/replaced elements."""
    try:
        html = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            html = file_path.read_text(encoding='latin-1')
        except Exception:
            return 0, 0, 0, 0, 0

    soup = BeautifulSoup(html, 'html.parser')

    paypal_removed = remove_paypal_links(soup)
    eats_removed = remove_eats_links(soup)
    is_was_replaced = replace_is_with_was(soup)
    appreciation_removed = remove_appreciation_text(soup)
    donation_replaced = replace_donation_text(soup)

    if paypal_removed > 0 or eats_removed > 0 or is_was_replaced > 0 or appreciation_removed > 0 or donation_replaced > 0:
        file_path.write_text(str(soup), encoding='utf-8')

    return paypal_removed, eats_removed, is_was_replaced, appreciation_removed, donation_replaced


def move_last_show_to_past_events(publish_path: Path) -> bool:
    """Move the last show event from current events to past events page."""

    # The exact event content to find and move
    last_show_marker = "LAST SHOW AT 1731 MARYAND AVE"
    event_date = "Wednesday, November 11th, 7pm"

    # Find current events and past events pages
    current_events_page = None
    past_events_page = None

    for file_path in publish_path.rglob('*.html'):
        try:
            html = file_path.read_text(encoding='utf-8')
            name = file_path.name.lower()

            if last_show_marker in html:
                current_events_page = file_path

            if 'past' in name and 'event' in name.replace('past', '').replace('.html', '') + html.lower()[:500]:
                past_events_page = file_path
            elif 'pastevents' in name or 'past_events' in name or 'past-events' in name:
                past_events_page = file_path
        except Exception:
            continue

    # Search more specifically for past events
    if not past_events_page:
        for file_path in publish_path.rglob('*.html'):
            name = file_path.name.lower()
            if 'past' in name:
                past_events_page = file_path
                break

    if not current_events_page:
        print("  Could not find current events page with last show")
        return False

    if not past_events_page:
        print("  Could not find past events page")
        return False

    print(f"  Current events page: {current_events_page.relative_to(publish_path)}")
    print(f"  Past events page: {past_events_page.relative_to(publish_path)}")

    # Parse current events page
    current_html = current_events_page.read_text(encoding='utf-8')
    current_soup = BeautifulSoup(current_html, 'html.parser')

    # Find just the event block - look for the smallest container with the event
    last_show_element = None

    # Find the text node with the marker
    for text_node in current_soup.find_all(string=re.compile(last_show_marker, re.IGNORECASE)):
        # Start from the text and find the event container
        # Go up to find a reasonable event container (but not too far up)
        element = text_node.parent

        # Keep track of the element and its depth
        candidate = None
        depth = 0
        max_depth = 5  # Don't go more than 5 levels up

        while element and depth < max_depth:
            # Check if this looks like an event container
            element_text = element.get_text() if element.name else ''

            # A good event container should have the date and artists but not be the whole page
            if event_date in element_text and 'Eze Jackson' in element_text:
                # Check it's not too big (shouldn't contain navigation links to other pages)
                if 'Past Events' not in element_text or element.name in ['p', 'div', 'li', 'article']:
                    # Make sure it's a block element
                    if element.name in ['div', 'p', 'li', 'article', 'section', 'tr', 'td']:
                        candidate = element
                        # If it's a small element like p or li, this is probably it
                        if element.name in ['p', 'li', 'tr']:
                            break

            element = element.parent
            depth += 1

        if candidate:
            last_show_element = candidate
            break

    if not last_show_element:
        # Try alternative: look for a div/p containing just this event
        for element in current_soup.find_all(['div', 'p', 'li', 'article']):
            text = element.get_text()
            if last_show_marker in text and 'Eze Jackson' in text:
                # Make sure this isn't the main content container
                # Check that it doesn't contain navigation or too many other events
                children_with_dates = len(element.find_all(string=re.compile(r'\d{1,2}(st|nd|rd|th),?\s*\d{1,2}')))
                if children_with_dates <= 2:  # Allow for the one event
                    last_show_element = element
                    break

    if not last_show_element:
        print("  Could not find the last show event element")
        return False

    # Extract the HTML before removing
    last_show_html = str(last_show_element)

    # Remove from current events page
    last_show_element.decompose()

    # Save the modified current events page
    current_events_page.write_text(str(current_soup), encoding='utf-8')

    # Parse past events page and add the last show at the end
    past_html = past_events_page.read_text(encoding='utf-8')
    past_soup = BeautifulSoup(past_html, 'html.parser')

    # Find existing event entries to determine where to add
    # Look for the last event entry or main content area
    content_area = None

    # Try to find where other events are listed
    for element in past_soup.find_all(['div', 'article', 'section', 'ul', 'main']):
        # Look for elements that contain event-like content
        text = element.get_text()
        if re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', text):
            if element.name in ['div', 'article', 'section', 'main']:
                content_area = element
                break

    # Fallback to main content areas
    if not content_area:
        content_area = past_soup.find('main') or \
                      past_soup.find(class_=re.compile(r'content|events', re.IGNORECASE)) or \
                      past_soup.find('article')

    if not content_area:
        # Last resort: find body
        content_area = past_soup.find('body')

    if content_area:
        # Create the last show element and append
        last_show_soup = BeautifulSoup(last_show_html, 'html.parser')

        # Add a line break for separation
        content_area.append(BeautifulSoup('<br/>', 'html.parser'))
        content_area.append(last_show_soup)

        # Save the modified past events page
        past_events_page.write_text(str(past_soup), encoding='utf-8')
        print("  Successfully moved last show to past events")
        return True

    print("  Could not find content area in past events page")
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
    print(f"  Copied successfully!")

    # Process HTML files in publish folder
    html_files = list(publish_path.rglob('*.html'))
    print(f"\nFound {len(html_files)} HTML files to process")

    total_paypal = 0
    total_eats = 0
    total_is_was = 0
    total_appreciation = 0
    total_donation = 0
    files_modified = 0

    for file_path in html_files:
        paypal, eats, is_was, appreciation, donation = process_html_file(file_path)

        if paypal > 0 or eats > 0 or is_was > 0 or appreciation > 0 or donation > 0:
            files_modified += 1
            print(f"  Modified: {file_path.relative_to(publish_path)}")
            if paypal > 0:
                print(f"    - Removed {paypal} PayPal element(s)")
            if eats > 0:
                print(f"    - Removed {eats} Eats element(s)")
            if is_was > 0:
                print(f"    - Replaced {is_was} 'is' -> 'was' occurrence(s)")
            if appreciation > 0:
                print(f"    - Removed {appreciation} appreciation text(s)")
            if donation > 0:
                print(f"    - Replaced {donation} donation text(s) with Undercroft message")

        total_paypal += paypal
        total_eats += eats
        total_is_was += is_was
        total_appreciation += appreciation
        total_donation += donation

    # Move last show from current events to past events
    print("\nMoving last show to past events...")
    last_show_moved = move_last_show_to_past_events(publish_path)

    print(f"\n{'='*50}")
    print(f"Edit complete!")
    print(f"Output directory: {publish_path.absolute()}")
    print(f"Files modified: {files_modified}")
    print(f"PayPal elements removed: {total_paypal}")
    print(f"Eats elements removed: {total_eats}")
    print(f"'is' -> 'was' replacements: {total_is_was}")
    print(f"Appreciation text removed: {total_appreciation}")
    print(f"Donation text replacements: {total_donation}")
    print(f"Last show moved to past events: {'Yes' if last_show_moved else 'No'}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
