"""Command-line entry point for Canvas to Open edX converter"""

import sys
import argparse
from .converter import CanvasToOpenEdXConverter


def main():
    parser = argparse.ArgumentParser(
        description='Convert Canvas IMSCC export to Open edX OLX format'
    )
    parser.add_argument('imscc_path', help='Path to Canvas IMSCC export file')
    parser.add_argument('output_dir', help='Output directory for OLX')
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print verbose output'
    )
    
    args = parser.parse_args()
    
    converter = CanvasToOpenEdXConverter(verbose=args.verbose)
    report = converter.convert(args.imscc_path, args.output_dir)
    
    if args.verbose:
        print("\nConversion Report:")
        print(f"  Course: {report['course_title']}")
        print(f"  ID: {report['course_id']}")
        print(f"  Chapters: {report['statistics']['chapters']}")
        print(f"  Sequentials: {report['statistics']['sequentials']}")
        print(f"  Verticals: {report['statistics']['verticals']}")
        print(f"  Components: {report['statistics']['components']}")
        print(f"  Assets: {report['statistics']['assets']}")
        if report['skipped']:
            print(f"  Skipped items: {report['skipped']}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
