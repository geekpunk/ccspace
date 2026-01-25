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
- Copies `archive/` to `publish/` (preserves original)
- Removes PayPal donation links and buttons
- Removes "eat" and "eats" header links
- Changes "Charm City Art Space is" to "Charm City Art Space was"
- Removes "Anything you can give is appreciated. We need your help to keep us going."
- Replaces donation text with closing message and link to [The Undercroft](https://theundercroft.org/)
- Moves the last show event from current events to past events

**Output:** `publish/` folder

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

This creates the `publish/` folder with the edited site ready for hosting.

## Requirements

- Python 3.10+
- requests
- beautifulsoup4

## Snapshot Source

The archive is based on the Wayback Machine snapshot from May 9, 2017:
https://web.archive.org/web/20170509211847/http://www.ccspace.org/

## About Charm City Art Space

Charm City Art Space was a DIY art and music venue in Baltimore, Maryland. It held its last show in November 2015. This archive preserves the website as a historical record of the space and its community.
