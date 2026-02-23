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
from ..converters.asset_manager import AssetManager


class CanvasToIRConverter:
    """Convert Canvas course data to Intermediate Representation"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.url_gen = URLNameGenerator()
        self.qti_parser = QTIParser(verbose=verbose)
        self.capa_converter = QTIToCapaConverter(verbose=verbose)
        self.asset_manager = None  # Set during convert()
        self.skipped_items = []  # Track unsupported content
        self.timed_quizzes = []  # Track quizzes with time limits
        self.assignment_groups = {}  # Map identifier to group info
        self.identifier_to_url_name = {}  # Map Canvas identifiers to OLX url_names
        self.item_id_to_url_name = {}  # Map item identifier to url_name (avoids double-generation)
    
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
            print(" Converting to intermediate representation...")
        
        # Build assignment groups map
        for group in canvas_data.get('assignment_groups', []):
            self.assignment_groups[group['identifier']] = group
        
        # Build identifier to url_name map for internal link conversion
        self._build_identifier_map(canvas_data['modules'])
        
        # Pass the map to asset manager if available
        if self.asset_manager:
            self.asset_manager.identifier_to_url_name = self.identifier_to_url_name
        
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
        
        # Store assignment groups for grading policy generation
        course_ir.assignment_groups = canvas_data.get('assignment_groups', [])
        course_ir.group_weighting_scheme = canvas_data.get('group_weighting_scheme', '')
        
        # Get front page content for updates.html
        front_page_result = canvas_parser.get_front_page()
        if front_page_result:
            front_page_identifier, front_page_content = front_page_result
            # Convert URLs in front page content
            if self.asset_manager:
                front_page_content = self.asset_manager.convert_html_urls(front_page_content)
            course_ir.front_page_content = front_page_content
            if self.verbose:
                print("    Found front page for updates.html")
        
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
            print(f"    Converted {len(course_ir.chapters)} chapters")
        
        # Add Import Notes chapter if there are skipped items
        if self.skipped_items:
            notes_chapter = self._create_import_notes_chapter()
            course_ir.chapters.append(notes_chapter)
        
        return course_ir
    
    def _build_identifier_map(self, modules: List[Dict]):
        """Build map of Canvas identifiers to OLX url_names for internal link conversion.

        Also stores item identifier → url_name so that _convert_item_to_vertical
        can reuse the same url_name instead of generating a new (colliding) one.
        """
        self.identifier_to_url_name = {}
        self.item_id_to_url_name = {}

        for module in modules:
            for item in module.get('items', []):
                identifierref = item.get('identifierref')
                item_id = item.get('identifier')
                if identifierref:
                    # Generate the url_name once — reused later during conversion
                    url_name = self.url_gen.generate(item['title'])
                    self.identifier_to_url_name[identifierref] = url_name
                    if item_id:
                        self.item_id_to_url_name[item_id] = url_name
    
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
        
        # Check if module is published (active) or unpublished
        is_published = module['workflow_state'] == 'active'
        
        chapter = ChapterIR(
            display_name=module['title'],
            url_name=chapter_url_name,
            published=is_published,
            position=module['position']
        )
        
        # Create single sequential for module
        sequential = SequentialIR(
            display_name=module['title'],
            url_name=f"{chapter_url_name}_content",
            published=is_published,
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
                    print(f"     Error converting item '{item['title']}': {e}")
        
        chapter.sequentials.append(sequential)
        
        return chapter
    
    def _convert_item_to_vertical(
        self, 
        item: Dict, 
        canvas_parser
    ) -> Optional[VerticalIR]:
        """Convert Canvas module item to Vertical with components"""
        
        content_type = item['content_type']
        
        # Check if this is actually a quiz by looking for assessment_qti.xml
        identifier = item.get('identifierref')
        if identifier and content_type not in ['Quizzes::Quiz', 'WikiPage', 'Assignment']:
            qti_path = canvas_parser.extract_dir / identifier / "assessment_qti.xml"
            if qti_path.exists():
                content_type = 'Quizzes::Quiz'
        
        # Check if item is published (active) or unpublished
        is_published = item['workflow_state'] == 'active'
        
        # Reuse the url_name generated during _build_identifier_map to avoid
        # collisions from double-generating the same title
        item_id = item.get('identifier')
        if item_id and item_id in self.item_id_to_url_name:
            vert_url_name = self.item_id_to_url_name[item_id]
        else:
            vert_url_name = self.url_gen.generate(item['title'])

        vertical = VerticalIR(
            display_name=item['title'],
            url_name=vert_url_name,
            published=is_published
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
                # Append time limit hint to vertical title if this quiz is timed
                # (timed_quizzes list was just appended to by _convert_quiz)
                if self.timed_quizzes and self.timed_quizzes[-1]['title'] == item['title']:
                    tl = self.timed_quizzes[-1]['time_limit']
                    vertical.display_name = f"{vertical.display_name} ({tl} min time limit)"
        
        elif content_type == 'ContextExternalTool':
            # LTI tool - track as skipped
            self.skipped_items.append({
                'type': 'LTI Tool',
                'title': item['title'],
                'url': item.get('url', 'N/A')
            })

        elif content_type in ('DiscussionTopic', 'Discussion'):
            # Discussion topics cannot be auto-converted
            self.skipped_items.append({
                'type': 'Discussion Topic',
                'title': item['title'],
                'url': item.get('url', '')
            })

        elif content_type == 'ExternalUrl':
            # External URL links
            self.skipped_items.append({
                'type': 'External URL',
                'title': item['title'],
                'url': item.get('url', 'N/A')
            })

        else:
            # Any other unrecognized content type
            if content_type and content_type not in ('WikiPage', 'Assignment', 'Quizzes::Quiz'):
                self.skipped_items.append({
                    'type': content_type,
                    'title': item['title'],
                    'url': item.get('url', '')
                })

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
                print(f"     No content found for page: {item['title']}")
            return None
        
        # Extract body content
        soup = BeautifulSoup(html_content, 'html.parser')
        body = soup.find('body')
        
        if body:
            # Remove body tags, keep content
            content = ''.join(str(child) for child in body.children)
        else:
            content = html_content
        
        # Convert asset URLs if asset manager is available
        if self.asset_manager:
            content = self.asset_manager.convert_html_urls(content)
        
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
        """
        Convert assignment to appropriate OLX component.

        - online_text_entry → ORA (Open Response Assessment) with text input
        - online_upload → ORA with file upload enabled
        - online_text_entry,online_upload → ORA with both text and file upload
        - none / on_paper / external_tool / not_graded → HTML info block
        """

        identifier = item['identifierref']
        settings = canvas_parser.get_assignment_settings(identifier)

        if not settings:
            if self.verbose:
                print(f"     No settings found for assignment: {item['title']}")
            return None

        # Get assignment metadata
        points = settings.get('points_possible', 0)
        submission_types = settings.get('submission_types', '')
        grading_type = settings.get('grading_type', '')
        html_content = settings.get('html_content', '')

        # Convert asset URLs in the assignment content
        if html_content and self.asset_manager:
            html_content = self.asset_manager.convert_html_urls(html_content)

        # Determine if this can be an ORA component
        sub_types = [s.strip() for s in submission_types.split(',')] if submission_types else []
        has_text = 'online_text_entry' in sub_types
        has_upload = 'online_upload' in sub_types

        if has_text or has_upload:
            return self._convert_assignment_to_ora(item, settings, html_content, has_text, has_upload)
        else:
            return self._convert_assignment_to_html(item, settings, html_content)

    def _convert_assignment_to_ora(
        self,
        item: Dict,
        settings: Dict,
        html_content: str,
        has_text: bool,
        has_upload: bool
    ) -> ComponentIR:
        """Convert assignment to ORA component for text/upload submissions"""
        import xml.etree.ElementTree as ET
        from xml.dom import minidom

        title = item['title']
        points = settings.get('points_possible', 0)
        prompt_text = html_content if html_content else f'Please complete the assignment: {title}'

        # Strip HTML for the prompt (ORA prompts use plain text description)
        from bs4 import BeautifulSoup
        prompt_plain = BeautifulSoup(prompt_text, 'html.parser').get_text(separator='\n').strip()

        ora = ET.Element('openassessment')
        ora.set('submission_start', '2001-01-01T00:00')
        ora.set('submission_due', '2099-01-01T00:00')
        ora.set('display_name', title)
        ora.set('prompts_type', 'html')
        ora.set('teams_enabled', 'False')
        ora.set('show_rubric_during_response', 'False')
        ora.set('allow_learner_resubmissions', 'False')

        # Set response types based on submission types
        if has_text:
            ora.set('text_response', 'required')
            ora.set('text_response_editor', 'text')
        else:
            ora.set('text_response', 'optional')

        if has_upload:
            ora.set('file_upload_response', 'required' if not has_text else 'optional')
            ora.set('allow_multiple_files', 'True')
        else:
            ora.set('file_upload_response', 'none')

        ora.set('allow_latex', 'False')

        # Title
        title_elem = ET.SubElement(ora, 'title')
        title_elem.text = title

        # Assessments - staff assessment only for imported assignments
        assessments = ET.SubElement(ora, 'assessments')
        staff = ET.SubElement(assessments, 'assessment')
        staff.set('name', 'staff-assessment')
        staff.set('start', '2001-01-01T00:00')
        staff.set('due', '2099-01-01T00:00')
        staff.set('required', 'True')

        # Prompts - use HTML prompt to preserve formatting
        prompts = ET.SubElement(ora, 'prompts')
        prompt = ET.SubElement(prompts, 'prompt')
        description = ET.SubElement(prompt, 'description')
        description.text = prompt_plain

        # Rubric with points based on Canvas assignment points
        rubric = ET.SubElement(ora, 'rubric')
        criterion = ET.SubElement(rubric, 'criterion')
        criterion.set('feedback', 'optional')

        criterion_name = ET.SubElement(criterion, 'name')
        criterion_name.text = 'Overall Quality'
        criterion_label = ET.SubElement(criterion, 'label')
        criterion_label.text = 'Overall Quality'
        criterion_prompt = ET.SubElement(criterion, 'prompt')
        criterion_prompt.text = 'Evaluate the overall quality of the submission.'

        # Scale rubric options to match Canvas point value
        max_points = int(points) if points else 3
        if max_points <= 0:
            max_points = 3

        # Create 4-point scale mapped to Canvas points
        scale = [
            (0, 'Incomplete', 'Submission does not address the requirements.'),
            (max(1, max_points // 3), 'Developing', 'Submission partially meets requirements.'),
            (max(2, (max_points * 2) // 3), 'Proficient', 'Submission meets requirements.'),
            (max_points, 'Exemplary', 'Submission exceeds requirements.'),
        ]

        for pts, label, explanation in scale:
            option = ET.SubElement(criterion, 'option')
            option.set('points', str(pts))
            opt_name = ET.SubElement(option, 'name')
            opt_name.text = label
            opt_label = ET.SubElement(option, 'label')
            opt_label.text = label
            opt_exp = ET.SubElement(option, 'explanation')
            opt_exp.text = explanation

        feedback_prompt = ET.SubElement(rubric, 'feedbackprompt')
        feedback_prompt.text = '(Optional) Provide additional feedback.'
        feedback_default = ET.SubElement(rubric, 'feedback_default_text')
        feedback_default.text = ''

        # Prettify
        rough = ET.tostring(ora, encoding='unicode')
        try:
            reparsed = minidom.parseString(rough)
            pretty = reparsed.toprettyxml(indent="  ")
            lines = [l for l in pretty.split('\n') if l.strip() and not l.startswith('<?xml')]
            content = '\n'.join(lines)
        except Exception:
            content = rough

        if self.verbose:
            sub_desc = []
            if has_text:
                sub_desc.append('text')
            if has_upload:
                sub_desc.append('file upload')
            print(f"    Assignment '{title}' -> ORA ({', '.join(sub_desc)})")

        return ComponentIR(
            type='openassessment',
            display_name=title,
            url_name=self.url_gen.generate(f"{title}_assignment"),
            content=content,
            settings=settings,
            canvas_source=item
        )

    def _convert_assignment_to_html(
        self,
        item: Dict,
        settings: Dict,
        html_content: str
    ) -> ComponentIR:
        """Convert non-submittable assignment to HTML info block"""
        points = settings.get('points_possible', 0)
        submission_types = settings.get('submission_types', '')
        grading_type = settings.get('grading_type', '')

        submission_display = submission_types.replace(',', ', ').replace('_', ' ') if submission_types else 'Not specified'
        grading_display = grading_type.replace('_', ' ').title() if grading_type else 'Not specified'

        content_parts = []

        content_parts.append(f'''<div class="assignment-info" style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
    <p><strong>Assignment:</strong> {item['title']}</p>
    <p><strong>Points Possible:</strong> {points}</p>
    <p><strong>Submission Type:</strong> {submission_display}</p>
    <p><strong>Grading Type:</strong> {grading_display}</p>
</div>''')

        if html_content:
            content_parts.append(f'<div class="assignment-content">\n{html_content}\n</div>')

        content_parts.append('''<div class="assignment-note" style="background: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 20px; border: 1px solid #ffc107;">
    <p><em>Note: This assignment was imported from Canvas. Submission type is not online — configure grading manually in Open edX.</em></p>
</div>''')

        full_content = '\n'.join(content_parts)

        return ComponentIR(
            type='html',
            display_name=item['title'],
            url_name=self.url_gen.generate(f"{item['title']}_assignment"),
            content=full_content,
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
                print(f"     No QTI file found for quiz: {item['title']}")
            return []
        
        # Parse QTI
        quiz_data = self.qti_parser.parse_quiz(qti_path)
        
        if not quiz_data or not quiz_data.get('questions'):
            if self.verbose:
                print(f"     No questions found in quiz: {item['title']}")
            return []
        
        # Get quiz-level metadata from assessment_meta.xml
        meta_path = canvas_parser.extract_dir / identifier / "assessment_meta.xml"
        quiz_settings = self._parse_assessment_meta(meta_path)

        # Convert each question to a component
        components = []
        failed_questions = 0

        for i, question in enumerate(quiz_data['questions'], 1):
            try:
                # Convert to CAPA/ORA/HTML - returns (content, component_type)
                content, component_type = self.capa_converter.convert_question(question)

                # Apply quiz-level settings to problem components
                settings = {}
                if component_type == 'problem' and quiz_settings:
                    if quiz_settings.get('max_attempts'):
                        settings['max_attempts'] = quiz_settings['max_attempts']
                    if quiz_settings.get('show_correct_answers'):
                        settings['showanswer'] = 'finished'
                    else:
                        settings['showanswer'] = 'never'
                    if question.get('points'):
                        settings['weight'] = question['points']

                # Create component with appropriate type
                component = ComponentIR(
                    type=component_type,
                    display_name=question.get('title') or f"Question {i}",
                    url_name=self.url_gen.generate(f"{item['title']}_q{i}"),
                    content=content,
                    settings=settings,
                    canvas_source=item
                )
                components.append(component)
            except Exception as e:
                failed_questions += 1
                if self.verbose:
                    print(f"     WARNING: Failed to convert question {i} in '{item['title']}': {e}")

        # Track timed quizzes for the conversion report
        time_limit = quiz_settings.get('time_limit')
        if time_limit and time_limit > 0:
            self.timed_quizzes.append({
                'title': item['title'],
                'time_limit': time_limit,
                'quiz_type': quiz_settings.get('quiz_type', 'assignment'),
                'questions': len(components),
            })

        if self.verbose:
            msg = f"    Converted quiz '{item['title']}': {len(components)} questions"
            if failed_questions:
                msg += f" ({failed_questions} failed)"
            if time_limit:
                msg += f" (time limit: {time_limit} min)"
            print(msg)

        return components
    
    def _parse_assessment_meta(self, meta_path) -> Dict:
        """Parse assessment_meta.xml for quiz-level settings"""
        from pathlib import Path
        meta_path = Path(meta_path)

        if not meta_path.exists():
            return {}

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(meta_path)
            root = tree.getroot()

            ns = {'cc': 'http://canvas.instructure.com/xsd/cccv1p0'}

            def get_text(tag):
                for prefix, uri in ns.items():
                    child = root.find(f'{{{uri}}}{tag}')
                    if child is not None and child.text:
                        return child.text
                child = root.find(tag)
                return child.text if child is not None and child.text else ''

            settings = {}

            # Time limit (Canvas stores in minutes)
            time_limit = get_text('time_limit')
            if time_limit:
                try:
                    settings['time_limit'] = int(float(time_limit))
                except (ValueError, TypeError):
                    pass

            # Allowed attempts
            allowed_attempts = get_text('allowed_attempts')
            if allowed_attempts:
                try:
                    attempts = int(allowed_attempts)
                    # Canvas uses -1 for unlimited
                    if attempts > 0:
                        settings['max_attempts'] = attempts
                except (ValueError, TypeError):
                    pass

            # Scoring policy (keep_highest, keep_latest, keep_average)
            scoring_policy = get_text('scoring_policy')
            if scoring_policy:
                settings['scoring_policy'] = scoring_policy

            # Show correct answers
            show_correct = get_text('show_correct_answers')
            settings['show_correct_answers'] = show_correct == 'true'

            # Points possible
            points = get_text('points_possible')
            if points:
                try:
                    settings['points_possible'] = float(points)
                except (ValueError, TypeError):
                    pass

            # Quiz type
            quiz_type = get_text('quiz_type')
            if quiz_type:
                settings['quiz_type'] = quiz_type

            if self.verbose and settings:
                print(f"    Quiz settings: {settings}")

            return settings

        except Exception as e:
            if self.verbose:
                print(f"     WARNING: Failed to parse assessment_meta.xml: {e}")
            return {}

    def _create_import_notes_chapter(self) -> ChapterIR:
        """Create Import Notes chapter with unsupported content report"""
        chapter = ChapterIR(
            display_name="Import Notes",
            url_name=self.url_gen.generate("import_notes"),
            published=True
        )
        
        sequential = SequentialIR(
            display_name="Unsupported Content",
            url_name=self.url_gen.generate("unsupported_content"),
            published=True
        )
        
        vertical = VerticalIR(
            display_name="Items Requiring Manual Review",
            url_name=self.url_gen.generate("manual_review"),
            published=True
        )
        
        # Build HTML report
        html_content = '<h2>Unsupported Content</h2>\n'
        html_content += '<p>The following items could not be automatically converted and require manual setup in Open edX:</p>\n\n'
        
        # Group by type
        by_type = {}
        for item in self.skipped_items:
            item_type = item['type']
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append(item)
        
        # Generate report by type
        for item_type, items in sorted(by_type.items()):
            html_content += f'<h3>{item_type}s</h3>\n<ul>\n'
            for item in items:
                html_content += f'  <li><strong>{item["title"]}</strong>'
                if item.get('url'):
                    html_content += f'<br/>URL: {item["url"]}'
                html_content += '</li>\n'
            html_content += '</ul>\n\n'
        
        html_content += '<p><em>These items have been skipped during conversion. Please recreate them manually in Open edX Studio.</em></p>'
        
        component = ComponentIR(
            type='html',
            display_name='Unsupported Items Report',
            url_name=self.url_gen.generate('unsupported_report'),
            content=html_content
        )
        
        vertical.components.append(component)
        sequential.verticals.append(vertical)
        chapter.sequentials.append(sequential)
        
        return chapter
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string"""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None
