"""
Main Canvas to Open edX Converter

Orchestrates the conversion pipeline.
"""

from pathlib import Path
from typing import Dict

from .parsers.canvas_parser import CanvasParser
from .converters.canvas_to_ir import CanvasToIRConverter
from .converters.asset_manager import AssetManager
from .generators.olx_generator import OLXGenerator
from .models.intermediate_rep import CourseIR


class CanvasToOpenEdXConverter:
    """Main converter class orchestrating the pipeline"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.canvas_parser = None
        self.ir_converter = CanvasToIRConverter(verbose=verbose)
    
    def convert(self, imscc_path: str, output_dir: str) -> Dict:
        """
        Convert Canvas IMSCC to Open edX OLX
        
        Args:
            imscc_path: Path to Canvas IMSCC file
            output_dir: Output directory for OLX
            
        Returns:
            Conversion report dictionary
        """
        
        if self.verbose:
            print("=" * 60)
            print("Canvas to Open edX Converter")
            print("=" * 60)
        
        # Step 1: Parse Canvas course
        if self.verbose:
            print("\nStep 1: Parsing Canvas course...")
        
        with CanvasParser(verbose=self.verbose) as parser:
            self.canvas_parser = parser
            canvas_data = parser.parse(imscc_path)
            
            if self.verbose:
                print(f"   Parsed: {canvas_data['title']}")
                print(f"   Modules: {len(canvas_data['modules'])}")
            
            # Step 2: Convert to IR
            if self.verbose:
                print("\nStep 2: Converting to intermediate representation...")
            
            # Initialize asset manager
            asset_manager = AssetManager(
                parser.extract_dir, 
                Path(output_dir),
                verbose=self.verbose
            )
            self.ir_converter.asset_manager = asset_manager
            
            course_ir = self.ir_converter.convert(canvas_data, parser)
            
            if self.verbose:
                print(f"   Course: {course_ir.org}/{course_ir.course}/{course_ir.run}")
                print(f"   Chapters: {len(course_ir.chapters)}")
            
            # Step 3: Copy assets
            if self.verbose:
                print("\nStep 3: Copying assets...")
            
            asset_count = asset_manager.copy_all_assets()
            
            # Step 4: Generate OLX
            if self.verbose:
                print("\nStep 4: Generating Open edX OLX...")
            
            olx_gen = OLXGenerator(output_dir, verbose=self.verbose)
            olx_gen.generate(course_ir)
            
            # Step 5: Generate report
            report = self._generate_report(canvas_data, course_ir, output_dir, asset_count)
        
        if self.verbose:
            print("\n" + "=" * 60)
            print("Conversion Complete")
            print("=" * 60)
            print(f"\nOLX Output: {output_dir}")
        
        return report
    
    def _generate_report(
        self, 
        canvas_data: Dict, 
        course_ir: CourseIR, 
        output_dir: str,
        asset_count: int = 0
    ) -> Dict:
        """Generate conversion report"""
        
        total_items = sum(
            len(seq.verticals) 
            for chapter in course_ir.chapters 
            for seq in chapter.sequentials
        )
        
        total_components = sum(
            len(vert.components)
            for chapter in course_ir.chapters
            for seq in chapter.sequentials
            for vert in seq.verticals
        )
        
        # Count skipped items by type
        skipped_by_type = {}
        for item in self.ir_converter.skipped_items:
            item_type = item['type']
            skipped_by_type[item_type] = skipped_by_type.get(item_type, 0) + 1
        
        report = {
            'course_title': course_ir.title,
            'course_id': f"{course_ir.org}/{course_ir.course}/{course_ir.run}",
            'source_file': Path(canvas_data.get('extract_dir', '')).parent.name,
            'statistics': {
                'chapters': len(course_ir.chapters),
                'sequentials': sum(len(c.sequentials) for c in course_ir.chapters),
                'verticals': total_items,
                'components': total_components,
                'assets': asset_count
            },
            'skipped': skipped_by_type,
            'output_directory': output_dir
        }
        
        return report


def convert_canvas_to_openedx(
    imscc_path: str,
    output_dir: str,
    verbose: bool = True
) -> Dict:
    """
    Convenience function to convert Canvas to Open edX
    
    Args:
        imscc_path: Path to Canvas IMSCC export file
        output_dir: Output directory for OLX
        verbose: Print progress messages
        
    Returns:
        Conversion report dictionary
    """
    converter = CanvasToOpenEdXConverter(verbose=verbose)
    return converter.convert(imscc_path, output_dir)
