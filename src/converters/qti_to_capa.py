"""
QTI to CAPA Converter

Converts QTI quiz questions to Open edX CAPA (Computer-Aided Personalized Approach) format.
Supports multiple choice, true/false, multiple response questions.
"""

from typing import Dict, List
import xml.etree.ElementTree as ET
from xml.dom import minidom


class QTIToCapaConverter:
    """Convert QTI questions to CAPA XML"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def convert_question(self, question: Dict) -> str:
        """
        Convert a single QTI question to CAPA XML
        
        Args:
            question: Parsed question dictionary from QTIParser
            
        Returns:
            CAPA XML string
        """
        q_type = question.get('type', 'unknown')
        
        if q_type == 'multiple_choice':
            return self._convert_multiple_choice(question)
        elif q_type == 'true_false':
            return self._convert_true_false(question)
        elif q_type == 'multiple_response':
            return self._convert_multiple_response(question)
        elif q_type == 'short_answer':
            return self._convert_short_answer(question)
        elif q_type == 'numerical':
            return self._convert_numerical(question)
        elif q_type == 'essay':
            return self._convert_essay(question)
        else:
            if self.verbose:
                print(f"   ⚠️  Unsupported question type: {q_type}")
            return self._convert_unsupported(question)
    
    def _convert_multiple_choice(self, question: Dict) -> str:
        """Convert multiple choice question to CAPA"""
        # Build problem XML
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Create multiplechoiceresponse
        mc_response = ET.SubElement(problem, 'multiplechoiceresponse')
        
        # Add choices
        choice_group = ET.SubElement(mc_response, 'choicegroup', type='MultipleChoice')
        
        correct_ids = question.get('correct_answers', [])
        
        for choice in question['choices']:
            is_correct = choice['id'] in correct_ids
            choice_elem = ET.SubElement(
                choice_group, 
                'choice',
                correct='true' if is_correct else 'false'
            )
            choice_elem.text = choice['text']
        
        return self._prettify_xml(problem)
    
    def _convert_true_false(self, question: Dict) -> str:
        """Convert true/false question to CAPA"""
        # True/false is just a special case of multiple choice
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Create multiplechoiceresponse
        mc_response = ET.SubElement(problem, 'multiplechoiceresponse')
        
        # Add True/False choices
        choice_group = ET.SubElement(mc_response, 'choicegroup', type='MultipleChoice')
        
        correct_ids = question.get('correct_answers', [])
        
        for choice in question['choices']:
            is_correct = choice['id'] in correct_ids
            choice_elem = ET.SubElement(
                choice_group,
                'choice',
                correct='true' if is_correct else 'false'
            )
            choice_elem.text = choice['text']
        
        return self._prettify_xml(problem)
    
    def _convert_multiple_response(self, question: Dict) -> str:
        """Convert multiple response (checkbox) question to CAPA"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Create choiceresponse
        choice_response = ET.SubElement(problem, 'choiceresponse')
        
        # Add choices
        checkboxgroup = ET.SubElement(choice_response, 'checkboxgroup')
        
        correct_ids = question.get('correct_answers', [])
        
        for choice in question['choices']:
            is_correct = choice['id'] in correct_ids
            choice_elem = ET.SubElement(
                checkboxgroup,
                'choice',
                correct='true' if is_correct else 'false'
            )
            choice_elem.text = choice['text']
        
        return self._prettify_xml(problem)
    
    def _convert_short_answer(self, question: Dict) -> str:
        """Convert short answer/fill-in-blank to CAPA stringresponse"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Get correct answers
        answers = question.get('correct_answers', [])
        if not answers:
            # No correct answer specified - treat as essay
            return self._convert_essay(question)
        
        # Create stringresponse (case insensitive by default)
        string_resp = ET.SubElement(
            problem,
            'stringresponse',
            answer=answers[0],
            type='ci'  # Case insensitive
        )
        
        # Add additional acceptable answers
        for answer in answers[1:]:
            ET.SubElement(string_resp, 'additional_answer', answer=answer)
        
        # Add text input
        ET.SubElement(string_resp, 'textline', size='20')
        
        return self._prettify_xml(problem)
    
    def _convert_numerical(self, question: Dict) -> str:
        """Convert numerical question to CAPA numericalresponse"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Get answer and tolerance
        answers = question.get('correct_answers', [])
        if not answers:
            # No answer - create placeholder
            note = ET.SubElement(problem, 'p')
            note.text = "[No correct answer specified for numerical question]"
            return self._prettify_xml(problem)
        
        # Create numericalresponse
        num_resp = ET.SubElement(
            problem,
            'numericalresponse',
            answer=str(answers[0])
        )
        
        # Add tolerance if specified
        tolerance = question.get('tolerance')
        if tolerance is not None:
            # Add as responseparam
            ET.SubElement(
                num_resp,
                'responseparam',
                type='tolerance',
                default=str(tolerance)
            )
        
        # Add text input (formulaequationinput for numerical)
        ET.SubElement(num_resp, 'formulaequationinput')
        
        return self._prettify_xml(problem)
    
    def _convert_essay(self, question: Dict) -> str:
        """Convert essay question to note (manually graded)"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Add note about manual grading
        note = ET.SubElement(problem, 'p')
        note.text = "[This is an essay question that requires manual grading in Canvas. Consider using Open edX's manual grading features or converting to a different question type.]"
        
        return self._prettify_xml(problem)
    
    def _convert_unsupported(self, question: Dict) -> str:
        """Create placeholder for unsupported question types"""
        problem = ET.Element('problem')
        
        # Add note about unsupported type
        note = ET.SubElement(problem, 'p')
        note.text = f"[Question type '{question.get('type', 'unknown')}' not yet supported]"
        
        # Add question text if available
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Show choices if available
        if question.get('choices'):
            choices_elem = ET.SubElement(problem, 'p')
            choices_text = "Choices:\n"
            for i, choice in enumerate(question['choices'], 1):
                choices_text += f"{i}. {choice['text']}\n"
            choices_elem.text = choices_text
        
        return self._prettify_xml(problem)
    
    def _strip_html_tags(self, html: str) -> str:
        """Remove HTML tags from text, keeping content"""
        if not html:
            return ''
        
        # Simple HTML tag removal - for basic cases
        # For more complex HTML, we'd want to use BeautifulSoup
        import re
        
        # Remove <div> and <p> tags but keep content
        text = re.sub(r'<div[^>]*>', '', html)
        text = re.sub(r'</div>', '', text)
        text = re.sub(r'<p[^>]*>', '', text)
        text = re.sub(r'</p>', '\n', text)
        
        # Remove any remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up whitespace
        text = text.strip()
        
        return text
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """Convert XML element to pretty-printed string"""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        pretty = reparsed.toprettyxml(indent="  ")
        
        # Remove XML declaration and extra blank lines
        lines = [line for line in pretty.split('\n') 
                if line.strip() and not line.startswith('<?xml')]
        
        return '\n'.join(lines)
