"""
Unit tests for process_new_content.py
"""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup
from process_new_content import (
    ContentBlock,
    MarkdownContentFile,
    NewContentProcessor
)


class TestContentBlock:
    """Tests for ContentBlock class."""

    def test_content_block_creation(self):
        """Test creating a content block."""
        block = ContentBlock('#main', '# Hello World')
        assert block.element_selector == '#main'
        assert block.markdown_content == '# Hello World'
        assert block.html_content is None

    def test_markdown_conversion(self):
        """Test converting markdown to HTML."""
        block = ContentBlock('#main', '# Hello World')
        block.convert_to_html()
        assert block.html_content is not None
        assert '<h1>Hello World</h1>' in block.html_content

    def test_markdown_with_bold(self):
        """Test markdown with bold text."""
        block = ContentBlock('#main', 'This is **bold** text')
        block.convert_to_html()
        assert '<strong>bold</strong>' in block.html_content

    def test_markdown_with_links(self):
        """Test markdown with links."""
        block = ContentBlock('#main', '[Link](http://example.com)')
        block.convert_to_html()
        assert '<a href="http://example.com">Link</a>' in block.html_content


class TestMarkdownContentFile:
    """Tests for MarkdownContentFile class."""

    def test_parse_frontmatter(self, tmp_path):
        """Test parsing YAML frontmatter."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #main -->
Content here
""")
        md_content = MarkdownContentFile(md_file)
        assert md_content.target_html == 'test.html'

    def test_missing_frontmatter(self, tmp_path):
        """Test error when frontmatter is missing."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("# Just content")

        with pytest.raises(ValueError, match="No YAML frontmatter"):
            MarkdownContentFile(md_file)

    def test_missing_target_html(self, tmp_path):
        """Test error when target_html is not specified."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
some_other_field: value
---

Content
""")
        with pytest.raises(ValueError, match="No 'target_html' specified"):
            MarkdownContentFile(md_file)

    def test_parse_single_block(self, tmp_path):
        """Test parsing a single content block."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #main -->
# Main Content
This is the main content.
""")
        md_content = MarkdownContentFile(md_file)
        assert len(md_content.blocks) == 1
        assert md_content.blocks[0].element_selector == '#main'
        assert '# Main Content' in md_content.blocks[0].markdown_content

    def test_parse_multiple_blocks(self, tmp_path):
        """Test parsing multiple content blocks."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #main -->
# Main Content

<!-- block: element: .sidebar -->
## Sidebar Content
""")
        md_content = MarkdownContentFile(md_file)
        assert len(md_content.blocks) == 2
        assert md_content.blocks[0].element_selector == '#main'
        assert md_content.blocks[1].element_selector == '.sidebar'

    def test_no_blocks_error(self, tmp_path):
        """Test error when no blocks are found."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
target_html: test.html
---

Just content without block markers
""")
        with pytest.raises(ValueError, match="No content blocks found"):
            MarkdownContentFile(md_file)

    def test_convert_all_blocks(self, tmp_path):
        """Test converting all blocks to HTML."""
        md_file = tmp_path / 'test.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #main -->
# Heading

<!-- block: element: .sidebar -->
**Bold text**
""")
        md_content = MarkdownContentFile(md_file)
        md_content.convert_blocks_to_html()

        assert '<h1>Heading</h1>' in md_content.blocks[0].html_content
        assert '<strong>Bold text</strong>' in md_content.blocks[1].html_content


class TestNewContentProcessor:
    """Tests for NewContentProcessor class."""

    def test_load_config(self, tmp_path):
        """Test loading configuration."""
        config_file = tmp_path / 'config.yaml'
        config_file.write_text("""
new_content_dir: newContent
publish_dir: docs
""")
        processor = NewContentProcessor(str(config_file))
        assert processor.config['new_content_dir'] == 'newContent'
        assert processor.config['publish_dir'] == 'docs'

    def test_process_markdown_injection(self, tmp_path):
        """Test full markdown processing and HTML injection."""
        # Create config
        config_file = tmp_path / 'config.yaml'
        config_file.write_text(f"""
new_content_dir: {tmp_path / 'newContent'}
publish_dir: {tmp_path / 'docs'}
""")

        # Create directories
        new_content_dir = tmp_path / 'newContent'
        new_content_dir.mkdir()
        docs_dir = tmp_path / 'docs'
        docs_dir.mkdir()

        # Create target HTML file
        target_html = docs_dir / 'test.html'
        target_html.write_text("""
<html>
<body>
    <div id="main"></div>
</body>
</html>
""")

        # Create markdown file
        md_file = new_content_dir / 'content.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #main -->
# Test Heading
This is test content.
""")

        # Process
        processor = NewContentProcessor(str(config_file))
        processor.process_markdown_files()

        # Verify injection
        result_html = target_html.read_text()
        soup = BeautifulSoup(result_html, 'html.parser')
        main_div = soup.select_one('#main')

        assert main_div is not None
        assert main_div.find('h1') is not None
        assert 'Test Heading' in main_div.get_text()

    def test_copy_images(self, tmp_path):
        """Test copying images to docs/images."""
        # Create config
        config_file = tmp_path / 'config.yaml'
        config_file.write_text(f"""
new_content_dir: {tmp_path / 'newContent'}
publish_dir: {tmp_path / 'docs'}
""")

        # Create directories
        new_content_dir = tmp_path / 'newContent'
        new_content_dir.mkdir()
        docs_dir = tmp_path / 'docs'
        docs_dir.mkdir()

        # Create test image
        test_image = new_content_dir / 'test.png'
        test_image.write_text('fake image data')

        # Process
        processor = NewContentProcessor(str(config_file))
        processor.copy_images()

        # Verify copy
        copied_image = docs_dir / 'images' / 'test.png'
        assert copied_image.exists()
        assert copied_image.read_text() == 'fake image data'

    def test_element_not_found_warning(self, tmp_path, capsys):
        """Test warning when target element is not found."""
        # Create config
        config_file = tmp_path / 'config.yaml'
        config_file.write_text(f"""
new_content_dir: {tmp_path / 'newContent'}
publish_dir: {tmp_path / 'docs'}
""")

        # Create directories
        new_content_dir = tmp_path / 'newContent'
        new_content_dir.mkdir()
        docs_dir = tmp_path / 'docs'
        docs_dir.mkdir()

        # Create target HTML without the required element
        target_html = docs_dir / 'test.html'
        target_html.write_text("""
<html>
<body>
    <div id="different"></div>
</body>
</html>
""")

        # Create markdown file
        md_file = new_content_dir / 'content.md'
        md_file.write_text("""---
target_html: test.html
---

<!-- block: element: #nonexistent -->
# Content
""")

        # Process
        processor = NewContentProcessor(str(config_file))
        processor.process_markdown_files()

        # Check for warning
        captured = capsys.readouterr()
        assert "Warning: Element '#nonexistent' not found" in captured.out
