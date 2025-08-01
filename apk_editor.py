"""
APK Editor - Core APK processing functionality
Handles decompilation, compilation, and signing of APK files
"""

import os
import subprocess
import shutil
import zipfile
import logging
from pathlib import Path

class APKEditor:
    """Main class for APK editing operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.apktool_path = self._find_apktool()
        self.java_path = self._find_java()
        
    def _find_apktool(self):
        """Find APKTool executable"""
        # Check common locations
        possible_paths = [
            'apktool.jar',
            'tools/apktool.jar',
            os.path.expanduser('~/apktool.jar'),
            '/usr/local/bin/apktool.jar'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(['which', 'apktool'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        return None
    
    def _find_java(self):
        """Find Java executable"""
        try:
            result = subprocess.run(['java', '-version'], capture_output=True, text=True)
            if result.returncode == 0:
                return 'java'
        except:
            pass
        
        return None
    
    def _run_command(self, command, cwd=None):
        """Run system command and return success status"""
        try:
            self.logger.info(f"Running command: {' '.join(command)}")
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                self.logger.info("Command executed successfully")
                return True
            else:
                self.logger.error(f"Command failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("Command timed out")
            return False
        except Exception as e:
            self.logger.error(f"Error running command: {e}")
            return False
    
    def decompile_apk(self, apk_path, output_dir):
        """Decompile APK file"""
        if not os.path.exists(apk_path):
            self.logger.error(f"APK file not found: {apk_path}")
            return False
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # If APKTool is available, use it
        if self.apktool_path and self.java_path:
            command = [
                self.java_path, '-jar', self.apktool_path,
                'd', apk_path, '-o', output_dir, '-f'
            ]
            return self._run_command(command)
        else:
            # Fallback: Extract APK as ZIP
            return self._extract_apk_as_zip(apk_path, output_dir)
    
    def _extract_apk_as_zip(self, apk_path, output_dir):
        """Extract APK file as a ZIP archive (fallback method)"""
        try:
            with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                zip_ref.extractall(output_dir)
            
            self.logger.info("APK extracted as ZIP (simulation mode)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error extracting APK: {e}")
            return False
    
    def compile_apk(self, project_dir, output_path):
        """Compile APK from project directory"""
        if not os.path.exists(project_dir):
            self.logger.error(f"Project directory not found: {project_dir}")
            return False
        
        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # If APKTool is available, use it
        if self.apktool_path and self.java_path:
            command = [
                self.java_path, '-jar', self.apktool_path,
                'b', project_dir, '-o', output_path
            ]
            success = self._run_command(command)
            
            if success:
                # Sign the APK
                return self._sign_apk(output_path)
            return False
        else:
            # Fallback: Create ZIP file
            return self._create_apk_as_zip(project_dir, output_path)
    
    def _create_apk_as_zip(self, project_dir, output_path):
        """Create APK file as ZIP (fallback method)"""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                for root, dirs, files in os.walk(project_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, project_dir)
                        zip_ref.write(file_path, arc_path)
            
            self.logger.info("APK created as ZIP (simulation mode)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating APK: {e}")
            return False
    
    def _sign_apk(self, apk_path):
        """Sign APK with debug keystore"""
        try:
            # Create debug keystore if it doesn't exist
            keystore_path = self._create_debug_keystore()
            
            if not keystore_path:
                self.logger.warning("Could not create keystore, APK will be unsigned")
                return True  # Continue without signing
            
            # Sign APK using jarsigner
            command = [
                'jarsigner', '-verbose', '-sigalg', 'SHA1withRSA',
                '-digestalg', 'SHA1', '-keystore', keystore_path,
                '-storepass', 'android', '-keypass', 'android',
                apk_path, 'androiddebugkey'
            ]
            
            return self._run_command(command)
            
        except Exception as e:
            self.logger.error(f"Error signing APK: {e}")
            return True  # Continue without signing
    
    def _create_debug_keystore(self):
        """Create debug keystore for signing"""
        keystore_path = 'debug.keystore'
        
        if os.path.exists(keystore_path):
            return keystore_path
        
        try:
            command = [
                'keytool', '-genkey', '-v', '-keystore', keystore_path,
                '-alias', 'androiddebugkey', '-keyalg', 'RSA',
                '-keysize', '2048', '-validity', '10000',
                '-storepass', 'android', '-keypass', 'android',
                '-dname', 'CN=Android Debug,O=Android,C=US'
            ]
            
            if self._run_command(command):
                return keystore_path
            
        except Exception as e:
            self.logger.error(f"Error creating keystore: {e}")
        
        return None
    
    def get_apk_info(self, apk_path):
        """Get APK information"""
        info = {
            'filename': os.path.basename(apk_path),
            'size': os.path.getsize(apk_path) if os.path.exists(apk_path) else 0,
            'valid': False
        }
        
        try:
            # Check if it's a valid ZIP file
            with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                files = zip_ref.namelist()
                
                # Check for essential APK files
                has_manifest = 'AndroidManifest.xml' in files
                has_dex = any(f.endswith('.dex') for f in files)
                
                info['valid'] = has_manifest and has_dex
                info['files_count'] = len(files)
                
        except Exception as e:
            self.logger.error(f"Error reading APK info: {e}")
        
        return info
    
    def is_ready(self):
        """Check if APK Editor is ready to use"""
        return {
            'apktool_available': self.apktool_path is not None,
            'java_available': self.java_path is not None,
            'ready': True,  # Basic functionality always available
            'simulation_mode': self.apktool_path is None
        }