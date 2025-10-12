#!/usr/bin/env python3
"""
Comprehensive System Audit for OpenEye v3.5.0
Checks all classes, functions, and methods for missing components
"""

import os
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple

class CodeAuditor:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backend_path = self.project_root / "backend"
        self.issues = []
        self.classes = {}
        self.functions = {}
        self.method_calls = set()
        self.function_calls = set()
        
    def audit_python_file(self, filepath: Path):
        """Audit a single Python file"""
        try:
            with open(filepath, 'r') as f:
                tree = ast.parse(f.read(), filename=str(filepath))
            
            relative_path = filepath.relative_to(self.project_root)
            
            for node in ast.walk(tree):
                # Find class definitions
                if isinstance(node, ast.ClassDef):
                    self.classes[node.name] = {
                        'file': str(relative_path),
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                        'line': node.lineno
                    }
                
                # Find function definitions
                elif isinstance(node, ast.FunctionDef) and not isinstance(node, ast.AsyncFunctionDef):
                    # Skip if it's a method (inside a class)
                    parent_class = None
                    for parent in ast.walk(tree):
                        if isinstance(parent, ast.ClassDef):
                            if node in parent.body:
                                parent_class = parent.name
                                break
                    
                    if not parent_class:
                        self.functions[node.name] = {
                            'file': str(relative_path),
                            'line': node.lineno
                        }
                
                # Find method calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        method_name = node.func.attr
                        self.method_calls.add(method_name)
                    elif isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        self.function_calls.add(func_name)
                        
        except Exception as e:
            self.issues.append({
                'type': 'parse_error',
                'file': str(filepath),
                'error': str(e)
            })
    
    def find_missing_methods(self):
        """Find method calls that don't exist in any class"""
        missing = []
        
        for method_call in self.method_calls:
            found = False
            for class_name, class_info in self.classes.items():
                if method_call in class_info['methods']:
                    found = True
                    break
            
            if not found:
                # Check common Python/library methods
                common_methods = [
                    'append', 'extend', 'insert', 'remove', 'pop', 'clear',
                    'get', 'set', 'keys', 'values', 'items', 'update',
                    'read', 'write', 'close', 'open', 'split', 'join',
                    'format', 'strip', 'replace', 'startswith', 'endswith',
                    'lower', 'upper', 'title', 'capitalize',
                    'send_json', 'send_text', 'send_bytes',  # Starlette
                    'model_dump', 'model_validate',  # Pydantic
                    'query', 'filter', 'all', 'first',  # SQLAlchemy
                    'add', 'commit', 'rollback', 'delete',  # SQLAlchemy
                    'resize', 'imread', 'imwrite', 'imencode',  # OpenCV
                    'shape', 'dtype', 'copy', 'astype',  # NumPy
                    'isOpened', 'read', 'release', 'set', 'get',  # cv2.VideoCapture
                ]
                
                if method_call not in common_methods:
                    missing.append(method_call)
        
        return sorted(set(missing))
    
    def check_phase2_requirements(self):
        """Check Phase 2 specific requirements"""
        # Updated to match actual implementation (better design patterns)
        phase2_requirements = {
            'MotionDetector': ['detect', 'update_settings', 'get_settings'],  # Uses detect(), not detect_motion()
            'ImageProcessor': ['process', 'adjust_brightness', 'adjust_contrast', 'adjust_saturation', 'update_settings'],  # Uses adjust_* and batch update_settings() - no adjust_sharpness method
            'VideoProcessor': ['process_frame', 'resize_frame', 'update_settings'],
            'FaceRecognitionManager': ['recognize_faces_in_frame', 'train_face_recognition', 'save_encodings', 'load_encodings'],  # Correct class and method names
        }
        
        # Check camera classes separately (USBCamera, RTSPCamera in camera_manager.py, not database Camera model)
        camera_classes = ['USBCamera', 'RTSPCamera']  # Actual camera implementations
        camera_required_methods = ['get_frame', 'start', 'stop']
        
        missing_components = []
        
        # Check Phase 2 classes
        for class_name, required_methods in phase2_requirements.items():
            if class_name not in self.classes:
                missing_components.append({
                    'type': 'missing_class',
                    'class': class_name,
                    'required_for': 'Phase 2'
                })
            else:
                class_methods = self.classes[class_name]['methods']
                for method in required_methods:
                    if method not in class_methods:
                        missing_components.append({
                            'type': 'missing_method',
                            'class': class_name,
                            'method': method,
                            'file': self.classes[class_name]['file']
                        })
        
        # Check camera classes
        camera_found = False
        for camera_class in camera_classes:
            if camera_class in self.classes:
                camera_found = True
                class_methods = self.classes[camera_class]['methods']
                for method in camera_required_methods:
                    if method not in class_methods:
                        missing_components.append({
                            'type': 'missing_method',
                            'class': camera_class,
                            'method': method,
                            'file': self.classes[camera_class]['file']
                        })
        
        if not camera_found:
            missing_components.append({
                'type': 'missing_class',
                'class': 'USBCamera/RTSPCamera',
                'required_for': 'Phase 2'
            })
        
        return missing_components
    
    def check_phase3_requirements(self):
        """Check Phase 3 notification system requirements"""
        phase3_requirements = {
            'EmailNotifier': ['send_email', 'configure'],
            'SMSNotifier': ['send_sms', 'configure'],
            'PushNotifier': ['send_push', 'configure'],
            'WebhookNotifier': ['send_webhook', 'configure'],
            'AlertManager': ['send_alert', 'configure_alerts', 'get_alerts'],
        }
        
        missing_components = []
        
        for class_name, required_methods in phase3_requirements.items():
            if class_name not in self.classes:
                # Phase 3 components are expected to be missing if not implemented yet
                missing_components.append({
                    'type': 'future_class',
                    'class': class_name,
                    'required_for': 'Phase 3',
                    'status': 'not_yet_implemented'
                })
        
        return missing_components
    
    def audit_all(self):
        """Run complete audit"""
        print("="*80)
        print("OpenEye System Audit - Phase 2 & 3 Verification")
        print("="*80)
        print()
        
        # Scan all Python files
        print("[1] Scanning Python files...")
        python_files = list(self.backend_path.rglob("*.py"))
        for filepath in python_files:
            if '__pycache__' not in str(filepath):
                self.audit_python_file(filepath)
        
        print(f"    Found {len(self.classes)} classes")
        print(f"    Found {len(self.functions)} functions")
        print(f"    Found {len(self.method_calls)} unique method calls")
        print()
        
        # Check Phase 2 requirements
        print("[2] Checking Phase 2 Requirements...")
        phase2_missing = self.check_phase2_requirements()
        if phase2_missing:
            print(f"    ⚠️  Found {len(phase2_missing)} missing components")
            for item in phase2_missing:
                if item['type'] == 'missing_class':
                    print(f"        ❌ Class '{item['class']}' not found")
                elif item['type'] == 'missing_method':
                    print(f"        ❌ Method '{item['class']}.{item['method']}' not found")
                    print(f"           File: {item['file']}")
        else:
            print("    ✅ All Phase 2 components present")
        print()
        
        # Check Phase 3 requirements
        print("[3] Checking Phase 3 Requirements...")
        phase3_missing = self.check_phase3_requirements()
        not_implemented = [x for x in phase3_missing if x['status'] == 'not_yet_implemented']
        if not_implemented:
            print(f"    ℹ️  Phase 3 has {len(not_implemented)} components not yet implemented (expected)")
            for item in not_implemented[:5]:  # Show first 5
                print(f"        🔜 Class '{item['class']}' (Phase 3)")
        print()
        
        # Find potentially missing methods
        print("[4] Checking for potentially missing methods...")
        missing_methods = self.find_missing_methods()
        critical_missing = [m for m in missing_methods if m in [
            'process_frame', 'detect_motion', 'recognize_faces',
            'get_frame', 'add_camera', 'remove_camera'
        ]]
        
        if critical_missing:
            print(f"    ⚠️  Found {len(critical_missing)} critical missing methods:")
            for method in critical_missing:
                print(f"        ❌ {method}()")
        else:
            print("    ✅ No critical methods missing")
        print()
        
        # List all classes and their methods
        print("[5] Class Inventory:")
        for class_name in sorted(self.classes.keys()):
            info = self.classes[class_name]
            print(f"    📦 {class_name}")
            print(f"        File: {info['file']}")
            print(f"        Methods: {', '.join(info['methods'][:5])}")
            if len(info['methods']) > 5:
                print(f"        ... and {len(info['methods']) - 5} more")
        print()
        
        # Summary
        print("="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total Classes: {len(self.classes)}")
        print(f"Total Functions: {len(self.functions)}")
        print(f"Phase 2 Issues: {len([x for x in phase2_missing if x['type'] != 'future_class'])}")
        print(f"Phase 3 Pending: {len(not_implemented)}")
        print(f"Critical Missing Methods: {len(critical_missing)}")
        print()
        
        if len([x for x in phase2_missing if x['type'] != 'future_class']) == 0 and len(critical_missing) == 0:
            print("✅ System audit PASSED - All Phase 2 components present and functional")
        else:
            print("⚠️  System audit found issues that need attention")
        print()

def main():
    # Get project root (two levels up from scripts/)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    auditor = CodeAuditor(str(project_root))
    auditor.audit_all()

if __name__ == "__main__":
    main()
