"""
URL Name Generation Utilities

Generates valid, unique url_names for Open edX components.
"""

import re
from typing import Set


class URLNameGenerator:
    """Generates unique, URL-safe names for Open edX components"""
    
    def __init__(self):
        self.used_names: Set[str] = set()
    
    def generate(self, display_name: str, max_length: int = 50) -> str:
        """
        Generate a unique, URL-safe url_name from a display name
        
        Args:
            display_name: Human-readable name
            max_length: Maximum length for url_name
            
        Returns:
            Unique url_name string
        """
        # Convert to lowercase
        name = display_name.lower().strip()
        
        # Replace spaces and special chars with underscores
        name = re.sub(r'[^a-z0-9_-]', '_', name)
        
        # Collapse multiple underscores
        name = re.sub(r'_+', '_', name)
        
        # Remove leading/trailing underscores
        name = name.strip('_')
        
        # Truncate if too long
        if len(name) > max_length:
            name = name[:max_length].rstrip('_')
        
        # Ensure uniqueness
        original_name = name
        counter = 1
        while name in self.used_names:
            suffix = f"_{counter}"
            truncated = original_name[:max_length - len(suffix)]
            name = f"{truncated}{suffix}"
            counter += 1
        
        self.used_names.add(name)
        return name
    
    def reset(self):
        """Clear all used names"""
        self.used_names.clear()
