# Canvas to Open edX Converter

Convert Canvas LMS courses to Open edX format.

## Quick Start

```bash
pip install -r requirements.txt
python -m src.converter course.imscc output_dir
```

## Features

- ✅ Modules → Chapters/Sections
- ✅ Wiki pages → HTML components  
- ✅ Quizzes → CAPA problems (5 types)
- ✅ Assets → /static/ with URL conversion
- ✅ Assignments → Info pages

## Supported Question Types

| Type | Status |
|------|--------|
| Multiple Choice | ✅ |
| True/False | ✅ |
| Multiple Response | ✅ |
| Short Answer | ✅ |
| Numerical | ✅ |

## Usage

### Python
```python
from src.converter import convert_canvas_to_openedx

report = convert_canvas_to_openedx('course.imscc', 'output_dir', verbose=True)
```

### Web Interface
```bash
python app.py  # http://localhost:5000
```

## Asset Management

Automatically copies Canvas assets and converts URLs:
```html
<!-- Canvas -->
<img src="$IMS-CC-FILEBASE$/image.png"/>

<!-- Open edX -->
<img src="/static/image.png"/>
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
└── static/              # Assets from Canvas
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

- Question banks not supported (inline questions only)
- Essays show manual grading note
- LTI tools skipped
- Assignments → info pages only

## Troubleshooting

**Quiz has 0 questions?** Check if using question banks (not supported)

**Images not loading?** Verify `/static/` directory created and URLs converted

**Import fails?** Check Studio logs and validate XML structure

## Documentation

- `docs/SHORT_ANSWER_NUMERICAL.md` - Question type details

## Requirements

- Python 3.11+
- beautifulsoup4, lxml, Flask

## License

MIT
