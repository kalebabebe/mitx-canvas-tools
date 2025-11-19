#!/usr/bin/env python3
"""
Canvas to Open edX Converter - Command Line Interface
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.converter import convert_canvas_to_openedx


def main():
    parser = argparse.ArgumentParser(
        description='Convert Canvas course exports to Open edX OLX format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Basic conversion
  python cli.py canvas-course.imscc output_olx/
  
  # With verbose output
  python cli.py canvas-course.imscc output_olx/ --verbose
  
  # Quiet mode
  python cli.py canvas-course.imscc output_olx/ --quiet
        '''
    )
    
    parser.add_argument(
        'imscc_file',
        help='Path to Canvas IMSCC export file'
    )
    
    parser.add_argument(
        'output_dir',
        help='Output directory for Open edX OLX'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (default)'
    )
    
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress output messages'
    )
    
    args = parser.parse_args()
    
    # Check input file exists
    imscc_path = Path(args.imscc_file)
    if not imscc_path.exists():
        print(f"❌ Error: File not found: {imscc_path}")
        sys.exit(1)
    
    # Check file extension
    if imscc_path.suffix.lower() != '.imscc':
        print(f"⚠️  Warning: File does not have .imscc extension")
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run conversion
    verbose = not args.quiet
    
    try:
        report = convert_canvas_to_openedx(
            str(imscc_path),
            str(output_dir),
            verbose=verbose
        )
        
        # Print summary
        if not args.quiet:
            print("\n📊 Conversion Summary:")
            print(f"   Course: {report['course_title']}")
            print(f"   Course ID: {report['course_id']}")
            print(f"   Chapters: {report['statistics']['chapters']}")
            print(f"   Verticals: {report['statistics']['verticals']}")
            print(f"   Components: {report['statistics']['components']}")
            print(f"\n📁 Output: {report['output_directory']}")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
