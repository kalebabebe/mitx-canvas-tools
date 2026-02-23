"""
Flask Web Application for Canvas to Open edX Converter
Simple upload/convert/download interface
"""

import os
import tarfile
import tempfile
import zipfile
from pathlib import Path
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import shutil

from src.converter import convert_canvas_to_openedx

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['OUTPUT_FOLDER'] = '/tmp/outputs'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)


def cleanup_tmp_folders():
    """
    Clear old files from /tmp/uploads and /tmp/outputs to prevent
    disk space exhaustion on PythonAnywhere or other constrained hosts.
    Recreates the directories after clearing.
    """
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        try:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            app.logger.warning(f"Could not clean {folder}: {e}")

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    """Handle file upload and conversion"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith(('.imscc', '.zip')):
        return jsonify({'error': 'File must be .imscc or .zip'}), 400
    
    try:
        # Clean up old files before starting to free disk space
        cleanup_tmp_folders()

        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        # Create output directory
        output_name = Path(filename).stem + '_olx'
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_name)

        # Remove old output if exists
        if os.path.exists(output_path):
            shutil.rmtree(output_path)

        # Convert
        report = convert_canvas_to_openedx(upload_path, output_path, verbose=False)

        # Create tar.gz of output using streaming to keep memory low
        zip_name = output_name + '.tar.gz'
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_name)

        with tarfile.open(zip_path, 'w:gz') as tar:
            for root, dirs, files in os.walk(output_path):
                for f in files:
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, output_path)
                    tar.add(full_path, arcname=arcname)

        # Cleanup: remove upload and uncompressed OLX directory to save space
        os.remove(upload_path)
        shutil.rmtree(output_path, ignore_errors=True)

        return jsonify({
            'success': True,
            'report': report,
            'download_url': f'/download/{zip_name}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download(filename):
    """Download converted file"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename
    )

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
