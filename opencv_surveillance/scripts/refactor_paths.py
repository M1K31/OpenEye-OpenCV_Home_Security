#!/usr/bin/env python3
"""
Path Refactoring Script - Updates all hardcoded paths to use PathManager
"""

import re
from pathlib import Path

# Files to update
FILES_TO_UPDATE = [
    "backend/core/face_recognition.py",
    "backend/api/routes/faces.py",
    "backend/api/routes/cameras.py",
]

PROJECT_ROOT = Path(__file__).parent.parent

def refactor_face_recognition():
    """Update face_recognition.py"""
    file_path = PROJECT_ROOT / "backend/core/face_recognition.py"
    content = file_path.read_text()

    # Update os.listdir and os.path.join to use Path methods
    content = re.sub(
        r'for person_name in os\.listdir\(self\.faces_folder\):\s+person_path = os\.path\.join\(self\.faces_folder, person_name\)\s+if not os\.path\.isdir\(person_path\):\s+continue',
        '''for person_path in self.faces_folder.iterdir():
            if not person_path.is_dir():
                continue
            person_name = person_path.name''',
        content
    )

    # Update image file iteration
    content = re.sub(
        r'for image_file in os\.listdir\(person_path\):',
        'for image_file_path in person_path.iterdir():',
        content
    )

    # Update image_path construction
    content = re.sub(
        r'image_path = os\.path\.join\(person_path, image_file\)',
        'image_path = image_file_path',
        content
    )

    # Update image_file references to use .name
    content = re.sub(
        r'if not image_file\.lower\(\)\.endswith',
        'if not image_file_path.name.lower().endswith',
        content
    )

    # Update delete_person
    content = re.sub(
        r'person_path = os\.path\.join\(self\.faces_folder, person_name\)',
        'person_path = self.faces_folder / person_name',
        content
    )

    # Update os.path.exists to Path.exists()
    content = re.sub(
        r'if os\.path\.exists\(person_path\):',
        'if person_path.exists():',
        content
    )

    file_path.write_text(content)
    print(f"✅ Updated {file_path}")

def refactor_faces_api():
    """Update faces.py API routes"""
    file_path = PROJECT_ROOT / "backend/api/routes/faces.py"
    content = file_path.read_text()

    # Add PathManager import if not present
    if 'from backend.core.paths import paths' not in content:
        content = content.replace(
            'from backend.core.face_recognition import get_face_manager',
            'from backend.core.face_recognition import get_face_manager\nfrom backend.core.paths import paths'
        )

    # Replace all os.path.join(face_manager.faces_folder, ...) with paths.faces_dir / ...
    content = re.sub(
        r'person_path = os\.path\.join\(face_manager\.faces_folder, ([^)]+)\)',
        r'person_path = paths.faces_dir / \1',
        content
    )

    # Replace os.path.exists with Path.exists()
    content = re.sub(
        r'if os\.path\.exists\(([^)]+)\):',
        r'if (\1).exists():',
        content
    )

    # Replace face_manager.faces_folder references in return statements
    content = re.sub(
        r'faces_folder=face_manager\.faces_folder',
        'faces_folder=str(paths.faces_dir)',
        content
    )

    file_path.write_text(content)
    print(f"✅ Updated {file_path}")

def refactor_cameras_api():
    """Update cameras.py API routes"""
    file_path = PROJECT_ROOT / "backend/api/routes/cameras.py"
    content = file_path.read_text()

    # Add PathManager import if not present
    if 'from backend.core.paths import paths' not in content:
        # Find the imports section
        import_section_end = content.find('\nrouter = APIRouter()')
        if import_section_end > 0:
            imports = content[:import_section_end]
            rest = content[import_section_end:]
            imports += '\nfrom backend.core.paths import paths'
            content = imports + rest

    # Replace hardcoded snapshots path
    content = re.sub(
        r'snapshots_dir = os\.path\.join\("data", "snapshots"\)\s+os\.makedirs\(snapshots_dir, exist_ok=True\)',
        'snapshots_dir = paths.snapshots_dir\n    snapshots_dir.mkdir(parents=True, exist_ok=True)',
        content
    )

    # Replace filepath construction
    content = re.sub(
        r'filepath = os\.path\.join\(snapshots_dir, filename\)',
        'filepath = snapshots_dir / filename',
        content
    )

    # Update cv2.imwrite to use str()
    content = re.sub(
        r'cv2\.imwrite\(filepath, frame\)',
        'cv2.imwrite(str(filepath), frame)',
        content
    )

    file_path.write_text(content)
    print(f"✅ Updated {file_path}")

def main():
    print("🔧 Path Refactoring Script")
    print("=" * 50)

    refactor_face_recognition()
    refactor_faces_api()
    refactor_cameras_api()

    print("=" * 50)
    print("✅ All files updated successfully!")
    print("\nNext steps:")
    print("1. Review the changes")
    print("2. Test the application")
    print("3. Commit the refactoring")

if __name__ == "__main__":
    main()
