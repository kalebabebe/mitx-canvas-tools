"""
Asset Manager

Copies Canvas assets to Open edX static directory and converts URLs.
"""

import shutil
from pathlib import Path
from typing import Dict, Set, Optional
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
        # Map of Canvas identifiers to OLX url_names for internal link conversion
        self.identifier_to_url_name: Dict[str, str] = {}
        
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
        
        # Convert Panopto LTI embeds to direct embeds
        html = self._convert_panopto_embeds(html)
        
        # Convert $IMS-CC-FILEBASE$ references
        # Example: $IMS-CC-FILEBASE$/Uploaded%20Media/info.png -> /static/Uploaded Media/info.png
        def replace_filebase(match):
            path = match.group(1)
            # URL decode
            decoded = urllib.parse.unquote(path)
            return f'/static/{decoded}'
        
        html = re.sub(r'\$IMS-CC-FILEBASE\$/([^"\'>\s]+)', replace_filebase, html)
        
        # Convert $WIKI_REFERENCE$ links to jump_to_id links or strip if not found
        html = self._convert_wiki_references(html)
        
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
    
    def _convert_panopto_embeds(self, html: str) -> str:
        """Convert Canvas Panopto LTI iframes to direct Panopto embeds"""
        
        # Pattern to match Panopto LTI iframes
        # Looks for iframes with src containing panopto and custom_context_delivery parameter
        panopto_iframe_pattern = re.compile(
            r'<iframe[^>]*src="[^"]*(?:panopto|PANOPTO)[^"]*custom_context_delivery(?:%3D|=)([a-f0-9-]+)[^"]*"[^>]*>(?:</iframe>)?',
            re.IGNORECASE
        )
        
        def replace_panopto_iframe(match):
            video_id = match.group(1)
            
            # Build responsive Panopto embed
            embed_html = f'''<div style="position: relative; width: 100%; height: 0; padding-bottom: 56.25%">
	<iframe src="https://mit.hosted.panopto.com/Panopto/Pages/Embed.aspx?id={video_id}&autoplay=false&offerviewer=true&showtitle=true&showbrand=true&captions=false&interactivity=all" style="border: 1px solid #464646; position: absolute; top: 0; left: 0; width: 100%; height: 100%; box-sizing: border-box;" allowfullscreen allow="autoplay" aria-label="Panopto Embedded Video Player"></iframe>
</div>'''
            return embed_html
        
        html = panopto_iframe_pattern.sub(replace_panopto_iframe, html)
        
        return html
    
    def _convert_wiki_references(self, html: str) -> str:
        """Convert $WIKI_REFERENCE$ links to jump_to_id or strip to plain text"""
        
        # Pattern to match anchor tags with $WIKI_REFERENCE$ hrefs
        wiki_link_pattern = re.compile(
            r'<a([^>]*)href="[^"]*\$WIKI_REFERENCE\$/pages/([^"]+)"([^>]*)>([^<]*)</a>',
            re.IGNORECASE
        )
        
        def replace_wiki_link(match):
            before_href = match.group(1)
            identifier = match.group(2)
            after_href = match.group(3)
            link_text = match.group(4)
            
            # URL decode the identifier
            identifier = urllib.parse.unquote(identifier)
            
            # Try to find the url_name for this identifier
            url_name = self.identifier_to_url_name.get(identifier)
            
            if url_name:
                # Convert to jump_to_id link
                return f'<a{before_href}href="/jump_to_id/{url_name}"{after_href}>{link_text}</a>'
            else:
                # Strip to plain text with class for styling
                return f'<span class="canvas-internal-link">{link_text}</span>'
        
        html = wiki_link_pattern.sub(replace_wiki_link, html)
        
        # Clean up any remaining $WIKI_REFERENCE$ that might be in other attributes
        html = re.sub(r'\$WIKI_REFERENCE\$/pages/[^"\'>\s]+', '#', html)
        
        return html
