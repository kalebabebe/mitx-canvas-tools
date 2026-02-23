"""
Open edX OLX Generator

Generates Open edX OLX course structure from Intermediate Representation.
"""

from pathlib import Path
from typing import Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json

from ..models.intermediate_rep import (
    CourseIR, ChapterIR, SequentialIR, VerticalIR, ComponentIR
)


class OLXGenerator:
    """Generate Open edX OLX from Intermediate Representation"""
    
    def __init__(self, output_dir: str, verbose: bool = False):
        self.output_dir = Path(output_dir)
        self.verbose = verbose
    
    def generate(self, course_ir: CourseIR):
        """
        Generate complete OLX structure
        
        Args:
            course_ir: Course intermediate representation
        """
        if self.verbose:
            print(f" Generating OLX in {self.output_dir}...")
        
        # Create directory structure
        self._create_directories()
        
        # Generate course files
        self._generate_course_xml(course_ir)
        self._generate_course_definition(course_ir)
        
        # Generate chapters
        failed_chapters = []
        for chapter in course_ir.chapters:
            try:
                self._generate_chapter(chapter)
            except Exception as e:
                failed_chapters.append(chapter.url_name)
                if self.verbose:
                    print(f"    WARNING: Failed to generate chapter '{chapter.display_name}': {e}")

        # Validate: check that all referenced chapter files exist
        self._validate_chapter_files(course_ir, failed_chapters)
        
        # Generate policies
        self._generate_policies(course_ir)
        
        # Generate about page
        self._generate_about_page(course_ir)
        
        # Generate info/updates from front page
        self._generate_info_updates(course_ir)
        
        # Generate assets.xml
        self._generate_assets_xml()
        
        if self.verbose:
            print(f"    OLX generated successfully")
    
    def _create_directories(self):
        """Create OLX directory structure"""
        dirs = [
            'course',
            'chapter',
            'sequential',
            'vertical',
            'html',
            'problem',
            'openassessment',
            'video',
            'static',
            'policies',
            'about',
            'info',
            'assets',
            'drafts',
        ]
        
        for dir_name in dirs:
            (self.output_dir / dir_name).mkdir(parents=True, exist_ok=True)
    
    def _generate_course_xml(self, course_ir: CourseIR):
        """Generate root course.xml pointer"""
        course_xml = f'<course url_name="{course_ir.run}" org="{course_ir.org}" course="{course_ir.course}"/>'
        
        output_file = self.output_dir / 'course.xml'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(course_xml))
    
    def _generate_course_definition(self, course_ir: CourseIR):
        """Generate course/{run}.xml with metadata"""
        
        # Build course element
        course_elem = ET.Element('course')
        course_elem.set('display_name', course_ir.title)
        course_elem.set('language', course_ir.language)
        course_elem.set('self_paced', str(course_ir.self_paced).lower())
        
        if course_ir.start_date:
            course_elem.set('start', course_ir.start_date.isoformat())
        
        # Add chapters
        for chapter in course_ir.chapters:
            chapter_ref = ET.SubElement(course_elem, 'chapter')
            chapter_ref.set('url_name', chapter.url_name)
        
        # Add wiki
        wiki = ET.SubElement(course_elem, 'wiki')
        wiki.set('slug', f"{course_ir.org}.{course_ir.course}.{course_ir.run}")
        
        # Write file
        xml_str = ET.tostring(course_elem, encoding='unicode')
        output_file = self.output_dir / 'course' / f'{course_ir.run}.xml'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(xml_str))
    
    def _generate_chapter(self, chapter: ChapterIR):
        """Generate chapter XML file"""
        
        chapter_elem = ET.Element('chapter')
        chapter_elem.set('display_name', chapter.display_name)
        
        if not chapter.published:
            chapter_elem.set('visible_to_staff_only', 'true')
        
        # Add sequentials
        for sequential in chapter.sequentials:
            self._generate_sequential(sequential)
            
            seq_ref = ET.SubElement(chapter_elem, 'sequential')
            seq_ref.set('url_name', sequential.url_name)
        
        # Write file
        xml_str = ET.tostring(chapter_elem, encoding='unicode')
        output_file = self.output_dir / 'chapter' / f'{chapter.url_name}.xml'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(xml_str))
    
    def _generate_sequential(self, sequential: SequentialIR):
        """Generate sequential XML file"""
        
        seq_elem = ET.Element('sequential')
        seq_elem.set('display_name', sequential.display_name)
        
        if sequential.prereq:
            seq_elem.set('prereq', sequential.prereq)
        
        if not sequential.published:
            seq_elem.set('visible_to_staff_only', 'true')
        
        # Add verticals
        for vertical in sequential.verticals:
            self._generate_vertical(vertical)
            
            vert_ref = ET.SubElement(seq_elem, 'vertical')
            vert_ref.set('url_name', vertical.url_name)
        
        # Write file
        xml_str = ET.tostring(seq_elem, encoding='unicode')
        output_file = self.output_dir / 'sequential' / f'{sequential.url_name}.xml'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(xml_str))
    
    def _generate_vertical(self, vertical: VerticalIR):
        """Generate vertical XML file"""

        vert_elem = ET.Element('vertical')
        vert_elem.set('display_name', vertical.display_name)

        # Handle unpublished verticals
        if not vertical.published:
            vert_elem.set('visible_to_staff_only', 'true')

        # Add components - continue even if individual components fail
        for component in vertical.components:
            try:
                self._generate_component(component)

                comp_ref = ET.SubElement(vert_elem, component.type)
                comp_ref.set('url_name', component.url_name)
            except Exception as e:
                if self.verbose:
                    print(f"    WARNING: Failed to generate component '{component.display_name}': {e}")

        # Write file
        xml_str = ET.tostring(vert_elem, encoding='unicode')
        output_file = self.output_dir / 'vertical' / f'{vertical.url_name}.xml'

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(xml_str))
    
    def _generate_component(self, component: ComponentIR):
        """Generate component files"""
        
        if component.type == 'html':
            self._generate_html_component(component)
        elif component.type == 'problem':
            self._generate_problem_component(component)
        elif component.type == 'openassessment':
            self._generate_ora_component(component)
    
    def _generate_html_component(self, component: ComponentIR):
        """Generate HTML component (XML + HTML file)"""
        
        # Generate XML metadata
        html_elem = ET.Element('html')
        html_elem.set('display_name', component.display_name)
        html_elem.set('filename', component.url_name)
        
        xml_str = ET.tostring(html_elem, encoding='unicode')
        xml_file = self.output_dir / 'html' / f'{component.url_name}.xml'
        
        with open(xml_file, 'w', encoding='utf-8') as f:
            f.write(self._prettify_xml(xml_str))
        
        # Generate HTML content file
        html_file = self.output_dir / 'html' / f'{component.url_name}.html'
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(component.content)
    
    def _generate_problem_component(self, component: ComponentIR):
        """Generate problem component with optional settings"""

        content = component.content

        # Inject quiz-level settings into the <problem> tag if available
        settings = component.settings or {}
        if settings:
            attrs = []
            if settings.get('max_attempts'):
                attrs.append(f'max_attempts="{settings["max_attempts"]}"')
            if settings.get('showanswer'):
                attrs.append(f'showanswer="{settings["showanswer"]}"')
            if settings.get('weight'):
                attrs.append(f'weight="{settings["weight"]}"')

            if attrs:
                attrs_str = ' ' + ' '.join(attrs)
                # Insert attributes into existing <problem> tag
                content = content.replace('<problem>', f'<problem{attrs_str}>', 1)

        problem_file = self.output_dir / 'problem' / f'{component.url_name}.xml'
        with open(problem_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_ora_component(self, component: ComponentIR):
        """Generate Open Response Assessment (ORA) component"""
        
        # ORA components are stored as XML files
        ora_file = self.output_dir / 'openassessment' / f'{component.url_name}.xml'
        with open(ora_file, 'w', encoding='utf-8') as f:
            f.write(component.content)
    
    def _generate_policies(self, course_ir: CourseIR):
        """Generate policy files including grading policy from Canvas assignment groups"""
        
        # Create policy directory
        policy_dir = self.output_dir / 'policies' / course_ir.run
        policy_dir.mkdir(parents=True, exist_ok=True)
        
        # Build grading policy from Canvas assignment groups
        grading_policy = self._build_grading_policy(course_ir)
        
        with open(policy_dir / 'grading_policy.json', 'w') as f:
            json.dump(grading_policy, f, indent=4)
        
        # Build policy.json with course settings
        policy = {
            f"course/{course_ir.run}": {
                "display_name": course_ir.title,
                "language": course_ir.language,
                "self_paced": course_ir.self_paced,
                "tabs": [
                    {"course_staff_only": False, "name": "Course", "type": "courseware"},
                    {"course_staff_only": False, "name": "Progress", "type": "progress"},
                    {"course_staff_only": False, "name": "Dates", "type": "dates"},
                    {"course_staff_only": False, "name": "Discussion", "type": "discussion"},
                    {"course_staff_only": False, "is_hidden": True, "name": "Wiki", "type": "wiki"},
                ]
            }
        }
        
        with open(policy_dir / 'policy.json', 'w') as f:
            json.dump(policy, f, indent=4)
    
    def _build_grading_policy(self, course_ir: CourseIR) -> Dict:
        """Build grading policy from Canvas assignment groups"""
        
        grader = []
        
        # Check if we have assignment groups with weights
        assignment_groups = getattr(course_ir, 'assignment_groups', [])
        group_weighting = getattr(course_ir, 'group_weighting_scheme', '')
        
        if assignment_groups and group_weighting == 'percent':
            # Use Canvas assignment groups with weights
            for group in assignment_groups:
                weight = group.get('group_weight', 0)
                if weight > 0:  # Only include groups with non-zero weight
                    # Convert Canvas group name to Open edX format
                    title = group.get('title', 'Homework')
                    short_label = self._make_short_label(title)
                    
                    grader.append({
                        "drop_count": 0,
                        "min_count": 1,
                        "short_label": short_label,
                        "type": title,
                        "weight": weight / 100.0  # Canvas uses percentage, Open edX uses decimal
                    })
        
        # If no valid groups or no weighting, use default
        if not grader:
            grader = [
                {
                    "drop_count": 0,
                    "min_count": 1,
                    "short_label": "HW",
                    "type": "Homework",
                    "weight": 1.0
                }
            ]
        
        return {
            "GRADER": grader,
            "GRADE_CUTOFFS": {
                "Pass": 0.5
            }
        }
    
    def _make_short_label(self, title: str) -> str:
        """Create a short label from assignment group title"""
        # Take first letters of each word, up to 3 characters
        words = title.split()
        if len(words) == 1:
            return title[:3].upper()
        else:
            return ''.join(word[0] for word in words[:3]).upper()
    
    def _generate_about_page(self, course_ir: CourseIR):
        """Generate about/overview.html"""
        
        overview_content = f'''<section class="about">
  <h2>About This Course</h2>
  <p>{course_ir.title}</p>
  <p>This course was imported from Canvas LMS.</p>
</section>

<section class="prerequisites">
  <h2>Requirements</h2>
  <p>Please check with your instructor for specific course requirements.</p>
</section>

<section class="course-staff">
  <h2>Course Staff</h2>
  <article class="teacher">
    <h3>Instructor</h3>
    <p>Contact your course instructor for more information.</p>
  </article>
</section>
'''
        
        about_file = self.output_dir / 'about' / 'overview.html'
        with open(about_file, 'w', encoding='utf-8') as f:
            f.write(overview_content)
    
    def _generate_info_updates(self, course_ir: CourseIR = None):
        """Generate info/updates.html from Canvas front page if available"""
        
        if course_ir and course_ir.front_page_content:
            # Use Canvas front page content wrapped in update format
            # The <ol> with <li> items is the expected format for updates
            updates_content = f'''<ol>
<li>
<h2>Welcome</h2>
{course_ir.front_page_content}
</li>
</ol>'''
        else:
            updates_content = '<ol></ol>'
        
        updates_file = self.output_dir / 'info' / 'updates.html'
        with open(updates_file, 'w', encoding='utf-8') as f:
            f.write(updates_content)
    
    def _generate_assets_xml(self):
        """Generate assets/assets.xml"""
        
        assets_content = '<assets/>'
        
        assets_file = self.output_dir / 'assets' / 'assets.xml'
        with open(assets_file, 'w', encoding='utf-8') as f:
            f.write(assets_content)
    
    def _validate_chapter_files(self, course_ir: CourseIR, failed_chapters: list):
        """Validate that all chapters referenced in course definition have files"""
        chapter_dir = self.output_dir / 'chapter'
        missing = []
        for chapter in course_ir.chapters:
            chapter_file = chapter_dir / f'{chapter.url_name}.xml'
            if not chapter_file.exists():
                missing.append(chapter)

        if missing:
            print(f"    WARNING: {len(missing)} chapter(s) referenced in course.xml but missing files:")
            for chapter in missing:
                print(f"      - {chapter.display_name} ({chapter.url_name})")

            # Attempt to write empty chapter files so imports don't break
            for chapter in missing:
                try:
                    chapter_elem = ET.Element('chapter')
                    chapter_elem.set('display_name', chapter.display_name)
                    chapter_elem.set('visible_to_staff_only', 'true')
                    # Add a note about the generation failure
                    xml_str = ET.tostring(chapter_elem, encoding='unicode')
                    output_file = chapter_dir / f'{chapter.url_name}.xml'
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(self._prettify_xml(xml_str))
                    print(f"      -> Created placeholder for: {chapter.display_name}")
                except Exception as e:
                    print(f"      -> Failed to create placeholder: {e}")

    def _prettify_xml(self, xml_string: str) -> str:
        """Prettify XML string"""
        try:
            dom = minidom.parseString(xml_string)
            return dom.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')
        except:
            # If parsing fails, return original
            return xml_string
