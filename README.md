# CCSpace.org Archive

This project downloads and archives the Charm City Art Space website from the Wayback Machine, creating a static site that can be hosted anywhere.

## Scripts

### archive_site.py

Downloads the May 2017 snapshot of ccspace.org from the Wayback Machine and creates a static archive.

**Features:**
- Downloads all pages and discovers subpages by crawling links
- Downloads all assets (CSS, JS, images, fonts, etc.)
- Removes all Wayback Machine artifacts and injected content
- Converts PHP files to HTML
- Rewrites `index.php?action=X` links to `X.html`
- Converts absolute paths to relative paths
- Fixes protocol-relative URLs (`//` links)
- Creates an `index.html` that redirects to the main page

**Output:** `archive/` folder

### edit_archive.py

Copies the archive to a publish folder and makes editorial changes appropriate for a memorial/historical site.

**Features:**
- Copies `archive/` to `docs/` (preserves original)
- Removes PayPal donation links and buttons
- Removes "eat" and "eats" header links
- Changes "Charm City Art Space is" to "Charm City Art Space was"
- Removes "Anything you can give is appreciated. We need your help to keep us going."
- Replaces donation text with closing message and link to [The Undercroft](https://theundercroft.org/)
- Moves the last show event from current events to past events
- Creates `<div id="newContent"></div>` injection points on index.html and events.html
- Adds mobile responsive CSS with:
  - Hamburger menu (☰) replacing the horizontal nav on mobile
  - Sticky header and footer with scrollable content in between
  - Closing message banner displayed under the header on mobile
  - Sidebar (`#notes`) hidden on mobile to avoid duplicate content

**Output:** `docs/` folder (configurable via `config.yaml`)

### process_new_content.py

Processes markdown files from the `newContent/` folder and injects them into HTML files in the `docs/` folder. Also copies images from `newContent/` to `docs/images/`.

**Features:**
- Processes markdown files with YAML frontmatter
- Supports multiple content blocks per file with HTML comment delimiters
- Converts markdown to HTML using the `markdown` library
- Injects content into specific HTML elements using CSS selectors
- Copies all images from `newContent/` to `docs/images/`
- Replaces existing content in target elements with new content

**Pre-configured Injection Points:**
- `index.html` has `<div id="newContent"></div>` after the main blurb paragraph
- `events.html` has `<div id="newContent"></div>` after the blurb paragraph
- Target these with `#newContent` selector in your markdown files

**Markdown File Format:**
```markdown
---
target_html: index.html
---

<!-- block: element: #newContent -->
# Your Content Here
This will be inserted into the newContent div

<!-- block: element: #notes -->
## Additional Info
This goes into the notes sidebar
```

**Output:** Updates existing HTML files in `docs/` folder and copies images

### config.yaml

Configuration file for the archive tools.

```yaml
# Source folder (downloaded archive)
archive_dir: archive

# Destination folder for published site
publish_dir: docs

# New content folder (markdown files and images)
new_content_dir: newContent
```

## Usage

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Download the archive

```bash
python archive_site.py
```

This creates the `archive/` folder with the downloaded site.

### 3. Apply edits for publishing

```bash
python edit_archive.py
```

This creates the `docs/` folder with the edited site ready for hosting (compatible with GitHub Pages).

### 4. (Optional) Add new content

Create markdown files in the `newContent/` folder to add dynamic content to the site:

**Example:** `newContent/announcement.md`
```markdown
---
target_html: index.html
---

<!-- block: element: #newContent -->
# Important Announcement
Your content here will appear on the index page
```

Then run:
```bash
python3 process_new_content.py
```

This processes markdown files from the `newContent/` folder and injects them into existing HTML files in the `docs/` folder. Images in `newContent/` (and subdirectories) are automatically copied to `docs/images/`.

See `newContent/README.md` and `newContent/LOCATIONS.md` for complete documentation.

## Testing

The project includes a comprehensive test suite to ensure the accuracy of the archival and editing processes.

### Running Tests

1. Install test dependencies (included in `requirements.txt`):
   ```bash
   pip install pytest
   ```

2. Run the full test suite:
   ```bash
   pytest
   ```

### Test Coverage

- **`test_archive_site.py`**: Validates the core archiving logic, including:
  - URL cleaning and normalization
  - WayBack Machine artifact removal
  - PHP to HTML path conversion
  - Asset extraction (CSS, images, JS)
  
- **`test_edit_archive.py`**: Verifies all editorial modifications:
  - Removal of PayPal/donation elements
  - Text replacements ("is" -> "was")
  - Mobile responsiveness injection (hamburger menu, meta tags)
  - Historical event moves (last show logic)
  - newContent div creation and placement

- **`test_process_new_content.py`**: Tests the new content processing system:
  - YAML frontmatter parsing
  - Content block extraction with HTML comment delimiters
  - Markdown to HTML conversion
  - HTML injection into target elements
  - Image copying functionality

## Requirements

- Python 3.10+
- requests
- beautifulsoup4
- pyyaml
- markdown (for `process_new_content.py`)

## Snapshot Source

The archive is based on the Wayback Machine snapshot from May 9, 2017:
https://web.archive.org/web/20170509211847/http://www.ccspace.org/

## Dynamic Content Management

The site supports dynamic content injection through markdown files:

1. Create `.md` files in the `newContent/` folder
2. Use YAML frontmatter to specify the target HTML file
3. Use HTML comment delimiters to define content blocks with CSS selectors
4. Run `python3 process_new_content.py` to inject content

**Pre-configured injection points:**
- `#newContent` on index.html (after main blurb)
- `#newContent` on events.html (after blurb)
- `#notes` on most pages (sidebar area)

See `newContent/LOCATIONS.md` for detailed documentation.

## About Charm City Art Space

Charm City Art Space was a DIY art and music venue in Baltimore, Maryland. It held its last show in November 2015. This archive preserves the website as a historical record of the space and its community.
