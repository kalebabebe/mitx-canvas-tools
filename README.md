# Canvas to Open edX Converter

Convert Canvas LMS courses to Open edX format.

## Quick Start

```bash
pip install -r requirements.txt
python -m src.converter course.imscc output_dir
```

## Features

- ✅ Course structure (modules → chapters)
- ✅ Wiki pages with asset URL conversion
- ✅ Quizzes with 5 question types
- ✅ Question banks (loads from separate files)
- ✅ Multiple acceptable answers (short answer)
- ✅ Asset copying to /static/
- ✅ Unsupported content report (LTI tools, etc.)
- ✅ Clean, emoji-free output

## Supported Question Types

| Type | Canvas | Open edX |
|------|--------|----------|
| Multiple Choice | `cc.multiple_choice.v0p1` | `<multiplechoiceresponse>` |
| True/False | `cc.true_false.v0p1` | `<multiplechoiceresponse>` |
| Multiple Response | `cc.multiple_response.v0p1` | `<choiceresponse>` |
| Short Answer | `cc.fib.v0p1` | `<stringresponse>` |
| Numerical | `numerical_question` | `<numericalresponse>` |

## Usage

### Python API
```python
from src.converter import convert_canvas_to_openedx

report = convert_canvas_to_openedx('course.imscc', 'output_dir', verbose=True)

# Check results
print(f"Chapters: {report['statistics']['chapters']}")
print(f"Components: {report['statistics']['components']}")
print(f"Assets: {report['statistics']['assets']}")
print(f"Skipped: {report['skipped']}")
```

### Web Interface
```bash
python app.py  # http://localhost:5000
```

## New Features

### Question Banks
Automatically loads questions from Canvas question bank files (`non_cc_assessments/*.qti`).

### Multiple Answers
Short answer questions support multiple acceptable answers:
```xml
<stringresponse answer="red" type="ci">
  <additional_answer answer="blue"/>
  <additional_answer answer="yellow"/>
</stringresponse>
```

### Unsupported Content Report
Creates "Import Notes" chapter listing all LTI tools and unsupported items that need manual setup.

### Validation Report
```python
{
  'statistics': {'chapters': 10, 'components': 61, 'assets': 48},
  'skipped': {'LTI Tool': 2}
}
```

## Output Structure

```
output_dir/
├── course.xml
├── chapter/*.xml
├── sequential/*.xml
├── vertical/*.xml
├── html/*.xml + *.html
├── problem/*.xml
├── static/              # Assets from Canvas
└── Import Notes/        # Unsupported content report
```

## Deployment

### Heroku
```bash
heroku create app-name
git push heroku main
```

### Local
```bash
python app.py
```

## Limitations

- Essay questions (manual grading note)
- Some Canvas-specific features

## Requirements

- Python 3.11+
- beautifulsoup4, lxml, Flask

See `requirements.txt` for complete list.
