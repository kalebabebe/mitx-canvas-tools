"""
QTI Parser for Canvas Quizzes

Parses QTI (Question & Test Interoperability) XML files from Canvas exports.
Supports multiple question types including multiple choice, true/false, 
multiple response, and more.
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from pathlib import Path


class QTIParser:
    """Parse Canvas QTI quiz files"""
    
    # QTI namespace
    NS = {'qti': 'http://www.imsglobal.org/xsd/ims_qtiasiv1p2'}
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def parse_quiz(self, qti_path: Path) -> Dict:
        """
        Parse QTI quiz file
        
        Args:
            qti_path: Path to assessment_qti.xml file
            
        Returns:
            Dictionary with quiz structure and questions
        """
        if not qti_path.exists():
            if self.verbose:
                print(f"⚠️  QTI file not found: {qti_path}")
            return None
        
        tree = ET.parse(qti_path)
        root = tree.getroot()
        
        # Find assessment element - try with namespace first
        assessment = root.find('qti:assessment', self.NS)
        if assessment is None:
            assessment = root.find('.//assessment')
        
        if assessment is None:
            if self.verbose:
                print("⚠️  No assessment element found in QTI")
            return None
        
        quiz_data = {
            'identifier': assessment.get('ident'),
            'title': assessment.get('title', 'Untitled Quiz'),
            'metadata': self._parse_metadata(assessment),
            'questions': []
        }
        
        # Find all items (questions) in the assessment - try with namespace
        items = assessment.findall('.//qti:item', self.NS)
        if not items:
            items = assessment.findall('.//item')
        
        for item in items:
            question = self._parse_item(item)
            if question:
                quiz_data['questions'].append(question)
        
        if self.verbose:
            print(f"   📝 Parsed quiz: {quiz_data['title']} ({len(quiz_data['questions'])} questions)")
        
        return quiz_data
    
    def _parse_metadata(self, assessment: ET.Element) -> Dict:
        """Parse quiz metadata"""
        metadata = {}
        
        # Try with and without namespace
        qtimetadata = (assessment.find('.//qtimetadata') or 
                      assessment.find('.//qti:qtimetadata', self.NS))
        
        if qtimetadata is not None:
            for field in qtimetadata.findall('.//qtimetadatafield'):
                label_elem = field.find('fieldlabel')
                entry_elem = field.find('fieldentry')
                
                if label_elem is not None and entry_elem is not None:
                    label = label_elem.text
                    entry = entry_elem.text
                    metadata[label] = entry
        
        return metadata
    
    def _parse_item(self, item: ET.Element) -> Optional[Dict]:
        """Parse individual quiz item (question)"""
        question = {
            'identifier': item.get('ident'),
            'title': item.get('title', ''),
            'type': self._get_question_type(item),
            'question_text': '',
            'choices': [],
            'correct_answers': [],
            'points': 1.0,
            'tolerance': None,
            'answer_ranges': []
        }
        
        # Parse presentation (question text and choices) - try with namespace
        presentation = item.find('.//qti:presentation', self.NS)
        if presentation is None:
            presentation = item.find('.//presentation')
            
        if presentation is not None:
            # Get question text - try with namespace
            material = presentation.find('.//qti:material', self.NS)
            if material is None:
                material = presentation.find('.//material')
                
            if material is not None:
                mattext = material.find('.//qti:mattext', self.NS)
                if mattext is None:
                    mattext = material.find('.//mattext')
                    
                if mattext is not None:
                    question['question_text'] = self._clean_html(mattext.text or '')
            
            # Check for response_str (short answer or numerical)
            response_str = presentation.find('.//qti:response_str', self.NS)
            if response_str is None:
                response_str = presentation.find('.//response_str')
            
            if response_str is not None:
                # This is a text input question (short answer or numerical)
                # Answers will be parsed from resprocessing
                pass
            else:
                # Parse choices for multiple choice questions - try with namespace
                response_lid = presentation.find('.//qti:response_lid', self.NS)
                if response_lid is None:
                    response_lid = presentation.find('.//response_lid')
                    
                if response_lid is not None:
                    cardinality = response_lid.get('rcardinality', 'Single')
                    question['multiple_answers'] = (cardinality == 'Multiple')
                    
                    render_choice = response_lid.find('.//qti:render_choice', self.NS)
                    if render_choice is None:
                        render_choice = response_lid.find('.//render_choice')
                        
                    if render_choice is not None:
                        # Find response labels - try with namespace
                        labels = render_choice.findall('.//qti:response_label', self.NS)
                        if not labels:
                            labels = render_choice.findall('.//response_label')
                            
                        for label in labels:
                            choice_id = label.get('ident')
                            
                            # Find material in label
                            mat = label.find('.//qti:material/qti:mattext', self.NS)
                            if mat is None:
                                mat = label.find('.//material/mattext')
                                
                            choice_text = mat.text if mat is not None else ''
                            
                            # Skip empty choices
                            if choice_text and choice_text.strip():
                                question['choices'].append({
                                    'id': choice_id,
                                    'text': choice_text
                                })
        
        # Parse correct answers from resprocessing - try with namespace
        resprocessing = item.find('.//qti:resprocessing', self.NS)
        if resprocessing is None:
            resprocessing = item.find('.//resprocessing')
            
        if resprocessing is not None:
            if question['type'] == 'numerical':
                self._parse_numerical_answers(resprocessing, question)
            else:
                question['correct_answers'] = self._parse_correct_answers(resprocessing)
        
        # Get points from metadata
        itemmetadata = item.find('.//qti:itemmetadata', self.NS)
        if itemmetadata is None:
            itemmetadata = item.find('.//itemmetadata')
            
        if itemmetadata is not None:
            fields = itemmetadata.findall('.//qti:qtimetadatafield', self.NS)
            if not fields:
                fields = itemmetadata.findall('.//qtimetadatafield')
                
            for field in fields:
                label = field.find('qti:fieldlabel', self.NS)
                if label is None:
                    label = field.find('fieldlabel')
                    
                entry = field.find('qti:fieldentry', self.NS)
                if entry is None:
                    entry = field.find('fieldentry')
                    
                if label is not None and entry is not None:
                    if label.text == 'points_possible':
                        try:
                            question['points'] = float(entry.text or 1.0)
                        except ValueError:
                            pass
        
        return question if question['question_text'] else None
    
    def _get_question_type(self, item: ET.Element) -> str:
        """Determine question type from metadata"""
        # Try with namespace
        itemmetadata = item.find('.//qti:itemmetadata', self.NS)
        if itemmetadata is None:
            itemmetadata = item.find('.//itemmetadata')
            
        if itemmetadata is not None:
            # Try with namespace
            fields = itemmetadata.findall('.//qti:qtimetadatafield', self.NS)
            if not fields:
                fields = itemmetadata.findall('.//qtimetadatafield')
                
            for field in fields:
                label = field.find('qti:fieldlabel', self.NS)
                if label is None:
                    label = field.find('fieldlabel')
                    
                entry = field.find('qti:fieldentry', self.NS)
                if entry is None:
                    entry = field.find('fieldentry')
                    
                if label is not None and entry is not None:
                    if label.text == 'cc_profile':
                        profile = entry.text or ''
                        if 'multiple_choice' in profile:
                            return 'multiple_choice'
                        elif 'multiple_response' in profile:
                            return 'multiple_response'
                        elif 'true_false' in profile:
                            return 'true_false'
                        elif 'short_answer' in profile or 'fib' in profile:
                            return 'short_answer'
                        elif 'essay' in profile:
                            return 'essay'
                        elif 'numerical' in profile:
                            return 'numerical'
                    elif label.text == 'question_type':
                        qtype = entry.text or 'unknown'
                        if qtype == 'numerical_question':
                            return 'numerical'
                        elif qtype == 'short_answer_question':
                            return 'short_answer'
                        return qtype
        
        return 'unknown'
    
    def _parse_correct_answers(self, resprocessing: ET.Element) -> List[str]:
        """Parse correct answer IDs from resprocessing section"""
        correct_ids = []
        
        # Find all respcondition elements - try with namespace
        respconditions = resprocessing.findall('.//qti:respcondition', self.NS)
        if not respconditions:
            respconditions = resprocessing.findall('.//respcondition')
        
        for respcondition in respconditions:
            # Check if this condition sets score to 100 (correct answer)
            setvar = respcondition.find('.//qti:setvar[@varname="SCORE"]', self.NS)
            if setvar is None:
                setvar = respcondition.find('.//setvar[@varname="SCORE"]')
                
            if setvar is not None:
                score = setvar.text
                if score and (score == '100' or score == '100.0'):
                    # Find the conditionvar
                    conditionvar = respcondition.find('.//qti:conditionvar', self.NS)
                    if conditionvar is None:
                        conditionvar = respcondition.find('.//conditionvar')
                        
                    if conditionvar is not None:
                        # Check if there's an <and> element (multiple response)
                        and_elem = conditionvar.find('qti:and', self.NS)
                        if and_elem is None:
                            and_elem = conditionvar.find('and')
                        
                        if and_elem is not None:
                            # For multiple response: get direct varequal children (not wrapped in <not>)
                            for child in and_elem:
                                if child.tag.endswith('varequal'):
                                    answer_id = child.text
                                    if answer_id:
                                        correct_ids.append(answer_id)
                                # Skip <not> elements - those are incorrect answers
                        else:
                            # Simple case - just find varequal elements
                            vareq_list = conditionvar.findall('.//qti:varequal', self.NS)
                            if not vareq_list:
                                vareq_list = conditionvar.findall('.//varequal')
                                
                            for varequal in vareq_list:
                                answer_id = varequal.text
                                if answer_id:
                                    correct_ids.append(answer_id)
        
        return correct_ids
    
    def _parse_numerical_answers(self, resprocessing: ET.Element, question: Dict) -> None:
        """Parse numerical answers including ranges and tolerances"""
        # Find all respcondition elements
        respconditions = resprocessing.findall('.//qti:respcondition', self.NS)
        if not respconditions:
            respconditions = resprocessing.findall('.//respcondition')
        
        for respcondition in respconditions:
            # Check if this condition gives full credit
            setvar = respcondition.find('.//qti:setvar[@varname="SCORE"]', self.NS)
            if setvar is None:
                setvar = respcondition.find('.//setvar[@varname="SCORE"]')
            
            if setvar is not None and setvar.text and setvar.text in ['100', '100.0']:
                conditionvar = respcondition.find('.//qti:conditionvar', self.NS)
                if conditionvar is None:
                    conditionvar = respcondition.find('.//conditionvar')
                
                if conditionvar is not None:
                    # Look for exact values or ranges
                    self._extract_numerical_values(conditionvar, question)
        
        # Calculate answer and tolerance from ranges if no exact answer
        if question['answer_ranges']:
            # Get the first non-zero range
            for min_val, max_val in question['answer_ranges']:
                if min_val != 0.0 or max_val != 0.0:
                    # If there's an exact answer that matches, use it with the range as tolerance
                    answer = None
                    for ans in question['correct_answers']:
                        try:
                            ans_val = float(ans)
                            if min_val <= ans_val <= max_val:
                                answer = ans_val
                                break
                        except ValueError:
                            pass
                    
                    # If no exact answer, use midpoint
                    if answer is None:
                        answer = (min_val + max_val) / 2
                    
                    tolerance = (max_val - min_val) / 2
                    
                    if not question['correct_answers']:
                        question['correct_answers'] = [str(answer)]
                    question['tolerance'] = tolerance
                    break
    
    def _extract_numerical_values(self, conditionvar: ET.Element, question: Dict) -> None:
        """Extract numerical values from condition variable"""
        # Check for <or> tag (multiple acceptable answers)
        or_elem = conditionvar.find('qti:or', self.NS)
        if or_elem is None:
            or_elem = conditionvar.find('or')
        
        parent = or_elem if or_elem is not None else conditionvar
        
        # Look for exact values
        vareq_list = parent.findall('.//qti:varequal', self.NS)
        if not vareq_list:
            vareq_list = parent.findall('.//varequal')
        
        for varequal in vareq_list:
            if varequal.text and varequal.text not in ['0.0', '']:
                try:
                    value = float(varequal.text)
                    if value != 0.0 and str(value) not in question['correct_answers']:
                        question['correct_answers'].append(str(value))
                except ValueError:
                    pass
        
        # Look for ranges (<and> with <vargte> and <varlte>)
        and_elems = parent.findall('.//qti:and', self.NS)
        if not and_elems:
            and_elems = parent.findall('.//and')
        
        for and_elem in and_elems:
            vargte = and_elem.find('qti:vargte', self.NS)
            if vargte is None:
                vargte = and_elem.find('vargte')
            
            varlte = and_elem.find('qti:varlte', self.NS)
            if varlte is None:
                varlte = and_elem.find('varlte')
            
            if vargte is not None and varlte is not None:
                try:
                    min_val = float(vargte.text)
                    max_val = float(varlte.text)
                    if min_val != 0.0 or max_val != 0.0:
                        question['answer_ranges'].append((min_val, max_val))
                except (ValueError, AttributeError):
                    pass
    
    def _clean_html(self, text: str) -> str:
        """Clean HTML entities from text"""
        if not text:
            return ''
        
        # Unescape common HTML entities
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')
        text = text.replace('&quot;', '"')
        text = text.replace('&nbsp;', ' ')
        
        return text
