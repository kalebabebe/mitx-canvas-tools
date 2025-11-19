# Canvas to Open edX Converter

Convert Canvas LMS course exports (IMSCC format) to Open edX OLX format with a simple web interface or command-line tool.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **🎓 Complete Course Conversion** - Modules, pages, quizzes, and assets
- **🧪 Quiz Support** - Multiple choice, true/false, checkboxes, fill-in-blank, and numerical questions
- **🖼️ Asset Management** - Automatic image and file copying with URL conversion
- **🌐 Web Interface** - Drag-and-drop file upload with real-time conversion
- **⚡ Fast** - Convert 70+ item courses in seconds
- **✅ Production Tested** - Validated with real Canvas courses

## Quick Start

### Web Interface (Recommended)

The easiest way to use the converter is through the web interface:

1. **Upload** your Canvas course export (.imscc file)
2. **Convert** - Processing takes 2-10 seconds depending on course size
3. **Download** the generated Open edX course package (.tar.gz)
4. **Import** into Open edX Studio

### Command Line

```bash
python cli.py input.imscc output_directory/ --verbose
```

## Installation

### Requirements

- Python 3.11 or higher
- pip (Python package manager)

### Setup

```bash
# Clone or download this repository
git clone <repository-url>
cd canvas-to-openedx-converter

# Install dependencies
pip install -r requirements.txt

# Run web interface
python app.py
# Open http://localhost:5000 in your browser

# Or use command line
python cli.py --help
```

## What Gets Converted

| Canvas Element | Open edX Output | Status |
|---------------|----------------|--------|
| Modules | Chapters | ✅ Full support |
| Module Items | Verticals | ✅ Full support |
| Wiki Pages | HTML Components | ✅ Full support |
| Quizzes - Multiple Choice | CAPA Problems | ✅ Full support |
| Quizzes - True/False | CAPA Problems | ✅ Full support |
| Quizzes - Checkboxes | CAPA Problems | ✅ Full support |
| Quizzes - Fill in Blank | CAPA Problems | ✅ Full support |
| Quizzes - Numerical | CAPA Problems | ✅ Full support |
| Images & Files | Static Assets | ✅ Full support |
| Module Prerequisites | Sequential Gating | ⚠️ Partial support |
| Assignments | Documentation | ⚠️ Manual setup needed |
| LTI Tools | Documentation | ⚠️ Manual setup needed |

## Output Format

The converter generates a complete Open edX OLX course structure:

```
output/
├── course.xml                    # Course entry point
├── course/{run}.xml             # Course definition
├── chapter/*.xml                # Course chapters (from Canvas modules)
├── sequential/*.xml             # Module sequences
├── vertical/*.xml               # Content containers
├── html/*.xml + *.html         # Wiki pages and content
├── problem/*.xml               # Quiz questions (CAPA format)
├── static/*                    # All images and assets
└── policies/{run}/
    ├── grading_policy.json
    └── policy.json
```

Import the entire output directory into Open edX Studio as a course archive.

## Supported Question Types

### Fully Supported
- **Multiple Choice** - Single correct answer
- **True/False** - Binary choice questions
- **Multiple Answer** - Checkboxes with multiple correct answers
- **Fill in the Blank** - Text-based answers with matching
- **Numerical** - Numeric answers with optional tolerance

### Not Supported
- **Essay Questions** - Open edX requires Open Response Assessment (ORA) which must be configured manually in Studio
- **Matching Questions** - Requires custom implementation in Open edX

## Usage Examples

### Basic Conversion

```bash
python cli.py my-canvas-course.imscc converted-course/
```

### With Verbose Output

```bash
python cli.py my-canvas-course.imscc converted-course/ --verbose
```

### Using Python API

```python
from src.converter import convert_canvas_to_openedx

report = convert_canvas_to_openedx(
    imscc_path='course.imscc',
    output_dir='output/',
    verbose=True
)

print(f"Converted {report['statistics']['chapters']} chapters")
print(f"Created {report['statistics']['components']} components")
print(f"Copied {report['assets']['converted']} assets")
```

## Configuration

### File Size Limits

For the web interface, adjust the maximum upload size in `app.py`:

```python
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB
```

### Timeout Settings

For very large courses (200+ items), consider deploying with increased timeout limits.

## Deployment

### Heroku

This application is ready for Heroku deployment. See [DEPLOY.md](DEPLOY.md) for detailed instructions.

Quick deploy:
```bash
heroku create your-app-name
git push heroku main
```

### Docker

```bash
docker build -t canvas-converter .
docker run -p 5000:5000 canvas-converter
```

### Local Production Server

```bash
gunicorn app:app --bind 0.0.0.0:5000
```

## Technical Details

### Standards Compliance

- **Input Format**: IMS Common Cartridge 1.3, IMS QTI 1.2
- **Output Format**: Open edX OLX, CAPA problem format
- **Validation**: 100% format compliance with Open edX specification

### Architecture

```
Canvas IMSCC → Parser → Intermediate Representation → Generator → Open edX OLX
                ↓                                          ↓
            QTI Parser                              Asset Manager
                ↓                                          ↓
            CAPA Converter                          URL Converter
```

### Performance

- Small courses (1-10 items): <1 second
- Medium courses (11-50 items): 1-3 seconds  
- Large courses (51-100 items): 3-5 seconds
- Very large courses (100+ items): 5-15 seconds

## Troubleshooting

### Common Issues

**"No file uploaded" or "File not found"**
- Ensure the file has a .imscc or .zip extension
- Check file isn't corrupted

**"Conversion timeout"**
- Very large courses may need more time
- Try command-line conversion instead of web interface
- Consider breaking course into smaller modules

**"Assets not found"**
- Check that your Canvas export includes the web_resources folder
- Some Canvas exports may not include all assets

**Quiz questions not converting**
- Empty quizzes are skipped (this is normal)
- Unsupported question types are documented in the conversion report
- Check that quizzes contain supported question types

## Known Limitations

- **Assignments**: Converted to documentation notes. Configure as Open Response Assessments (ORA) in Studio for grading.
- **LTI Tools**: Require manual configuration in Open edX Studio with appropriate passports and keys.
- **Conditional Release**: Canvas-specific feature with no direct Open edX equivalent.
- **Canvas Studio Videos**: Embedded videos may need re-linking in Open edX.

## Development

### Project Structure

```
canvas-to-openedx-converter/
├── app.py                      # Flask web application
├── cli.py                      # Command-line interface
├── src/
│   ├── parsers/               # Canvas IMSCC and QTI parsers
│   ├── converters/            # Conversion logic
│   ├── generators/            # OLX generation
│   ├── models/                # Data models
│   └── utils/                 # Helper utilities
├── templates/                 # Web interface templates
├── requirements.txt           # Python dependencies
└── tests/                     # Test files
```

### Running Tests

```bash
pytest tests/
```

### Contributing

Contributions are welcome! Please ensure:
- Code follows existing style conventions
- All tests pass
- New features include tests
- Documentation is updated

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Check existing documentation in the `outputs/` directory
- Review troubleshooting section above

## Acknowledgments

Built with:
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - HTML/XML parsing
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [lxml](https://lxml.de/) - XML processing

Implements:
- IMS Common Cartridge specification
- IMS QTI specification
- Open edX OLX format
- Open edX CAPA problem format

---

**Status**: Production ready  
**Version**: 1.0.0  
**Python**: 3.11+
