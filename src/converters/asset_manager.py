"""
Asset Manager

Copies Canvas assets to Open edX static directory and converts URLs.
"""

import shutil
from pathlib import Path
from typing import Dict, Set
import re
import urllib.parse


class AssetManager:
    """Manage Canvas asset copying and URL conversion"""
    
    def __init__(self, canvas_extract_dir: Path, output_dir: Path, verbose: bool = False):
        self.canvas_dir = canvas_extract_dir
        self.output_dir = output_dir
        self.static_dir = output_dir / "static"
        self.verbose = verbose
        self.copied_files: Set[str] = set()
        
    def copy_all_assets(self) -> int:
        """Copy all assets from Canvas web_resources to static directory"""
        web_resources = self.canvas_dir / "web_resources"
        
        if not web_resources.exists():
            if self.verbose:
                print("     No web_resources directory found")
            return 0
        
        # Create static directory
        self.static_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy all files
        count = 0
        for file_path in web_resources.rglob('*'):
            if file_path.is_file():
                # Preserve directory structure
                rel_path = file_path.relative_to(web_resources)
                dest_path = self.static_dir / rel_path
                
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
                
                self.copied_files.add(str(rel_path))
                count += 1
        
        if self.verbose and count > 0:
            print(f"    Copied {count} assets to /static/")
        
        return count
    
    def convert_html_urls(self, html: str) -> str:
        """Convert Canvas URLs to Open edX /static/ paths and clean up internal links"""
        if not html:
            return html
        
        # Convert $IMS-CC-FILEBASE$ references
        # Example: $IMS-CC-FILEBASE$/Uploaded%20Media/info.png -> /static/Uploaded Media/info.png
        def replace_filebase(match):
            path = match.group(1)
            # URL decode
            decoded = urllib.parse.unquote(path)
            return f'/static/{decoded}'
        
        html = re.sub(r'\$IMS-CC-FILEBASE\$/([^"\'>\s]+)', replace_filebase, html)
        
        # Handle $WIKI_REFERENCE$ links - convert to plain text links or remove
        # These are Canvas internal links that won't work in Open edX
        # Pattern: href="$WIKI_REFERENCE$/pages/page-slug"
        def replace_wiki_reference(match):
            full_match = match.group(0)
            # Extract the title attribute if present for better link text
            title_match = re.search(r'title="([^"]*)"', full_match)
            link_text_match = re.search(r'>([^<]+)<', full_match)
            
            # Get the page slug from the URL
            slug_match = re.search(r'\$WIKI_REFERENCE\$/pages/([^"\']+)', full_match)
            
            if link_text_match:
                link_text = link_text_match.group(1)
                # Return just the link text without the anchor tag
                return f'<span class="canvas-internal-link">{link_text}</span>'
            elif title_match:
                return f'<span class="canvas-internal-link">{title_match.group(1)}</span>'
            elif slug_match:
                # Clean up the slug to be human readable
                slug = urllib.parse.unquote(slug_match.group(1))
                slug = slug.replace('-', ' ').replace('%7C', '|')
                return f'<span class="canvas-internal-link">{slug}</span>'
            
            return ''
        
        # Replace entire anchor tags containing $WIKI_REFERENCE$
        html = re.sub(
            r'<a[^>]*href="[^"]*\$WIKI_REFERENCE\$[^"]*"[^>]*>([^<]*)</a>',
            lambda m: f'<span class="canvas-internal-link">{m.group(1)}</span>',
            html
        )
        
        # Also handle any remaining $WIKI_REFERENCE$ that might be in other attributes
        html = re.sub(r'\$WIKI_REFERENCE\$/pages/[^"\'>\s]+', '#', html)
        
        # Handle $CANVAS_COURSE_REFERENCE$ links similarly
        html = re.sub(
            r'<a[^>]*href="[^"]*\$CANVAS_COURSE_REFERENCE\$[^"]*"[^>]*>([^<]*)</a>',
            lambda m: f'<span class="canvas-internal-link">{m.group(1)}</span>',
            html
        )
        html = re.sub(r'\$CANVAS_COURSE_REFERENCE\$/[^"\'>\s]+', '#', html)
        
        # Handle $CANVAS_OBJECT_REFERENCE$ links
        html = re.sub(
            r'<a[^>]*href="[^"]*\$CANVAS_OBJECT_REFERENCE\$[^"]*"[^>]*>([^<]*)</a>',
            lambda m: f'<span class="canvas-internal-link">{m.group(1)}</span>',
            html
        )
        html = re.sub(r'\$CANVAS_OBJECT_REFERENCE\$/[^"\'>\s]+', '#', html)
        
        return html
