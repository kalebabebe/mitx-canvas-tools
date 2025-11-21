"""
Canvas to Intermediate Representation Converter

Converts parsed Canvas course data to IR format.
"""

from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
import re

from ..models.intermediate_rep import (
    CourseIR, ChapterIR, SequentialIR, VerticalIR, ComponentIR
)
from ..utils.url_name_generator import URLNameGenerator
from ..parsers.qti_parser import QTIParser
from ..converters.qti_to_capa import QTIToCapaConverter


class CanvasToIRConverter:
    """Convert Canvas course data to Intermediate Representation"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.url_gen = URLNameGenerator()
        self.qti_parser = QTIParser(verbose=verbose)
        self.capa_converter = QTIToCapaConverter(verbose=verbose)
    
    def convert(self, canvas_data: Dict, canvas_parser) -> CourseIR:
        """
        Convert Canvas course data to IR
        
        Args:
            canvas_data: Parsed Canvas course data
            canvas_parser: Canvas parser instance (for fetching content)
            
        Returns:
            CourseIR object
        """
        if self.verbose:
            print("🔄 Converting to intermediate representation...")
        
        # Extract course metadata
        org, course, run = self._extract_course_id(canvas_data)
        
        course_ir = CourseIR(
            title=canvas_data['title'],
            org=org,
            course=course,
            run=run,
            canvas_course_code=canvas_data.get('course_code', ''),
            canvas_identifier=canvas_data.get('identifier', ''),
            start_date=self._parse_date(canvas_data.get('start_date')),
            end_date=self._parse_date(canvas_data.get('end_date'))
        )
        
        # Build prerequisite map
        prereq_map = self._build_prerequisite_map(canvas_data['modules'])
        
        # Convert modules to chapters
        for module in canvas_data['modules']:
            chapter = self._convert_module_to_chapter(
                module, 
                canvas_parser,
                prereq_map.get(module['identifier'])
            )
            course_ir.chapters.append(chapter)
        
        if self.verbose:
            print(f"   ✅ Converted {len(course_ir.chapters)} chapters")
        
        return course_ir
    
    def _extract_course_id(self, canvas_data: Dict) -> tuple:
        """Extract org, course, run from Canvas data"""
        course_code = canvas_data.get('course_code', 'Course')
        start_date = canvas_data.get('start_date', '')
        
        # Try to parse course code
        # Common formats: "ORG.COURSE", "COURSE CODE", etc.
        parts = course_code.split('.')
        if len(parts) >= 2:
            org = parts[0]
            course = '.'.join(parts[1:])
        else:
            org = "CanvasImport"
            course = course_code.replace(' ', '_')
        
        # Extract run from date or use default
        if start_date:
            try:
                date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                run = str(date_obj.year)
            except:
                run = "Import"
        else:
            run = "Import"
        
        # Clean names
        org = self._clean_id(org)
        course = self._clean_id(course)
        run = self._clean_id(run)
        
        return org, course, run
    
    def _clean_id(self, text: str) -> str:
        """Clean text for use in course ID"""
        text = re.sub(r'[^a-zA-Z0-9_.-]', '_', text)
        text = re.sub(r'_+', '_', text)
        return text.strip('_')
    
    def _build_prerequisite_map(self, modules: List[Dict]) -> Dict[str, str]:
        """Build map of module prerequisites"""
        prereq_map = {}
        module_url_names = {}
        
        # First pass: generate url_names
        for module in modules:
            url_name = self.url_gen.generate(module['title'])
            module_url_names[module['identifier']] = url_name
        
        # Second pass: map prerequisites
        for module in modules:
            if module.get('prerequisites'):
                # Take first prerequisite (OEdX supports single prereq)
                prereq_id = module['prerequisites'][0]['identifierref']
                if prereq_id in module_url_names:
                    prereq_map[module['identifier']] = module_url_names[prereq_id]
        
        return prereq_map
    
    def _convert_module_to_chapter(
        self, 
        module: Dict, 
        canvas_parser,
        prereq: Optional[str] = None
    ) -> ChapterIR:
        """Convert Canvas module to Chapter + Sequential"""
        
        chapter_url_name = self.url_gen.generate(module['title'])
        
        chapter = ChapterIR(
            display_name=module['title'],
            url_name=chapter_url_name,
            published=(module['workflow_state'] == 'active'),
            position=module['position']
        )
        
        # Create single sequential for module
        sequential = SequentialIR(
            display_name=module['title'],
            url_name=f"{chapter_url_name}_content",
            published=(module['workflow_state'] == 'active'),
            prereq=prereq,
            require_sequential=module.get('require_sequential_progress', False)
        )
        
        # Convert module items to verticals
        for item in module['items']:
            try:
                vertical = self._convert_item_to_vertical(item, canvas_parser)
                if vertical:
                    sequential.verticals.append(vertical)
            except Exception as e:
                if self.verbose:
                    print(f"   ⚠️  Error converting item '{item['title']}': {e}")
        
        chapter.sequentials.append(sequential)
        
        return chapter
    
    def _convert_item_to_vertical(
        self, 
        item: Dict, 
        canvas_parser
    ) -> Optional[VerticalIR]:
        """Convert Canvas module item to Vertical with components"""
        
        content_type = item['content_type']
        
        vertical = VerticalIR(
            display_name=item['title'],
            url_name=self.url_gen.generate(item['title']),
            published=(item['workflow_state'] == 'active')
        )
        
        # Convert based on content type
        if content_type == 'WikiPage':
            component = self._convert_wiki_page(item, canvas_parser)
            if component:
                vertical.components.append(component)
        
        elif content_type == 'Assignment':
            component = self._convert_assignment(item, canvas_parser)
            if component:
                vertical.components.append(component)
        
        elif content_type == 'Quizzes::Quiz':
            components = self._convert_quiz(item, canvas_parser)
            if components:
                for component in components:
                    vertical.components.append(component)
        
        elif content_type == 'ContextExternalTool':
            # LTI tool - add to unsupported (handled by caller)
            pass
        
        return vertical if vertical.components else None
    
    def _convert_wiki_page(
        self, 
        item: Dict, 
        canvas_parser
    ) -> Optional[ComponentIR]:
        """Convert wiki page to HTML component"""
        
        identifier = item['identifierref']
        html_content = canvas_parser.get_wiki_page_content(identifier)
        
        if not html_content:
            if self.verbose:
                print(f"   ⚠️  No content found for page: {item['title']}")
            return None
        
        # Extract body content
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body')
        
        if body:
            # Remove body tags, keep content
            content = ''.join(str(child) for child in body.children)
        else:
            content = html_content
        
        # Wrap in div
        content = f'<div class="wiki-page-content">\n{content}\n</div>'
        
        return ComponentIR(
            type='html',
            display_name=item['title'],
            url_name=self.url_gen.generate(f"{item['title']}_html"),
            content=content,
            canvas_source=item
        )
    
    def _convert_assignment(
        self, 
        item: Dict, 
        canvas_parser
    ) -> Optional[ComponentIR]:
        """Convert assignment to HTML component (for now)"""
        
        identifier = item['identifierref']
        settings = canvas_parser.get_assignment_settings(identifier)
        
        if not settings:
            if self.verbose:
                print(f"   ⚠️  No settings found for assignment: {item['title']}")
            return None
        
        # Create HTML description
        points = settings.get('points_possible', 0)
        submission_type = settings.get('submission_types', 'not_graded')
        grading_type = settings.get('grading_type', 'not_graded')
        
        html_content = f'''<div class="assignment-info">
    <h3>{item['title']}</h3>
    <p><strong>Submission Type:</strong> {submission_type}</p>
    <p><strong>Grading Type:</strong> {grading_type}</p>
    <p><strong>Points Possible:</strong> {points}</p>
    
    <p><em>Note: This assignment was imported from Canvas. 
    Submission and grading functionality needs to be configured in Open edX.</em></p>
</div>'''
        
        return ComponentIR(
            type='html',
            display_name=item['title'],
            url_name=self.url_gen.generate(f"{item['title']}_assignment"),
            content=html_content,
            settings=settings,
            canvas_source=item
        )
    
    def _convert_quiz(
        self,
        item: Dict,
        canvas_parser
    ) -> List[ComponentIR]:
        """Convert quiz to problem components"""
        
        identifier = item['identifierref']
        
        # Find QTI file
        qti_path = canvas_parser.extract_dir / identifier / "assessment_qti.xml"
        
        if not qti_path.exists():
            if self.verbose:
                print(f"   ⚠️  No QTI file found for quiz: {item['title']}")
            return []
        
        # Parse QTI
        quiz_data = self.qti_parser.parse_quiz(qti_path)
        
        if not quiz_data or not quiz_data.get('questions'):
            if self.verbose:
                print(f"   ⚠️  No questions found in quiz: {item['title']}")
            return []
        
        # Convert each question to a component
        components = []
        
        for i, question in enumerate(quiz_data['questions'], 1):
            # Convert to CAPA
            capa_xml = self.capa_converter.convert_question(question)
            
            # Create problem component
            component = ComponentIR(
                type='problem',
                display_name=question.get('title') or f"Question {i}",
                url_name=self.url_gen.generate(f"{item['title']}_q{i}"),
                content=capa_xml,
                canvas_source=item
            )
            components.append(component)
        
        if self.verbose:
            print(f"   ✅ Converted quiz '{item['title']}': {len(components)} questions")
        
        return components
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string"""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
