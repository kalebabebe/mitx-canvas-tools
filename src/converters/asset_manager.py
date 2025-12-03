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
        """Convert Canvas URLs to Open edX /static/ paths"""
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
        
        return html
