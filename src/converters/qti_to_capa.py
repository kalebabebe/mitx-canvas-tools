"""
QTI to CAPA Converter

Converts QTI quiz questions to Open edX CAPA (Computer-Aided Personalized Approach) format.
Supports multiple choice, true/false, multiple response, matching, dropdowns,
fill-in-multiple-blanks, numerical, calculated, essay (ORA), and more.
"""

from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom
import re


class QTIToCapaConverter:
    """Convert QTI questions to CAPA XML"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def convert_question(self, question: Dict) -> Tuple[str, str]:
        """
        Convert a single QTI question to CAPA XML or ORA XML
        
        Args:
            question: Parsed question dictionary from QTIParser
            
        Returns:
            Tuple of (xml_content, component_type) where component_type is 'problem' or 'openassessment' or 'html'
        """
        q_type = question.get('type', 'unknown')
        
        if q_type == 'multiple_choice':
            return self._convert_multiple_choice(question), 'problem'
        elif q_type == 'true_false':
            return self._convert_true_false(question), 'problem'
        elif q_type == 'multiple_response':
            return self._convert_multiple_response(question), 'problem'
        elif q_type == 'short_answer':
            return self._convert_short_answer(question), 'problem'
        elif q_type == 'numerical':
            return self._convert_numerical(question), 'problem'
        elif q_type == 'essay':
            return self._convert_essay_ora(question), 'openassessment'
        elif q_type == 'matching_question':
            return self._convert_matching(question), 'problem'
        elif q_type == 'fill_in_multiple_blanks_question':
            return self._convert_fill_in_multiple_blanks(question), 'problem'
        elif q_type == 'multiple_dropdowns_question':
            return self._convert_multiple_dropdowns(question), 'problem'
        elif q_type == 'calculated_question':
            return self._convert_calculated(question), 'problem'
        elif q_type == 'file_upload_question':
            return self._convert_file_upload(question), 'problem'
        elif q_type == 'text_only_question':
            return self._convert_text_only(question), 'html'
        else:
            if self.verbose:
                print(f"   ⚠️  Unsupported question type: {q_type}")
            return self._convert_unsupported(question), 'problem'
    
    def _convert_multiple_choice(self, question: Dict) -> str:
        """Convert multiple choice question to CAPA"""
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
            # No correct answer specified - create ORA instead
            return self._convert_essay_ora(question)
        
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
            ET.SubElement(
                num_resp,
                'responseparam',
                type='tolerance',
                default=str(tolerance)
            )
        
        # Add text input
        ET.SubElement(num_resp, 'formulaequationinput')
        
        return self._prettify_xml(problem)
    
    def _convert_essay_ora(self, question: Dict) -> str:
        """Convert essay question to Open Response Assessment (ORA)"""
        # Clean and prepare the prompt text
        prompt_text = self._strip_html_tags(question.get('question_text', 'Please provide your response.'))
        title = question.get('title', 'Essay Question')
        
        # Build ORA XML
        ora = ET.Element('openassessment')
        ora.set('url_name', question.get('identifier', 'essay')[:32])
        ora.set('submission_start', '2001-01-01T00:00')
        ora.set('submission_due', '2099-01-01T00:00')
        ora.set('text_response', 'required')
        ora.set('text_response_editor', 'text')
        ora.set('allow_multiple_files', 'False')
        ora.set('allow_latex', 'False')
        ora.set('allow_learner_resubmissions', 'False')
        ora.set('display_name', title)
        ora.set('prompts_type', 'text')
        ora.set('teams_enabled', 'False')
        ora.set('show_rubric_during_response', 'False')
        
        # Add title
        title_elem = ET.SubElement(ora, 'title')
        title_elem.text = title
        
        # Add assessments - staff assessment only for imported essays
        assessments = ET.SubElement(ora, 'assessments')
        staff_assessment = ET.SubElement(assessments, 'assessment')
        staff_assessment.set('name', 'staff-assessment')
        staff_assessment.set('start', '2001-01-01T00:00')
        staff_assessment.set('due', '2099-01-01T00:00')
        staff_assessment.set('required', 'True')
        
        # Add prompts
        prompts = ET.SubElement(ora, 'prompts')
        prompt = ET.SubElement(prompts, 'prompt')
        description = ET.SubElement(prompt, 'description')
        description.text = prompt_text
        
        # Add a basic rubric
        rubric = ET.SubElement(ora, 'rubric')
        
        # Single criterion for basic grading
        criterion = ET.SubElement(rubric, 'criterion')
        criterion.set('feedback', 'optional')
        
        criterion_name = ET.SubElement(criterion, 'name')
        criterion_name.text = 'Response Quality'
        criterion_label = ET.SubElement(criterion, 'label')
        criterion_label.text = 'Response Quality'
        criterion_prompt = ET.SubElement(criterion, 'prompt')
        criterion_prompt.text = 'Evaluate the overall quality of the response.'
        
        # Add grading options
        for points, label, explanation in [
            (0, 'Incomplete', 'Response does not address the prompt or is missing.'),
            (1, 'Developing', 'Response partially addresses the prompt but needs improvement.'),
            (2, 'Proficient', 'Response adequately addresses the prompt.'),
            (3, 'Exemplary', 'Response thoroughly and effectively addresses the prompt.')
        ]:
            option = ET.SubElement(criterion, 'option')
            option.set('points', str(points))
            opt_name = ET.SubElement(option, 'name')
            opt_name.text = label
            opt_label = ET.SubElement(option, 'label')
            opt_label.text = label
            opt_exp = ET.SubElement(option, 'explanation')
            opt_exp.text = explanation
        
        # Add feedback prompt
        feedback_prompt = ET.SubElement(rubric, 'feedbackprompt')
        feedback_prompt.text = '(Optional) Provide additional feedback on this response.'
        
        feedback_default = ET.SubElement(rubric, 'feedback_default_text')
        feedback_default.text = ''
        
        return self._prettify_xml(ora)
    
    def _convert_matching(self, question: Dict) -> str:
        """Convert matching question to multiple dropdown questions"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Each match becomes a dropdown
        for blank in question.get('blanks', []):
            prompt = blank.get('prompt', '')
            choices = blank.get('choices', [])
            correct_id = blank.get('correct_answer')
            
            if not choices:
                continue
            
            # Find correct answer text
            correct_text = None
            option_texts = []
            for choice in choices:
                option_texts.append(choice['text'])
                if choice['id'] == correct_id:
                    correct_text = choice['text']
            
            if not correct_text and option_texts:
                correct_text = option_texts[0]
            
            # Create label for this match
            label_elem = ET.SubElement(problem, 'p')
            label_elem.text = f"Match: {prompt}"
            
            # Create optionresponse
            option_resp = ET.SubElement(problem, 'optionresponse')
            
            # Build options string
            options_str = str(tuple(option_texts))
            
            optioninput = ET.SubElement(option_resp, 'optioninput')
            optioninput.set('options', options_str)
            optioninput.set('correct', correct_text or '')
        
        # Add note about conversion
        note = ET.SubElement(problem, 'p')
        note.set('class', 'conversion-note')
        note.text = "[Note: This matching question was converted to dropdown format from Canvas.]"
        
        return self._prettify_xml(problem)
    
    def _convert_fill_in_multiple_blanks(self, question: Dict) -> str:
        """Convert fill-in-multiple-blanks to optionresponse dropdowns"""
        problem = ET.Element('problem')
        
        # Add question text
        question_text = question.get('question_text', '')
        if question_text:
            # Replace [blank] placeholders with actual dropdowns
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question_text)
        
        # Create a dropdown for each blank
        for blank in question.get('blanks', []):
            blank_name = blank.get('prompt', blank.get('blank_id', ''))
            choices = blank.get('choices', [])
            correct_id = blank.get('correct_answer')
            
            if not choices:
                continue
            
            # Find correct answer text
            correct_text = None
            option_texts = []
            for choice in choices:
                option_texts.append(choice['text'])
                if choice['id'] == correct_id:
                    correct_text = choice['text']
            
            if not correct_text and option_texts:
                correct_text = option_texts[0]
            
            # Create label showing which blank this is
            label_elem = ET.SubElement(problem, 'p')
            label_elem.text = f"[{blank_name}]:"
            
            # Create optionresponse
            option_resp = ET.SubElement(problem, 'optionresponse')
            
            options_str = str(tuple(option_texts))
            
            optioninput = ET.SubElement(option_resp, 'optioninput')
            optioninput.set('options', options_str)
            optioninput.set('correct', correct_text or '')
        
        # Add note about conversion
        note = ET.SubElement(problem, 'p')
        note.set('class', 'conversion-note')
        note.text = "[Note: This fill-in-the-blanks question was converted to dropdown format from Canvas.]"
        
        return self._prettify_xml(problem)
    
    def _convert_multiple_dropdowns(self, question: Dict) -> str:
        """Convert multiple dropdowns question to optionresponse"""
        problem = ET.Element('problem')
        
        # Add question text
        question_text = question.get('question_text', '')
        if question_text:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question_text)
        
        # Create a dropdown for each variable
        for blank in question.get('blanks', []):
            var_name = blank.get('prompt', blank.get('blank_id', ''))
            choices = blank.get('choices', [])
            correct_id = blank.get('correct_answer')
            
            if not choices:
                continue
            
            # Find correct answer text
            correct_text = None
            option_texts = []
            for choice in choices:
                option_texts.append(choice['text'])
                if choice['id'] == correct_id:
                    correct_text = choice['text']
            
            if not correct_text and option_texts:
                correct_text = option_texts[0]
            
            # Create label
            label_elem = ET.SubElement(problem, 'p')
            label_elem.text = f"[{var_name}]:"
            
            # Create optionresponse
            option_resp = ET.SubElement(problem, 'optionresponse')
            
            options_str = str(tuple(option_texts))
            
            optioninput = ET.SubElement(option_resp, 'optioninput')
            optioninput.set('options', options_str)
            optioninput.set('correct', correct_text or '')
        
        return self._prettify_xml(problem)
    
    def _convert_calculated(self, question: Dict) -> str:
        """Convert calculated/formula question to static numerical problem"""
        problem = ET.Element('problem')
        
        # Build question text with variable values substituted
        question_text = question.get('question_text', '')
        sample_vars = question.get('sample_vars', {})
        formula = question.get('formula', '')
        
        # Substitute variables in question text
        display_text = question_text
        for var_name, var_value in sample_vars.items():
            display_text = display_text.replace(f'[{var_name}]', str(var_value))
        
        if display_text:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(display_text)
        
        # Get the pre-calculated answer
        answers = question.get('correct_answers', [])
        if not answers:
            note = ET.SubElement(problem, 'p')
            note.text = "[No answer available for this calculated question]"
            return self._prettify_xml(problem)
        
        # Create numericalresponse
        num_resp = ET.SubElement(
            problem,
            'numericalresponse',
            answer=str(answers[0])
        )
        
        # Add tolerance
        tolerance = question.get('answer_tolerance', 0)
        if tolerance:
            ET.SubElement(
                num_resp,
                'responseparam',
                type='tolerance',
                default=str(tolerance)
            )
        
        # Add input
        ET.SubElement(num_resp, 'formulaequationinput')
        
        # Add note about original formula (for reference)
        if formula:
            note = ET.SubElement(problem, 'p')
            note.set('class', 'conversion-note')
            var_info = ', '.join([f"{k}={v}" for k, v in sample_vars.items()])
            note.text = f"[Note: Originally a formula question. Formula: {formula}, Variables: {var_info}]"
        
        return self._prettify_xml(problem)
    
    def _convert_file_upload(self, question: Dict) -> str:
        """Convert file upload question to placeholder problem"""
        problem = ET.Element('problem')
        
        # Add question text
        if question['question_text']:
            text_elem = ET.SubElement(problem, 'p')
            text_elem.text = self._strip_html_tags(question['question_text'])
        
        # Add note about file upload
        note = ET.SubElement(problem, 'p')
        note.set('class', 'conversion-note')
        note.text = "[This was a file upload question in Canvas. File uploads require manual grading. Consider using Open edX's ORA (Open Response Assessment) with file upload enabled, or configure this as a separately graded assignment.]"
        
        return self._prettify_xml(problem)
    
    def _convert_text_only(self, question: Dict) -> str:
        """Convert text-only question to HTML content (not a problem)"""
        # This returns HTML, not CAPA XML
        html_content = f'''<div class="quiz-text-content">
{self._strip_html_tags(question.get('question_text', ''))}
</div>'''
        return html_content
    
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
        """
        Clean HTML for use in CAPA problem XML.

        Preserves semantic HTML tags that CAPA supports (strong, em, ul, ol, li,
        table, tr, td, th, img, br, sub, sup, pre, code, a) while removing
        Canvas-specific wrapper tags (div, span, p with classes).
        """
        if not html:
            return ''

        import re

        # Tags to preserve (CAPA XML supports these)
        preserve_tags = {
            'strong', 'b', 'em', 'i', 'u',
            'ul', 'ol', 'li',
            'table', 'thead', 'tbody', 'tr', 'td', 'th',
            'img', 'br', 'hr',
            'sub', 'sup',
            'pre', 'code',
            'a',
        }

        # Remove Canvas-specific wrapper tags but keep content
        # Remove <div>, <span>, <p> tags (but keep their content)
        text = re.sub(r'<div[^>]*>', '', html)
        text = re.sub(r'</div>', '', text)
        text = re.sub(r'<span[^>]*>', '', text)
        text = re.sub(r'</span>', '', text)
        # Convert <p> to newlines for readability
        text = re.sub(r'<p[^>]*>', '', text)
        text = re.sub(r'</p>', '\n', text)

        # Remove any tags NOT in the preserve list
        def remove_unknown_tags(match):
            tag_content = match.group(0)
            # Extract tag name (handle both opening and closing)
            tag_match = re.match(r'</?(\w+)', tag_content)
            if tag_match:
                tag_name = tag_match.group(1).lower()
                if tag_name in preserve_tags:
                    return tag_content  # Keep it
            return ''  # Remove it

        text = re.sub(r'<[^>]+>', remove_unknown_tags, text)

        # Clean up excessive whitespace but preserve intentional newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """Convert XML element to pretty-printed string"""
        rough_string = ET.tostring(elem, encoding='unicode')
        try:
            reparsed = minidom.parseString(rough_string)
            pretty = reparsed.toprettyxml(indent="  ")

            # Remove XML declaration and extra blank lines
            lines = [line for line in pretty.split('\n')
                    if line.strip() and not line.startswith('<?xml')]

            return '\n'.join(lines)
        except Exception:
            # If prettifying fails, return raw XML rather than crashing
            return rough_string
