# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Monkey-patch for face_recognition_models to fix pkg_resources deprecation warning

The face_recognition_models package (v0.3.0) uses deprecated pkg_resources.
This module patches it to use importlib.resources instead (Python 3.9+).

This patch is applied at application startup before face_recognition is imported.

Warning being fixed:
    UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html.
    The pkg_resources package is slated for removal as early as 2025-11-30.
    Refrain from using this package or pin to Setuptools<81.

This can be removed once face_recognition_models is updated upstream.
"""
import sys
import importlib.resources as resources
from pathlib import Path


def patch_face_recognition_models():
    """
    Monkey-patch face_recognition_models to use importlib.resources
    instead of deprecated pkg_resources.

    This function should be called before importing face_recognition.
    """
    # Check if face_recognition_models is already imported
    if "face_recognition_models" in sys.modules:
        # Already imported, patch it in place
        module = sys.modules["face_recognition_models"]
    else:
        # Import it fresh
        import face_recognition_models as module

    # Get the package path using importlib.resources
    try:
        # Python 3.9+: Use files() API
        if hasattr(resources, 'files'):
            package_path = resources.files('face_recognition_models')
            models_path = package_path / 'models'

            def get_model_path(model_filename: str) -> str:
                """Get model file path using importlib.resources"""
                model_file = models_path / model_filename
                # Convert to string path
                return str(model_file)

        # Python 3.7-3.8 fallback: Use read_binary location
        else:
            import face_recognition_models
            package_dir = Path(face_recognition_models.__file__).parent
            models_dir = package_dir / 'models'

            def get_model_path(model_filename: str) -> str:
                """Get model file path using package __file__"""
                return str(models_dir / model_filename)

        # Replace the functions in the module
        module.pose_predictor_model_location = lambda: get_model_path(
            "shape_predictor_68_face_landmarks.dat"
        )
        module.pose_predictor_five_point_model_location = lambda: get_model_path(
            "shape_predictor_5_face_landmarks.dat"
        )
        module.face_recognition_model_location = lambda: get_model_path(
            "dlib_face_recognition_resnet_model_v1.dat"
        )
        module.cnn_face_detector_model_location = lambda: get_model_path(
            "mmod_human_face_detector.dat"
        )

        # Update the module in sys.modules
        sys.modules["face_recognition_models"] = module

        return True

    except Exception as e:
        # If patching fails, log the error but don't crash
        print(f"Warning: Failed to patch face_recognition_models: {e}")
        print("The pkg_resources deprecation warning will still appear.")
        return False


def is_patch_needed() -> bool:
    """
    Check if the patch is needed.

    Returns:
        True if face_recognition_models uses pkg_resources, False otherwise
    """
    try:
        import face_recognition_models
        # Check if the module has the original implementation
        source_file = face_recognition_models.__file__
        if source_file:
            with open(source_file, 'r') as f:
                content = f.read()
                return 'pkg_resources' in content
    except Exception:
        pass
    return False


# Auto-apply patch when this module is imported
if __name__ != "__main__":
    # Only patch if needed
    if is_patch_needed():
        success = patch_face_recognition_models()
        if success:
            print("✓ Successfully patched face_recognition_models to use importlib.resources")
