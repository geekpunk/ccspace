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
- Adds mobile responsive CSS with:
  - Hamburger menu (☰) replacing the horizontal nav on mobile
  - Sticky header and footer with scrollable content in between
  - Closing message banner displayed under the header on mobile
  - Sidebar (`#notes`) hidden on mobile to avoid duplicate content

**Output:** `docs/` folder (configurable via `config.yaml`)

### config.yaml

Configuration file for the archive tools.

```yaml
# Source folder (downloaded archive)
archive_dir: archive

# Destination folder for published site
publish_dir: docs
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

## Requirements

- Python 3.10+
- requests
- beautifulsoup4
- pyyaml

## Snapshot Source

The archive is based on the Wayback Machine snapshot from May 9, 2017:
https://web.archive.org/web/20170509211847/http://www.ccspace.org/

## About Charm City Art Space

Charm City Art Space was a DIY art and music venue in Baltimore, Maryland. It held its last show in November 2015. This archive preserves the website as a historical record of the space and its community.
