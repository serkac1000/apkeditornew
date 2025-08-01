"""
APK Editor Flask Application
Main application factory and route definitions
"""

import os
import shutil
import zipfile
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from apk_editor import APKEditor
import logging

# Initialize database
db = SQLAlchemy()

class Project(db.Model):
    """Database model for APK projects"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    original_filename = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), default='uploaded')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    path = db.Column(db.String(500))

def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apk_editor.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size
    app.config['UPLOAD_FOLDER'] = 'uploads'
    
    # Initialize extensions
    db.init_app(app)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create directories
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('projects', exist_ok=True)
    os.makedirs('temp', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Initialize APK Editor
    apk_editor = APKEditor()
    
    @app.cli.command("init-db")
    def init_db_command():
        """Creates the database tables."""
        db.create_all()
        print("Initialized the database.")
    
    @app.route('/')
    def index():
        """Main page"""
        projects = Project.query.order_by(Project.created_at.desc()).all()
        return render_template('index.html', projects=projects)
    
    @app.route('/upload', methods=['GET', 'POST'])
    def upload_apk():
        """Upload APK file"""
        if request.method == 'POST':
            if 'apk_file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['apk_file']
            project_name = request.form.get('project_name', '').strip()
            
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if not project_name:
                project_name = os.path.splitext(file.filename)[0]
            
            if file and file.filename.lower().endswith('.apk'):
                try:
                    # Save uploaded file
                    filename = secure_filename(file.filename)
                    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(upload_path)
                    
                    # Create project
                    project = Project(
                        name=project_name,
                        original_filename=filename,
                        status='uploaded',
                        path=upload_path
                    )
                    db.session.add(project)
                    db.session.commit()
                    
                    flash(f'APK uploaded successfully: {project_name}', 'success')
                    return redirect(url_for('project_detail', project_id=project.id))
                    
                except Exception as e:
                    flash(f'Error uploading file: {str(e)}', 'error')
            else:
                flash('Please select a valid APK file', 'error')
        
        return render_template('upload.html')
    
    @app.route('/project/<int:project_id>')
    def project_detail(project_id):
        """Project detail page"""
        project = Project.query.get_or_404(project_id)
        
        # Get project directory structure if decompiled
        project_dir = os.path.join('projects', f'project_{project_id}')
        files = []
        
        if os.path.exists(project_dir):
            for root, dirs, filenames in os.walk(project_dir):
                for filename in filenames:
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.xml')):
                        file_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(file_path, project_dir)
                        files.append({
                            'name': filename,
                            'path': rel_path,
                            'type': get_file_type(filename)
                        })
        
        return render_template('project_detail.html', project=project, files=files)
    
    @app.route('/decompile/<int:project_id>')
    def decompile_apk(project_id):
        """Decompile APK"""
        project = Project.query.get_or_404(project_id)
        
        try:
            project_dir = os.path.join('projects', f'project_{project_id}')
            success = apk_editor.decompile_apk(project.path, project_dir)
            
            if success:
                project.status = 'decompiled'
                db.session.commit()
                flash('APK decompiled successfully', 'success')
            else:
                flash('Failed to decompile APK', 'error')
                
        except Exception as e:
            flash(f'Error decompiling APK: {str(e)}', 'error')
        
        return redirect(url_for('project_detail', project_id=project_id))
    
    @app.route('/compile/<int:project_id>')
    def compile_apk(project_id):
        """Compile APK"""
        project = Project.query.get_or_404(project_id)
        
        try:
            project_dir = os.path.join('projects', f'project_{project_id}')
            output_path = os.path.join('temp', f'{project.name}_modified.apk')
            
            success = apk_editor.compile_apk(project_dir, output_path)
            
            if success:
                project.status = 'compiled'
                project.path = output_path
                db.session.commit()
                flash('APK compiled successfully', 'success')
            else:
                flash('Failed to compile APK', 'error')
                
        except Exception as e:
            flash(f'Error compiling APK: {str(e)}', 'error')
        
        return redirect(url_for('project_detail', project_id=project_id))
    
    @app.route('/download/<int:project_id>')
    def download_apk(project_id):
        """Download compiled APK"""
        project = Project.query.get_or_404(project_id)
        
        if project.status != 'compiled' or not os.path.exists(project.path):
            flash('APK not ready for download. Please compile first.', 'error')
            return redirect(url_for('project_detail', project_id=project_id))
        
        return send_file(project.path, as_attachment=True, 
                        download_name=f'{project.name}_modified.apk')
    
    @app.route('/edit_file/<int:project_id>/<path:file_path>')
    def edit_file(project_id, file_path):
        """Edit file in project"""
        project = Project.query.get_or_404(project_id)
        project_dir = os.path.join('projects', f'project_{project_id}')
        full_path = os.path.join(project_dir, file_path)
        
        if not os.path.exists(full_path):
            flash('File not found', 'error')
            return redirect(url_for('project_detail', project_id=project_id))
        
        file_type = get_file_type(file_path)
        content = None
        
        if file_type == 'xml':
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except:
                with open(full_path, 'r', encoding='latin-1') as f:
                    content = f.read()
        
        return render_template('edit_file.html', project=project, 
                             file_path=file_path, file_type=file_type, content=content)
    
    @app.route('/save_file/<int:project_id>/<path:file_path>', methods=['POST'])
    def save_file(project_id, file_path):
        """Save edited file"""
        project = Project.query.get_or_404(project_id)
        project_dir = os.path.join('projects', f'project_{project_id}')
        full_path = os.path.join(project_dir, file_path)
        
        content = request.form.get('content', '')
        
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            flash('File saved successfully', 'success')
        except Exception as e:
            flash(f'Error saving file: {str(e)}', 'error')
        
        return redirect(url_for('project_detail', project_id=project_id))
    
    @app.route('/delete_project/<int:project_id>')
    def delete_project(project_id):
        """Delete project"""
        project = Project.query.get_or_404(project_id)
        
        try:
            # Delete project files
            project_dir = os.path.join('projects', f'project_{project_id}')
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
            
            if os.path.exists(project.path):
                os.remove(project.path)
            
            # Delete from database
            db.session.delete(project)
            db.session.commit()
            
            flash('Project deleted successfully', 'success')
        except Exception as e:
            flash(f'Error deleting project: {str(e)}', 'error')
        
        return redirect(url_for('index'))
    
    @app.errorhandler(413)
    def too_large(e):
        flash('File too large. Maximum size is 100MB.', 'error')
        return redirect(url_for('upload_apk'))
    
    def get_file_type(filename):
        """Get file type based on extension"""
        ext = filename.lower().split('.')[-1]
        if ext in ['png', 'jpg', 'jpeg', 'webp']:
            return 'image'
        elif ext == 'xml':
            return 'xml'
        else:
            return 'other'
    
    return app