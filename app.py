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
    
    @app.route('/export_android_studio/<int:project_id>')
    def export_android_studio(project_id):
        """Export project for Android Studio"""
        project = Project.query.get_or_404(project_id)
        project_dir = os.path.join('projects', f'project_{project_id}')
        
        if not os.path.exists(project_dir):
            flash('Project not decompiled yet. Please decompile first.', 'error')
            return redirect(url_for('project_detail', project_id=project_id))
        
        try:
            # Create export ZIP
            export_path = os.path.join('temp', f'{project.name}_android_studio.zip')
            success = create_android_studio_export(project_dir, export_path, project.name)
            
            if success:
                return send_file(export_path, as_attachment=True,
                               download_name=f'{project.name}_android_studio.zip')
            else:
                flash('Failed to create Android Studio export', 'error')
                
        except Exception as e:
            flash(f'Error creating export: {str(e)}', 'error')
        
        return redirect(url_for('project_detail', project_id=project_id))
    
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
    
    def create_android_studio_export(project_dir, export_path, project_name):
        """Create Android Studio compatible project export"""
        try:
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                # Create Android Studio project structure
                
                # Add gradle wrapper
                gradle_wrapper_content = """#!/usr/bin/env sh
##############################################################################
##
##  Gradle start up script for UN*X
##
##############################################################################

# Attempt to set APP_HOME
# Resolve links: $0 may be a link
PRG="$0"
# Need this for relative symlinks.
while [ -h "$PRG" ] ; do
    ls=`ls -ld "$PRG"`
    link=`expr "$ls" : '.*-> \\(.*\\)$'`
    if expr "$link" : '/.*' > /dev/null; then
        PRG="$link"
    else
        PRG=`dirname "$PRG"`"/$link"
    fi
done
SAVED="`pwd`"
cd "`dirname \\"$PRG\\"`/" >/dev/null
APP_HOME="`pwd -P`"
cd "$SAVED" >/dev/null

APP_NAME="Gradle"
APP_BASE_NAME=`basename "$0"`

# Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
DEFAULT_JVM_OPTS='"-Xmx64m" "-Xms64m"'

# Use the maximum available, or set MAX_FD != -1 to use that value.
MAX_FD="maximum"

warn () {
    echo "$*"
}

die () {
    echo
    echo "$*"
    echo
    exit 1
}

# OS specific support (must be 'true' or 'false').
cygwin=false
msys=false
darwin=false
nonstop=false
case "`uname`" in
  CYGWIN* )
    cygwin=true
    ;;
  Darwin* )
    darwin=true
    ;;
  MINGW* )
    msys=true
    ;;
  NONSTOP* )
    nonstop=true
    ;;
esac

CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar

# Determine the Java command to use to start the JVM.
if [ -n "$JAVA_HOME" ] ; then
    if [ -x "$JAVA_HOME/jre/sh/java" ] ; then
        # IBM's JDK on AIX uses strange locations for the executables
        JAVACMD="$JAVA_HOME/jre/sh/java"
    else
        JAVACMD="$JAVA_HOME/bin/java"
    fi
    if [ ! -x "$JAVACMD" ] ; then
        die "ERROR: JAVA_HOME is set to an invalid directory: $JAVA_HOME

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
    fi
else
    JAVACMD="java"
    which java >/dev/null 2>&1 || die "ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.

Please set the JAVA_HOME variable in your environment to match the
location of your Java installation."
fi

# Increase the maximum file descriptors if we can.
if [ "$cygwin" = "false" -a "$darwin" = "false" -a "$nonstop" = "false" ] ; then
    MAX_FD_LIMIT=`ulimit -H -n`
    if [ $? -eq 0 ] ; then
        if [ "$MAX_FD" = "maximum" -o "$MAX_FD" = "max" ] ; then
            MAX_FD="$MAX_FD_LIMIT"
        fi
        ulimit -n $MAX_FD
        if [ $? -ne 0 ] ; then
            warn "Could not set maximum file descriptor limit: $MAX_FD"
        fi
    else
        warn "Could not query maximum file descriptor limit: $MAX_FD_LIMIT"
    fi
fi

# For Darwin, add options to specify how the application appears in the dock
if [ "$darwin" = "true" ]; then
    GRADLE_OPTS="$GRADLE_OPTS \\"-Xdock:name=$APP_NAME\\" \\"-Xdock:icon=$APP_HOME/media/gradle.icns\\""
fi

# For Cygwin or MSYS, switch paths to Windows format before running java
if [ "$cygwin" = "true" -o "$msys" = "true" ] ; then
    APP_HOME=`cygpath --path --mixed "$APP_HOME"`
    CLASSPATH=`cygpath --path --mixed "$CLASSPATH"`
    JAVACMD=`cygpath --unix "$JAVACMD"`

    # We build the pattern for arguments to be converted via cygpath
    ROOTDIRSRAW=`find -L / -maxdepth 1 -mindepth 1 -type d 2>/dev/null`
    SEP=""
    for dir in $ROOTDIRSRAW ; do
        ROOTDIRS="$ROOTDIRS$SEP$dir"
        SEP="|"
    done
    OURCYGPATTERN="(^($ROOTDIRS))"
    # Add a user-defined pattern to the cygpath arguments
    if [ "$GRADLE_CYGPATTERN" != "" ] ; then
        OURCYGPATTERN="$OURCYGPATTERN|($GRADLE_CYGPATTERN)"
    fi
    # Now convert the arguments - kludge to limit ourselves to /bin/sh
    i=0
    for arg in "$@" ; do
        CHECK=`echo "$arg"|egrep -c "$OURCYGPATTERN" -`
        CHECK2=`echo "$arg"|egrep -c "^-"`                                 ### Determine if an option

        if [ $CHECK -ne 0 ] && [ $CHECK2 -eq 0 ] ; then                    ### Added a condition
            eval `echo args$i`=`cygpath --path --ignore --mixed "$arg"`
        else
            eval `echo args$i`=\\"$arg\\"
        fi
        i=$((i+1))
    done
    case $i in
        (0) set -- ;;
        (1) set -- "$args0" ;;
        (2) set -- "$args0" "$args1" ;;
        (3) set -- "$args0" "$args1" "$args2" ;;
        (4) set -- "$args0" "$args1" "$args2" "$args3" ;;
        (5) set -- "$args0" "$args1" "$args2" "$args3" "$args4" ;;
        (6) set -- "$args0" "$args1" "$args2" "$args3" "$args4" "$args5" ;;
        (7) set -- "$args0" "$args1" "$args2" "$args3" "$args4" "$args5" "$args6" ;;
        (8) set -- "$args0" "$args1" "$args2" "$args3" "$args4" "$args5" "$args6" "$args7" ;;
        (9) set -- "$args0" "$args1" "$args2" "$args3" "$args4" "$args5" "$args6" "$args7" "$args8" ;;
    esac
fi

# Escape application args
save () {
    for i do printf %s\\\\%s "$1" "$i"; shift; done
    echo " "
}
APP_ARGS=$(save "$@")

# Collect all arguments for the java command
set -- $DEFAULT_JVM_OPTS $JAVA_OPTS $GRADLE_OPTS \\"-Dorg.gradle.appname=$APP_BASE_NAME\\" -classpath \\"$CLASSPATH\\" org.gradle.wrapper.GradleWrapperMain "$APP_ARGS"

exec "$JAVACMD" "$@"
"""
                zip_ref.writestr('gradlew', gradle_wrapper_content)
                
                # Add build.gradle (app level)
                app_build_gradle = f"""plugins {{
    id 'com.android.application'
}}

android {{
    namespace '{project_name.lower().replace(" ", "_")}'
    compileSdk 34

    defaultConfig {{
        applicationId "{project_name.lower().replace(" ", "_")}"
        minSdk 21
        targetSdk 34
        versionCode 1
        versionName "1.0"

        testInstrumentationRunner "androidx.test.runner.AndroidJUnitRunner"
    }}

    buildTypes {{
        release {{
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }}
    }}
    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }}
}}

dependencies {{
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.10.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    testImplementation 'junit:junit:4.13.2'
    androidTestImplementation 'androidx.test.ext:junit:1.1.5'
    androidTestImplementation 'androidx.test.espresso:espresso-core:3.5.1'
}}"""
                zip_ref.writestr('app/build.gradle', app_build_gradle)
                
                # Add settings.gradle
                settings_gradle = f"""pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{project_name}"
include ':app'
"""
                zip_ref.writestr('settings.gradle', settings_gradle)
                
                # Add build.gradle (project level)
                project_build_gradle = """plugins {
    id 'com.android.application' version '8.1.4' apply false
}"""
                zip_ref.writestr('build.gradle', project_build_gradle)
                
                # Add gradle.properties
                gradle_properties = """org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.enableJetifier=true"""
                zip_ref.writestr('gradle.properties', gradle_properties)
                
                # Copy original APK files to app/src/main
                for root, dirs, files in os.walk(project_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, project_dir)
                        
                        # Map APK structure to Android Studio structure
                        if arc_path.startswith('res/'):
                            new_path = f'app/src/main/{arc_path}'
                        elif arc_path == 'AndroidManifest.xml':
                            new_path = 'app/src/main/AndroidManifest.xml'
                        else:
                            # Put other files in assets
                            new_path = f'app/src/main/assets/{arc_path}'
                        
                        zip_ref.write(file_path, new_path)
                
                # Add proguard-rules.pro
                proguard_rules = """# Add project specific ProGuard rules here.
# You can control the set of applied configuration files using the
# proguardFiles setting in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# If your project uses WebView with JS, uncomment the following
# and specify the fully qualified class name to the JavaScript interface
# class:
#-keepclassmembers class fqcn.of.javascript.interface.for.webview {
#   public *;
#}

# Uncomment this to preserve the line number information for
# debugging stack traces.
#-keepattributes SourceFile,LineNumberTable

# If you keep the line number information, uncomment this to
# hide the original source file name.
#-renamesourcefileattribute SourceFile"""
                zip_ref.writestr('app/proguard-rules.pro', proguard_rules)
                
                # Add README
                readme_content = f"""# {project_name} - Android Studio Project

This project was exported from APK Editor and can be imported into Android Studio.

## Import Instructions:

1. Open Android Studio
2. Click "File" > "Open"
3. Select the extracted project folder
4. Click "OK" to import

## Project Structure:

- `app/src/main/AndroidManifest.xml` - Application manifest
- `app/src/main/res/` - Resources (layouts, drawables, values)
- `app/src/main/assets/` - Additional APK files

## Notes:

- This project contains the decompiled resources from the original APK
- You may need to add Java/Kotlin source files manually
- Some resources might need adjustment for proper compilation
- Consider using tools like jadx or dex2jar for source code recovery

## Building:

Run `./gradlew assembleDebug` to build a debug APK.
"""
                zip_ref.writestr('README.md', readme_content)
            
            return True
            
        except Exception as e:
            logging.error(f"Error creating Android Studio export: {e}")
            return False
    
    return app