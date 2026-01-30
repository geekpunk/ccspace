#!/usr/bin/env python3
"""
Process New Content Script

Processes markdown files from the newContent folder and injects them into HTML files
in the publish/docs folder. Also copies images from newContent to docs/images.

Markdown file format:
---
target_html: events.html
---

<!-- block: element: #main-content -->
# Content here
This content will be inserted into the #main-content element.

<!-- block: element: .sidebar -->
## Sidebar content
This goes into the .sidebar element.
"""

import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import markdown
import yaml
from bs4 import BeautifulSoup


class ContentBlock:
    """Represents a single content block with target element selector."""

    def __init__(self, element_selector: str, markdown_content: str):
        self.element_selector = element_selector
        self.markdown_content = markdown_content
        self.html_content = None

    def convert_to_html(self):
        """Convert markdown content to HTML."""
        self.html_content = markdown.markdown(
            self.markdown_content,
            extensions=['extra', 'codehilite', 'tables']
        )


class MarkdownContentFile:
    """Represents a markdown file with frontmatter and content blocks."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.target_html = None
        self.blocks: List[ContentBlock] = []
        self._parse()

    def _parse(self):
        """Parse the markdown file to extract frontmatter and blocks."""
        content = self.file_path.read_text(encoding='utf-8')

        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"No YAML frontmatter found in {self.file_path}")

        frontmatter_yaml = frontmatter_match.group(1)
        frontmatter = yaml.safe_load(frontmatter_yaml)
        self.target_html = frontmatter.get('target_html')

        if not self.target_html:
            raise ValueError(f"No 'target_html' specified in frontmatter of {self.file_path}")

        # Extract content after frontmatter
        content_after_frontmatter = content[frontmatter_match.end():]

        # Split by block comments
        block_pattern = re.compile(r'<!--\s*block:\s*element:\s*([^\s]+)\s*-->')

        # Find all block markers
        block_markers = list(block_pattern.finditer(content_after_frontmatter))

        if not block_markers:
            raise ValueError(f"No content blocks found in {self.file_path}")

        # Extract each block
        for i, match in enumerate(block_markers):
            element_selector = match.group(1)

            # Get content from after this marker to before the next marker (or end of file)
            start_pos = match.end()
            end_pos = block_markers[i + 1].start() if i + 1 < len(block_markers) else len(content_after_frontmatter)

            block_content = content_after_frontmatter[start_pos:end_pos].strip()

            block = ContentBlock(element_selector, block_content)
            self.blocks.append(block)

    def convert_blocks_to_html(self):
        """Convert all blocks from markdown to HTML."""
        for block in self.blocks:
            block.convert_to_html()


class NewContentProcessor:
    """Main processor for new content."""

    def __init__(self, config_path: str = 'config.yaml'):
        self.config = self._load_config(config_path)
        self.new_content_dir = Path(self.config['new_content_dir'])
        self.publish_dir = Path(self.config['publish_dir'])
        self.images_output_dir = self.publish_dir / 'images'

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def copy_images(self):
        """Copy all images from newContent folder to publish/docs/images."""
        if not self.new_content_dir.exists():
            print(f"Warning: {self.new_content_dir} does not exist. Skipping image copy.")
            return

        # Ensure output directory exists
        self.images_output_dir.mkdir(parents=True, exist_ok=True)

        # Common image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico'}

        # Find and copy all images
        copied_count = 0
        for image_file in self.new_content_dir.rglob('*'):
            if image_file.is_file() and image_file.suffix.lower() in image_extensions:
                destination = self.images_output_dir / image_file.name
                shutil.copy2(image_file, destination)
                print(f"Copied: {image_file.name} -> {destination}")
                copied_count += 1

        print(f"Total images copied: {copied_count}")

    def process_markdown_files(self):
        """Process all markdown files in the newContent folder."""
        if not self.new_content_dir.exists():
            print(f"Warning: {self.new_content_dir} does not exist. Skipping markdown processing.")
            return

        # Find all markdown files
        md_files = list(self.new_content_dir.rglob('*.md'))

        if not md_files:
            print(f"No markdown files found in {self.new_content_dir}")
            return

        print(f"Found {len(md_files)} markdown file(s) to process")

        for md_file in md_files:
            print(f"\nProcessing: {md_file.name}")
            try:
                self._process_single_markdown_file(md_file)
            except Exception as e:
                print(f"Error processing {md_file.name}: {e}")

    def _process_single_markdown_file(self, md_file_path: Path):
        """Process a single markdown file and inject into target HTML."""
        # Parse the markdown file
        md_content = MarkdownContentFile(md_file_path)

        # Convert blocks to HTML
        md_content.convert_blocks_to_html()

        # Get target HTML file path
        target_html_path = self.publish_dir / md_content.target_html

        if not target_html_path.exists():
            raise FileNotFoundError(f"Target HTML file not found: {target_html_path}")

        # Load and parse the HTML file
        html_content = target_html_path.read_text(encoding='utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Insert each block into its target element
        for block in md_content.blocks:
            target_element = soup.select_one(block.element_selector)

            if not target_element:
                print(f"  Warning: Element '{block.element_selector}' not found in {md_content.target_html}")
                continue

            # Create a new div to hold the injected content
            new_content = BeautifulSoup(block.html_content, 'html.parser')

            # Replace the content in the target element
            # Clear existing content first
            target_element.clear()

            # Insert the new content
            for element in new_content:
                target_element.append(element)

            print(f"  Replaced content in '{block.element_selector}'")

        # Write the modified HTML back to the file
        target_html_path.write_text(str(soup), encoding='utf-8')
        print(f"  Updated: {target_html_path}")

    def run(self):
        """Run the complete content processing workflow."""
        print("=== New Content Processor ===\n")

        print("Step 1: Copying images...")
        self.copy_images()

        print("\n" + "="*40)
        print("\nStep 2: Processing markdown files...")
        self.process_markdown_files()

        print("\n" + "="*40)
        print("\nContent processing complete!")


def main():
    """Main entry point."""
    processor = NewContentProcessor()
    processor.run()


if __name__ == '__main__':
    main()
