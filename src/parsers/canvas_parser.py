"""
Canvas Course Parser

Parses Canvas IMS Common Cartridge (IMSCC) export files.
"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup
import tempfile
import shutil


class CanvasParser:
    """Parse Canvas IMSCC export files"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.temp_dir = None
        self.extract_dir = None
        
    def parse(self, imscc_path: str) -> Dict:
        """
        Parse Canvas IMSCC file
        
        Args:
            imscc_path: Path to .imscc file
            
        Returns:
            Dictionary with course structure and content
        """
        imscc_path = Path(imscc_path)
        
        if not imscc_path.exists():
            raise FileNotFoundError(f"IMSCC file not found: {imscc_path}")
        
        # Extract IMSCC (ZIP) file
        self.temp_dir = Path(tempfile.mkdtemp(prefix="canvas_parser_"))
        self.extract_dir = self.temp_dir / "extracted"
        
        if self.verbose:
            print(f" Extracting {imscc_path.name}...")
        
        with zipfile.ZipFile(imscc_path, 'r') as zip_ref:
            zip_ref.extractall(self.extract_dir)
        
        # Parse structure
        manifest = self._parse_manifest()
        course_settings = self._parse_course_settings()
        modules = self._parse_modules()
        assignment_groups = self._parse_assignment_groups()
        
        # Build course structure
        course_data = {
            'title': course_settings.get('title', 'Untitled Course'),
            'course_code': course_settings.get('course_code', ''),
            'start_date': course_settings.get('start_at'),
            'end_date': course_settings.get('conclude_at'),
            'identifier': course_settings.get('identifier', ''),
            'group_weighting_scheme': course_settings.get('group_weighting_scheme', ''),
            'modules': modules,
            'assignment_groups': assignment_groups,
            'manifest': manifest,
            'extract_dir': self.extract_dir
        }
        
        return course_data
    
    def _parse_manifest(self) -> ET.Element:
        """Parse imsmanifest.xml"""
        manifest_path = self.extract_dir / "imsmanifest.xml"
        
        if not manifest_path.exists():
            raise ValueError("No imsmanifest.xml found in IMSCC")
        
        tree = ET.parse(manifest_path)
        return tree.getroot()
    
    def _parse_course_settings(self) -> Dict:
        """Parse course_settings/course_settings.xml"""
        settings_path = self.extract_dir / "course_settings" / "course_settings.xml"
        
        if not settings_path.exists():
            return {}
        
        tree = ET.parse(settings_path)
        root = tree.getroot()
        
        # Handle namespace
        ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}
        
        # Extract basic settings (try with and without namespace)
        settings = {
            'identifier': root.get('identifier'),
            'title': self._get_text_ns(root, 'title', ns),
            'course_code': self._get_text_ns(root, 'course_code', ns),
            'start_at': self._get_text_ns(root, 'start_at', ns),
            'conclude_at': self._get_text_ns(root, 'conclude_at', ns),
            'license': self._get_text_ns(root, 'license', ns),
            'is_public': self._get_text_ns(root, 'is_public', ns) == 'true',
            'group_weighting_scheme': self._get_text_ns(root, 'group_weighting_scheme', ns),
        }
        
        return settings
    
    def _parse_modules(self) -> List[Dict]:
        """Parse course_settings/module_meta.xml"""
        module_path = self.extract_dir / "course_settings" / "module_meta.xml"
        
        if not module_path.exists():
            if self.verbose:
                print("  No module_meta.xml found")
            return []
        
        tree = ET.parse(module_path)
        root = tree.getroot()
        
        # Handle XML namespace
        ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}
        
        modules = []
        # Try with namespace first
        for module_elem in root.findall('cc:module', ns):
            module_data = self._parse_module(module_elem)
            modules.append(module_data)
        
        # Fallback to no namespace
        if not modules:
            for module_elem in root.findall('.//module'):
                module_data = self._parse_module(module_elem)
                modules.append(module_data)
        
        return modules
    
    def _parse_module(self, module_elem: ET.Element) -> Dict:
        """Parse individual module element"""
        # Define namespace
        ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}
        
        module = {
            'identifier': module_elem.get('identifier'),
            'title': self._get_text_with_ns(module_elem, 'title', ns),
            'workflow_state': self._get_text_with_ns(module_elem, 'workflow_state', ns),
            'position': int(self._get_text_with_ns(module_elem, 'position', ns) or '0'),
            'require_sequential_progress': self._get_text_with_ns(module_elem, 'require_sequential_progress', ns) == 'true',
            'prerequisites': self._parse_prerequisites(module_elem, ns),
            'completion_requirements': self._parse_completion_requirements(module_elem, ns),
            'items': []
        }
        
        # Parse module items - try with namespace first, then without
        items_elem = module_elem.find('cc:items', ns)
        if items_elem is None:
            items_elem = module_elem.find('items')
            
        if items_elem is not None:
            # Try to find items with namespace
            item_list = items_elem.findall('cc:item', ns)
            if not item_list:
                # Fallback to no namespace
                item_list = items_elem.findall('item')
                
            for item_elem in item_list:
                item = self._parse_module_item(item_elem, ns)
                module['items'].append(item)
        
        return module
    
    def _parse_module_item(self, item_elem: ET.Element, ns: Dict = None) -> Dict:
        """Parse individual module item"""
        if ns is None:
            ns = {}
            
        return {
            'identifier': item_elem.get('identifier'),
            'content_type': self._get_text_with_ns(item_elem, 'content_type', ns),
            'title': self._get_text_with_ns(item_elem, 'title', ns),
            'identifierref': self._get_text_with_ns(item_elem, 'identifierref', ns),
            'workflow_state': self._get_text_with_ns(item_elem, 'workflow_state', ns),
            'position': int(self._get_text_with_ns(item_elem, 'position', ns) or '0'),
            'url': self._get_text_with_ns(item_elem, 'url', ns),
        }
    
    def _parse_prerequisites(self, module_elem: ET.Element, ns: Dict = None) -> List[Dict]:
        """Parse module prerequisites"""
        if ns is None:
            ns = {}
            
        prereqs = []
        # Try with namespace first
        prereq_elem = module_elem.find('cc:prerequisites', ns) if ns else None
        if prereq_elem is None:
            prereq_elem = module_elem.find('prerequisites')
        
        if prereq_elem is not None:
            # Try to find prereq elements with namespace
            prereq_list = prereq_elem.findall('cc:prerequisite', ns) if ns else []
            if not prereq_list:
                prereq_list = prereq_elem.findall('prerequisite')
                
            for prereq in prereq_list:
                prereqs.append({
                    'type': prereq.get('type'),
                    'identifierref': self._get_text_with_ns(prereq, 'identifierref', ns),
                    'title': self._get_text_with_ns(prereq, 'title', ns)
                })
        
        return prereqs
    
    def _parse_completion_requirements(self, module_elem: ET.Element, ns: Dict = None) -> List[Dict]:
        """Parse completion requirements"""
        if ns is None:
            ns = {}
            
        requirements = []
        # Try with namespace first
        req_elem = module_elem.find('cc:completionRequirements', ns) if ns else None
        if req_elem is None:
            req_elem = module_elem.find('completionRequirements')
        
        if req_elem is not None:
            # Try to find requirement elements with namespace
            req_list = req_elem.findall('cc:completionRequirement', ns) if ns else []
            if not req_list:
                req_list = req_elem.findall('completionRequirement')
                
            for req in req_list:
                requirements.append({
                    'type': req.get('type'),
                    'min_score': float(self._get_text_with_ns(req, 'min_score', ns) or '0'),
                    'identifierref': self._get_text_with_ns(req, 'identifierref', ns)
                })
        
        return requirements
    
    def get_wiki_page_content(self, identifier: str) -> Optional[str]:
        """Get wiki page HTML content"""
        # Try wiki_content directory
        wiki_dir = self.extract_dir / "wiki_content"
        
        if wiki_dir.exists():
            for html_file in wiki_dir.glob("*.html"):
                # Parse to check identifier
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    soup = BeautifulSoup(content, 'html.parser')
                    meta = soup.find('meta', {'name': 'identifier'})
                    
                    if meta and meta.get('content') == identifier:
                        # Extract body content
                        body = soup.find('body')
                        if body:
                            return str(body)
        
        return None
    
    def get_front_page(self) -> Optional[Tuple[str, str]]:
        """
        Find the front page (home page) of the Canvas course.
        
        Returns:
            Tuple of (identifier, html_content) if found, None otherwise
        """
        wiki_dir = self.extract_dir / "wiki_content"
        
        if not wiki_dir.exists():
            return None
        
        for html_file in wiki_dir.glob("*.html"):
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Check for front_page meta tag
                front_page_meta = soup.find('meta', {'name': 'front_page'})
                if front_page_meta and front_page_meta.get('content') == 'true':
                    # Get identifier
                    identifier_meta = soup.find('meta', {'name': 'identifier'})
                    identifier = identifier_meta.get('content') if identifier_meta else None
                    
                    # Extract body content
                    body = soup.find('body')
                    if body:
                        body_content = ''.join(str(child) for child in body.children)
                        return (identifier, body_content)
        
        return None
    
    def get_assignment_settings(self, identifier: str) -> Optional[Dict]:
        """Get assignment settings and HTML content"""
        # Look for assignment directory
        assignment_dir = self.extract_dir / identifier
        settings_file = assignment_dir / "assignment_settings.xml"
        
        if not settings_file.exists():
            return None
            
        tree = ET.parse(settings_file)
        root = tree.getroot()
        
        # Handle namespace
        ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}
        
        # Parse settings with namespace support
        settings = {
            'identifier': root.get('identifier'),
            'title': self._get_text_ns(root, 'title', ns),
            'points_possible': self._safe_float(self._get_text_ns(root, 'points_possible', ns), 0),
            'grading_type': self._get_text_ns(root, 'grading_type', ns),
            'submission_types': self._get_text_ns(root, 'submission_types', ns),
            'workflow_state': self._get_text_ns(root, 'workflow_state', ns),
            'due_at': self._get_text_ns(root, 'due_at', ns),
            'assignment_group_identifierref': self._get_text_ns(root, 'assignment_group_identifierref', ns),
        }
        
        # Find and read assignment HTML content
        html_content = None
        for html_file in assignment_dir.glob("*.html"):
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')
                body = soup.find('body')
                if body:
                    html_content = ''.join(str(child) for child in body.children)
                else:
                    html_content = content
                break
        
        settings['html_content'] = html_content
        
        return settings
    
    def _safe_float(self, value: str, default: float = 0) -> float:
        """Safely convert string to float"""
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _parse_assignment_groups(self) -> List[Dict]:
        """Parse course_settings/assignment_groups.xml"""
        groups_path = self.extract_dir / "course_settings" / "assignment_groups.xml"
        
        if not groups_path.exists():
            return []
        
        tree = ET.parse(groups_path)
        root = tree.getroot()
        
        # Handle namespace
        ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}
        
        groups = []
        
        # Try with namespace first
        for group_elem in root.findall('cc:assignmentGroup', ns):
            group = self._parse_assignment_group(group_elem, ns)
            groups.append(group)
        
        # Fallback to no namespace
        if not groups:
            for group_elem in root.findall('.//assignmentGroup'):
                group = self._parse_assignment_group(group_elem, {})
                groups.append(group)
        
        return groups
    
    def _parse_assignment_group(self, group_elem: ET.Element, ns: Dict) -> Dict:
        """Parse individual assignment group element"""
        return {
            'identifier': group_elem.get('identifier'),
            'title': self._get_text_ns(group_elem, 'title', ns),
            'position': int(self._get_text_ns(group_elem, 'position', ns) or '0'),
            'group_weight': self._safe_float(self._get_text_ns(group_elem, 'group_weight', ns), 0),
        }
    
    def _get_text(self, elem: ET.Element, tag: str, default: str = '') -> str:
        """Safely get text from XML element"""
        child = elem.find(tag)
        return child.text if child is not None and child.text else default
    
    def _get_text_with_ns(self, elem: ET.Element, tag: str, ns: Dict, default: str = '') -> str:
        """Safely get text from XML element with namespace support"""
        # Try with namespace first
        if ns and 'cc' in ns:
            child = elem.find(f'cc:{tag}', ns)
            if child is not None and child.text:
                return child.text
        
        # Fallback to no namespace
        child = elem.find(tag)
        return child.text if child is not None and child.text else default
    
    def _get_text_ns(self, elem: ET.Element, tag: str, ns: Dict, default: str = '') -> str:
        """Safely get text from XML element with namespace support"""
        # Try with namespace first
        for prefix, uri in ns.items():
            child = elem.find(f'{{{uri}}}{tag}')
            if child is not None and child.text:
                return child.text
        
        # Fallback to no namespace
        child = elem.find(tag)
        return child.text if child is not None and child.text else default
    
    def cleanup(self):
        """Clean up temporary files"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
