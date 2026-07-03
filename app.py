"""
Flask Web Application for Canvas to Open edX Converter
Simple upload/convert/download interface
"""

import os
import re
import shutil
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from flask import Flask, render_template, request, send_from_directory, jsonify

from src.converter import convert_canvas_to_openedx

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size
app.config['OUTPUT_FOLDER'] = os.path.join(tempfile.gettempdir(), 'canvas_edx_outputs')
app.config['JOB_TTL_SECONDS'] = 60 * 60  # downloads kept for 1 hour

os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

JOB_ID_RE = re.compile(r'^[0-9a-f]{32}$')


def cleanup_expired_jobs():
    """
    Remove job directories older than JOB_TTL_SECONDS. Unlike a blanket
    wipe, this never touches jobs from concurrent/recent requests.
    """
    now = time.time()
    root = app.config['OUTPUT_FOLDER']
    try:
        entries = os.listdir(root)
    except OSError:
        return
    for name in entries:
        path = os.path.join(root, name)
        try:
            if now - os.path.getmtime(path) > app.config['JOB_TTL_SECONDS']:
                shutil.rmtree(path, ignore_errors=True)
        except OSError as e:
            app.logger.warning(f"Could not clean {path}: {e}")


@app.errorhandler(413)
def request_entity_too_large(e):
    """Friendly JSON response for oversized uploads"""
    limit_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return jsonify({
        'error': f'File too large. Maximum upload size is {limit_mb}MB.',
        'type': 'RequestEntityTooLarge',
    }), 413


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

    report = None
    step = 'initializing'

    # Per-request working directories: concurrent conversions never collide.
    job_id = uuid.uuid4().hex
    job_dir = os.path.join(app.config['OUTPUT_FOLDER'], job_id)
    upload_dir = tempfile.mkdtemp(prefix='canvas_upload_')

    try:
        # Reclaim disk from expired jobs (never touches in-flight ones)
        step = 'cleaning up old files'
        cleanup_expired_jobs()

        os.makedirs(job_dir, exist_ok=True)

        # Save uploaded file (basename only; stored in our own temp dir)
        step = 'saving uploaded file'
        filename = os.path.basename(file.filename) or 'course.imscc'
        upload_path = os.path.join(upload_dir, filename)
        file.save(upload_path)

        # Convert
        step = 'converting course'
        output_name = Path(filename).stem + '_olx'
        output_path = os.path.join(job_dir, output_name)
        report = convert_canvas_to_openedx(upload_path, output_path, verbose=False)

        # Free disk space BEFORE creating the tarball
        step = 'creating download archive'
        shutil.rmtree(upload_dir, ignore_errors=True)

        # Create tar.gz of output using streaming to keep memory low
        tar_name = output_name + '.tar.gz'
        tar_path = os.path.join(job_dir, tar_name)

        with tarfile.open(tar_path, 'w:gz', compresslevel=6) as tar:
            for root, dirs, files in os.walk(output_path):
                for f in files:
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, output_path)
                    tar.add(full_path, arcname=arcname)

        # Cleanup: remove uncompressed OLX directory
        shutil.rmtree(output_path, ignore_errors=True)

        return jsonify({
            'success': True,
            'report': report,
            'download_url': f'/download/{job_id}/{tar_name}'
        })

    except Exception as e:
        import traceback
        shutil.rmtree(job_dir, ignore_errors=True)

        error_detail = {
            'error': f'Conversion failed during: {step}',
            'detail': str(e),
            'type': type(e).__name__,
        }

        # Include partial report if conversion got far enough
        if report:
            error_detail['partial_report'] = report

        app.logger.error(f"Conversion failed at step '{step}': {traceback.format_exc()}")
        return jsonify(error_detail), 500

    finally:
        shutil.rmtree(upload_dir, ignore_errors=True)


@app.route('/download/<job_id>/<path:filename>')
def download(job_id, filename):
    """Download converted file (path-traversal safe via send_from_directory)"""
    if not JOB_ID_RE.match(job_id):
        return jsonify({'error': 'Invalid download link'}), 404

    job_dir = os.path.join(app.config['OUTPUT_FOLDER'], job_id)
    if not os.path.isdir(job_dir):
        return jsonify({'error': 'File not found or link expired'}), 404

    return send_from_directory(job_dir, filename, as_attachment=True)


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
