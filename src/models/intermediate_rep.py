"""
Intermediate Representation (IR) Models

These classes represent the course structure in a format-agnostic way,
making it easy to convert from Canvas to Open edX.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class ComponentIR:
    """Intermediate representation of a component (problem, html, video, etc.)"""
    type: str  # 'html', 'problem', 'video', 'lti', etc.
    display_name: str
    url_name: str
    content: Any  # HTML string, XML string, or structured data
    settings: Dict[str, Any] = field(default_factory=dict)
    canvas_source: Dict[str, Any] = field(default_factory=dict)  # Original Canvas data


@dataclass
class VerticalIR:
    """Intermediate representation of a vertical (learning sequence)"""
    display_name: str
    url_name: str
    components: List[ComponentIR] = field(default_factory=list)
    published: bool = True


@dataclass
class SequentialIR:
    """Intermediate representation of a sequential (subsection)"""
    display_name: str
    url_name: str
    verticals: List[VerticalIR] = field(default_factory=list)
    published: bool = True
    prereq: Optional[str] = None  # url_name of prerequisite sequential
    prereq_min_score: Optional[float] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    require_sequential: bool = False


@dataclass
class ChapterIR:
    """Intermediate representation of a chapter (top-level section)"""
    display_name: str
    url_name: str
    sequentials: List[SequentialIR] = field(default_factory=list)
    published: bool = True
    position: int = 0


@dataclass
class CourseIR:
    """Intermediate representation of entire course"""
    title: str
    org: str
    course: str
    run: str
    chapters: List[ChapterIR] = field(default_factory=list)
    
    # Optional metadata
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    language: str = "en"
    self_paced: bool = True
    
    # Assets and resources
    assets: Dict[str, str] = field(default_factory=dict)  # identifier -> filename
    
    # Unsupported/special items
    lti_tools: List[Dict[str, Any]] = field(default_factory=list)
    unsupported_items: List[Dict[str, Any]] = field(default_factory=list)
    conditional_release_rules: List[Dict[str, Any]] = field(default_factory=list)
    
    # Canvas-specific
    canvas_course_code: str = ""
    canvas_identifier: str = ""
