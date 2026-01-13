# MITx Canvas Tools

Converts Canvas LMS course exports (.imscc) to Open edX OLX format for import into MITx.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Command Line
```bash
python -m src.converter course.imscc output_dir
```

### Python API
```python
from src.converter import convert_canvas_to_openedx

report = convert_canvas_to_openedx('course.imscc', 'output_dir', verbose=True)
print(report)
```

### Web Interface
```bash
python app.py  # runs on http://localhost:5000
```

## What Gets Converted

### Course Structure
- Canvas modules → OLX chapters/sequentials
- Wiki pages → HTML components with asset URL conversion
- Assignments → HTML components with metadata
- Quizzes → Problem components (see supported types below)

### Media & Assets
- Files copied to `/static/`
- Image URLs rewritten from `$IMS-CC-FILEBASE$` to `/static/`
- Panopto LTI embeds converted to direct embed iframes

### Navigation
- Canvas front page (`<meta name="front_page">`) → `info/updates.html`
- Internal wiki links converted to `/jump_to_id/` where possible

### Quiz Question Types

| Canvas Type | OLX Output |
|-------------|------------|
| Multiple Choice | `<multiplechoiceresponse>` |
| True/False | `<multiplechoiceresponse>` |
| Multiple Response | `<choiceresponse>` |
| Short Answer | `<stringresponse>` (supports multiple accepted answers) |
| Numerical | `<numericalresponse>` |
| Essay | Open Response Assessment (ORA) with staff grading |
| Matching | `<optionresponse>` (dropdown format) |
| Fill in Multiple Blanks | `<optionresponse>` |
| Multiple Dropdowns | `<optionresponse>` |
| Calculated | `<numericalresponse>` (static, using sample values) |
| File Upload | Placeholder HTML with instructions |
| Text Only | HTML component |

Question banks from `non_cc_assessments/*.qti` are automatically included.

## What Requires Manual Setup

The converter creates an "Import Notes" chapter listing content that couldn't be automatically converted:

- LTI tool integrations (Gradescope, Perusall, etc.)
- External URLs
- Some question types may need review after import

## Output Structure

```
output_dir/
├── course.xml
├── course/
├── chapter/
├── sequential/
├── vertical/
├── html/
├── problem/
├── openassessment/
├── static/
├── policies/
├── about/
└── info/
    └── updates.html    # Canvas front page content
```

## Deployment

Currently deployed on PythonAnywhere. To update:

1. Upload new code to `~/mitx-canvas-tools-main/`
2. Reload the web app from the Web tab

## Requirements

- Python 3.10+
- beautifulsoup4, lxml, Flask, Werkzeug

See `requirements.txt` for versions.
