"""
QTI Parser for Canvas Quizzes

Parses QTI (Question & Test Interoperability) XML files from Canvas exports.
Supports multiple question types including multiple choice, true/false, 
multiple response, matching, fill in multiple blanks, and more.
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
                print(f"  QTI file not found: {qti_path}")
            return None
        
        tree = ET.parse(qti_path)
        root = tree.getroot()
        
        # Find assessment element - try with namespace first
        assessment = root.find('qti:assessment', self.NS)
        if assessment is None:
            assessment = root.find('.//assessment')
        
        if assessment is None:
            if self.verbose:
                print("  No assessment element found in QTI")
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
        
        # Check for question bank references in this file
        self._load_banks_from_assessment(assessment, qti_path, quiz_data)
        
        # Also check non_cc_assessments file with same quiz ID
        base_dir = qti_path.parent.parent
        quiz_id = quiz_data['identifier']
        alt_qti_path = base_dir / "non_cc_assessments" / f"{quiz_id}.xml.qti"
        
        if alt_qti_path.exists() and alt_qti_path != qti_path:
            try:
                alt_tree = ET.parse(alt_qti_path)
                alt_root = alt_tree.getroot()
                alt_assessment = alt_root.find('qti:assessment', self.NS)
                if alt_assessment is None:
                    alt_assessment = alt_root.find('.//assessment')
                
                if alt_assessment is not None:
                    self._load_banks_from_assessment(alt_assessment, qti_path, quiz_data)
            except:
                pass
        
        if self.verbose:
            print(f"    Parsed quiz: {quiz_data['title']} ({len(quiz_data['questions'])} questions)")
        
        return quiz_data
    
    def _load_banks_from_assessment(self, assessment: ET.Element, qti_path: Path, quiz_data: Dict):
        """Load question banks referenced in an assessment"""
        sections = assessment.findall('.//qti:section', self.NS)
        if not sections:
            sections = assessment.findall('.//section')
        
        for section in sections:
            # Look for selection from question bank
            selection = section.find('.//qti:selection', self.NS)
            if selection is None:
                selection = section.find('.//selection')
            
            if selection is not None:
                sourcebank_ref = selection.find('qti:sourcebank_ref', self.NS)
                if sourcebank_ref is None:
                    sourcebank_ref = selection.find('sourcebank_ref')
                
                selection_number_elem = selection.find('qti:selection_number', self.NS)
                if selection_number_elem is None:
                    selection_number_elem = selection.find('selection_number')
                
                if sourcebank_ref is not None and selection_number_elem is not None:
                    bank_id = sourcebank_ref.text
                    num_questions = int(selection_number_elem.text)
                    
                    # Load questions from bank
                    bank_questions = self._load_question_bank(qti_path.parent.parent, bank_id, num_questions)
                    quiz_data['questions'].extend(bank_questions)
    
    def _load_question_bank(self, base_dir: Path, bank_id: str, num_questions: int) -> list:
        """Load questions from question bank file"""
        bank_path = base_dir / "non_cc_assessments" / f"{bank_id}.xml.qti"
        
        if not bank_path.exists():
            if self.verbose:
                print(f"     Question bank not found: {bank_id}")
            return []
        
        try:
            tree = ET.parse(bank_path)
            root = tree.getroot()
            
            # Find objectbank
            objectbank = root.find('.//qti:objectbank', self.NS)
            if objectbank is None:
                objectbank = root.find('.//objectbank')
            
            if objectbank is None:
                return []
            
            # Parse all items from bank
            items = objectbank.findall('.//qti:item', self.NS)
            if not items:
                items = objectbank.findall('.//item')
            
            questions = []
            for item in items[:num_questions]:  # Take only requested number
                question = self._parse_item(item)
                if question:
                    questions.append(question)
            
            if self.verbose and questions:
                print(f"    Loaded {len(questions)} questions from bank")
            
            return questions
            
        except Exception as e:
            if self.verbose:
                print(f"     Error loading question bank: {e}")
            return []
    
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
        question_type = self._get_question_type(item)
        
        question = {
            'identifier': item.get('ident'),
            'title': item.get('title', ''),
            'type': question_type,
            'question_text': '',
            'choices': [],
            'correct_answers': [],
            'points': 1.0,
            'tolerance': None,
            'answer_ranges': [],
            # For matching/dropdown/fill-in-multiple-blanks
            'blanks': [],  # List of {blank_id, prompt, choices, correct_answer}
            # For calculated questions
            'formula': None,
            'variables': [],
            'answer_tolerance': 0,
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
            
            # Route to specific parser based on question type
            if question_type in ['matching_question', 'multiple_dropdowns_question', 'fill_in_multiple_blanks_question']:
                self._parse_multi_response_item(presentation, question)
            elif question_type == 'calculated_question':
                self._parse_calculated_item(item, question)
            else:
                # Check for response_str (short answer or numerical)
                response_str = presentation.find('.//qti:response_str', self.NS)
                if response_str is None:
                    response_str = presentation.find('.//response_str')
                
                if response_str is None:
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
            if question_type == 'numerical':
                self._parse_numerical_answers(resprocessing, question)
            elif question_type in ['matching_question', 'multiple_dropdowns_question', 'fill_in_multiple_blanks_question']:
                self._parse_multi_response_answers(resprocessing, question)
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
        
        # For text_only questions, always return (they have no question text requirement)
        if question_type == 'text_only_question':
            return question
        
        return question if question['question_text'] else None
    
    def _parse_multi_response_item(self, presentation: ET.Element, question: Dict):
        """Parse matching, multiple dropdowns, and fill-in-multiple-blanks questions"""
        # These have multiple response_lid elements, one per blank/match
        response_lids = presentation.findall('.//qti:response_lid', self.NS)
        if not response_lids:
            response_lids = presentation.findall('.//response_lid')
        
        for response_lid in response_lids:
            blank_id = response_lid.get('ident', '')
            
            # Get the prompt/label for this blank
            material = response_lid.find('.//qti:material', self.NS)
            if material is None:
                material = response_lid.find('.//material')
            
            prompt = ''
            if material is not None:
                mattext = material.find('.//qti:mattext', self.NS)
                if mattext is None:
                    mattext = material.find('.//mattext')
                if mattext is not None:
                    prompt = mattext.text or ''
            
            # Get choices for this blank
            choices = []
            render_choice = response_lid.find('.//qti:render_choice', self.NS)
            if render_choice is None:
                render_choice = response_lid.find('.//render_choice')
            
            if render_choice is not None:
                labels = render_choice.findall('.//qti:response_label', self.NS)
                if not labels:
                    labels = render_choice.findall('.//response_label')
                
                for label in labels:
                    choice_id = label.get('ident')
                    mat = label.find('.//qti:material/qti:mattext', self.NS)
                    if mat is None:
                        mat = label.find('.//material/mattext')
                    choice_text = mat.text if mat is not None else ''
                    
                    if choice_text and choice_text.strip():
                        choices.append({
                            'id': choice_id,
                            'text': choice_text
                        })
            
            question['blanks'].append({
                'blank_id': blank_id,
                'prompt': prompt,
                'choices': choices,
                'correct_answer': None  # Will be filled by _parse_multi_response_answers
            })
    
    def _parse_multi_response_answers(self, resprocessing: ET.Element, question: Dict):
        """Parse correct answers for matching/dropdown/fill-in-multiple-blanks"""
        respconditions = resprocessing.findall('.//qti:respcondition', self.NS)
        if not respconditions:
            respconditions = resprocessing.findall('.//respcondition')
        
        for respcondition in respconditions:
            conditionvar = respcondition.find('.//qti:conditionvar', self.NS)
            if conditionvar is None:
                conditionvar = respcondition.find('.//conditionvar')
            
            if conditionvar is not None:
                vareq_list = conditionvar.findall('.//qti:varequal', self.NS)
                if not vareq_list:
                    vareq_list = conditionvar.findall('.//varequal')
                
                for varequal in vareq_list:
                    resp_ident = varequal.get('respident', '')
                    correct_id = varequal.text
                    
                    # Match to the corresponding blank
                    for blank in question['blanks']:
                        if blank['blank_id'] == resp_ident:
                            blank['correct_answer'] = correct_id
                            break
    
    def _parse_calculated_item(self, item: ET.Element, question: Dict):
        """Parse calculated/formula question"""
        # Look for itemproc_extension with calculated data
        itemproc = item.find('.//qti:itemproc_extension', self.NS)
        if itemproc is None:
            itemproc = item.find('.//itemproc_extension')
        
        if itemproc is not None:
            calculated = itemproc.find('.//qti:calculated', self.NS)
            if calculated is None:
                calculated = itemproc.find('.//calculated')
            
            if calculated is not None:
                # Get tolerance
                tolerance = calculated.find('.//qti:answer_tolerance', self.NS)
                if tolerance is None:
                    tolerance = calculated.find('.//answer_tolerance')
                if tolerance is not None and tolerance.text:
                    try:
                        question['answer_tolerance'] = float(tolerance.text)
                    except ValueError:
                        pass
                
                # Get formula
                formula = calculated.find('.//qti:formula', self.NS)
                if formula is None:
                    formula = calculated.find('.//formula')
                if formula is not None:
                    question['formula'] = formula.text
                
                # Get variables
                vars_elem = calculated.find('.//qti:vars', self.NS)
                if vars_elem is None:
                    vars_elem = calculated.find('.//vars')
                
                if vars_elem is not None:
                    var_elems = vars_elem.findall('.//qti:var', self.NS)
                    if not var_elems:
                        var_elems = vars_elem.findall('.//var')
                    
                    for var_elem in var_elems:
                        var_name = var_elem.get('name')
                        min_elem = var_elem.find('.//qti:min', self.NS)
                        if min_elem is None:
                            min_elem = var_elem.find('.//min')
                        max_elem = var_elem.find('.//qti:max', self.NS)
                        if max_elem is None:
                            max_elem = var_elem.find('.//max')
                        
                        var_data = {'name': var_name}
                        if min_elem is not None and min_elem.text:
                            var_data['min'] = float(min_elem.text)
                        if max_elem is not None and max_elem.text:
                            var_data['max'] = float(max_elem.text)
                        
                        question['variables'].append(var_data)
                
                # Get a sample answer from var_sets
                var_sets = calculated.find('.//qti:var_sets', self.NS)
                if var_sets is None:
                    var_sets = calculated.find('.//var_sets')
                
                if var_sets is not None:
                    var_set = var_sets.find('.//qti:var_set', self.NS)
                    if var_set is None:
                        var_set = var_sets.find('.//var_set')
                    
                    if var_set is not None:
                        answer = var_set.find('.//qti:answer', self.NS)
                        if answer is None:
                            answer = var_set.find('.//answer')
                        if answer is not None and answer.text:
                            question['correct_answers'] = [answer.text]
                        
                        # Get the variable values for this set
                        question['sample_vars'] = {}
                        var_vals = var_set.findall('.//qti:var', self.NS)
                        if not var_vals:
                            var_vals = var_set.findall('.//var')
                        for var_val in var_vals:
                            var_name = var_val.get('name')
                            if var_name and var_val.text:
                                question['sample_vars'][var_name] = var_val.text
    
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
                        # Map Canvas question types to our internal types
                        type_mapping = {
                            'numerical_question': 'numerical',
                            'short_answer_question': 'short_answer',
                            'multiple_choice_question': 'multiple_choice',
                            'true_false_question': 'true_false',
                            'multiple_answers_question': 'multiple_response',
                            'essay_question': 'essay',
                            'matching_question': 'matching_question',
                            'fill_in_multiple_blanks_question': 'fill_in_multiple_blanks_question',
                            'multiple_dropdowns_question': 'multiple_dropdowns_question',
                            'calculated_question': 'calculated_question',
                            'file_upload_question': 'file_upload_question',
                            'text_only_question': 'text_only_question',
                        }
                        return type_mapping.get(qtype, qtype)
        
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
