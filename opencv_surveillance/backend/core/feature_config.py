# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Feature Configuration System
Defines hardware requirements and default states for all features
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass


class FeatureCategory(str, Enum):
    """Feature categories"""
    CORE = "core"
    DETECTION = "detection"
    OPTIMIZATION = "optimization"
    RECORDING = "recording"
    ADVANCED = "advanced"


class HardwareTier(str, Enum):
    """Hardware tier levels"""
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH_END = "high_end"


@dataclass
class FeatureRequirements:
    """Hardware requirements for a feature"""
    min_ram_gb: float = 0
    min_cpu_cores: int = 1
    min_cpu_threads: int = 1
    gpu_required: bool = False
    gpu_recommended: bool = False
    min_gpu_memory_mb: int = 0
    min_disk_free_gb: float = 1

    # Performance impact indicators (1-10, higher = more intensive)
    cpu_impact: int = 1
    ram_impact: int = 1
    gpu_impact: int = 0
    disk_impact: int = 1
    network_impact: int = 1


@dataclass
class FeatureConfig:
    """Complete feature configuration"""
    feature_id: str
    name: str
    description: str
    category: FeatureCategory
    default_enabled: bool
    requirements: FeatureRequirements

    # CPU fallback available?
    has_cpu_fallback: bool = True

    # Alternative configurations
    cpu_mode_available: bool = False
    gpu_mode_available: bool = False

    # Warnings
    performance_warning: Optional[str] = None
    compatibility_notes: Optional[str] = None


# ============================================================================
# FEATURE DEFINITIONS
# ============================================================================

FEATURES: Dict[str, FeatureConfig] = {

    # ========== CORE FEATURES (Always Available) ==========

    "motion_detection": FeatureConfig(
        feature_id="motion_detection",
        name="Motion Detection",
        description="Detect movement in camera frames using background subtraction",
        category=FeatureCategory.CORE,
        default_enabled=True,
        requirements=FeatureRequirements(
            min_ram_gb=2,
            min_cpu_cores=1,
            cpu_impact=2,
            ram_impact=1
        ),
        has_cpu_fallback=True,
        performance_warning=None
    ),

    "recording": FeatureConfig(
        feature_id="recording",
        name="Video Recording",
        description="Record video when motion is detected",
        category=FeatureCategory.RECORDING,
        default_enabled=True,
        requirements=FeatureRequirements(
            min_ram_gb=2,
            min_cpu_cores=1,
            min_disk_free_gb=5,
            cpu_impact=3,
            disk_impact=5
        ),
        has_cpu_fallback=True,
        compatibility_notes="Disk space required for recordings"
    ),

    # ========== DETECTION FEATURES ==========

    "face_recognition_hog": FeatureConfig(
        feature_id="face_recognition_hog",
        name="Face Recognition (CPU)",
        description="Detect and recognize faces using CPU-optimized HOG algorithm",
        category=FeatureCategory.DETECTION,
        default_enabled=True,
        requirements=FeatureRequirements(
            min_ram_gb=4,
            min_cpu_cores=2,
            cpu_impact=5,
            ram_impact=3
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        performance_warning="Processing time: ~300ms per frame on CPU"
    ),

    "face_recognition_cnn": FeatureConfig(
        feature_id="face_recognition_cnn",
        name="Face Recognition (GPU)",
        description="Fast face detection using GPU-accelerated CNN",
        category=FeatureCategory.DETECTION,
        default_enabled=False,  # OFF by default - requires GPU
        requirements=FeatureRequirements(
            min_ram_gb=8,
            min_cpu_cores=2,
            gpu_required=True,  # GPU required for this mode
            min_gpu_memory_mb=4096,
            cpu_impact=2,
            ram_impact=4,
            gpu_impact=7
        ),
        has_cpu_fallback=False,  # This IS the GPU mode
        gpu_mode_available=True,
        performance_warning="Requires NVIDIA GPU with CUDA support",
        compatibility_notes="6-15x faster than CPU mode (~20-50ms per frame)"
    ),

    "object_detection": FeatureConfig(
        feature_id="object_detection",
        name="Object Detection (YOLOv8)",
        description="Detect objects including weapons, vehicles, packages",
        category=FeatureCategory.ADVANCED,
        default_enabled=False,  # OFF by default - intensive
        requirements=FeatureRequirements(
            min_ram_gb=8,
            min_cpu_cores=4,
            gpu_recommended=True,  # Works on CPU but slow
            min_gpu_memory_mb=6144,
            cpu_impact=8,
            ram_impact=5,
            gpu_impact=8
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        gpu_mode_available=True,
        performance_warning="CPU mode: ~2-5 FPS | GPU mode: ~30+ FPS",
        compatibility_notes="GPU strongly recommended for real-time performance"
    ),

    "weapon_detection": FeatureConfig(
        feature_id="weapon_detection",
        name="Weapon Detection",
        description="Detect weapons (guns, knives) and hazardous materials",
        category=FeatureCategory.ADVANCED,
        default_enabled=False,  # OFF by default - requires object detection
        requirements=FeatureRequirements(
            min_ram_gb=8,
            min_cpu_cores=4,
            gpu_recommended=True,
            min_gpu_memory_mb=6144,
            cpu_impact=8,
            ram_impact=5,
            gpu_impact=8
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        gpu_mode_available=True,
        performance_warning="Requires Object Detection to be enabled",
        compatibility_notes="Part of object detection system"
    ),

    "license_plate_recognition": FeatureConfig(
        feature_id="license_plate_recognition",
        name="License Plate Recognition",
        description="Detect and read vehicle license plates",
        category=FeatureCategory.ADVANCED,
        default_enabled=False,  # OFF by default - intensive
        requirements=FeatureRequirements(
            min_ram_gb=6,
            min_cpu_cores=4,
            gpu_recommended=True,
            min_gpu_memory_mb=4096,
            cpu_impact=7,
            ram_impact=4,
            gpu_impact=6
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        gpu_mode_available=True,
        performance_warning="CPU mode: ~500ms per plate | GPU mode: ~50ms per plate",
        compatibility_notes="Works on CPU but GPU recommended for multiple cameras"
    ),

    "barcode_qr_detection": FeatureConfig(
        feature_id="barcode_qr_detection",
        name="Barcode & QR Code Detection",
        description="Detect and read barcodes, QR codes, package labels",
        category=FeatureCategory.DETECTION,
        default_enabled=False,  # OFF by default
        requirements=FeatureRequirements(
            min_ram_gb=4,
            min_cpu_cores=2,
            cpu_impact=4,
            ram_impact=2
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        performance_warning="Adds ~100ms processing time per frame",
        compatibility_notes="CPU-friendly, no GPU required"
    ),

    "badge_name_detection": FeatureConfig(
        feature_id="badge_name_detection",
        name="Name Tag / Badge Detection",
        description="Detect and extract text from name tags and badges",
        category=FeatureCategory.DETECTION,
        default_enabled=False,  # OFF by default
        requirements=FeatureRequirements(
            min_ram_gb=6,
            min_cpu_cores=2,
            gpu_recommended=True,
            min_gpu_memory_mb=2048,
            cpu_impact=6,
            ram_impact=3,
            gpu_impact=4
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        gpu_mode_available=True,
        performance_warning="Requires Face Recognition to locate badges",
        compatibility_notes="GPU recommended for real-time processing"
    ),

    # ========== OPTIMIZATION FEATURES ==========

    "adaptive_frame_rate": FeatureConfig(
        feature_id="adaptive_frame_rate",
        name="Adaptive Frame Rate",
        description="Skip frames when idle to reduce CPU usage (80% reduction)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - user choice
        requirements=FeatureRequirements(
            min_ram_gb=2,
            min_cpu_cores=1,
            cpu_impact=-6,  # Negative = reduces CPU usage
            ram_impact=0
        ),
        has_cpu_fallback=True,
        performance_warning=None,
        compatibility_notes="Highly recommended for systems with multiple cameras"
    ),

    "frame_resolution_scaling": FeatureConfig(
        feature_id="frame_resolution_scaling",
        name="Resolution Scaling",
        description="Process at lower resolution for detection (2-4x speedup)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - user choice
        requirements=FeatureRequirements(
            min_ram_gb=2,
            min_cpu_cores=1,
            cpu_impact=-4,  # Reduces CPU usage
            ram_impact=-1
        ),
        has_cpu_fallback=True,
        performance_warning=None,
        compatibility_notes="Recordings remain full resolution, only detection is scaled"
    ),

    "hardware_video_encoding": FeatureConfig(
        feature_id="hardware_video_encoding",
        name="Hardware Video Encoding",
        description="Use GPU/hardware encoder for recording (70-90% CPU reduction)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - requires hardware support
        requirements=FeatureRequirements(
            min_ram_gb=4,
            min_cpu_cores=2,
            gpu_recommended=True,
            cpu_impact=-7,  # Huge CPU reduction
            gpu_impact=3
        ),
        has_cpu_fallback=True,
        cpu_mode_available=True,
        gpu_mode_available=True,
        performance_warning="Requires NVIDIA NVENC or Intel QuickSync support",
        compatibility_notes="Check GPU/CPU compatibility before enabling"
    ),

    "parallel_processing": FeatureConfig(
        feature_id="parallel_processing",
        name="Parallel Frame Processing",
        description="Process motion/faces/objects concurrently (15-20% speedup)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - user choice
        requirements=FeatureRequirements(
            min_ram_gb=8,
            min_cpu_cores=4,
            min_cpu_threads=8,
            cpu_impact=-2,  # Slight speedup
            ram_impact=2
        ),
        has_cpu_fallback=True,
        performance_warning="Requires multi-core CPU for benefit",
        compatibility_notes="Best with 4+ cores, minimal benefit on dual-core"
    ),

    "redis_caching": FeatureConfig(
        feature_id="redis_caching",
        name="Redis Caching",
        description="Cache frequently accessed data (50-90% faster queries)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - requires Redis
        requirements=FeatureRequirements(
            min_ram_gb=4,  # Redis needs memory
            min_cpu_cores=2,
            cpu_impact=-3,  # Reduces DB load
            ram_impact=2
        ),
        has_cpu_fallback=True,
        performance_warning="Requires Redis server installation",
        compatibility_notes="Optional but recommended for 10+ cameras"
    ),

    "batch_database_inserts": FeatureConfig(
        feature_id="batch_database_inserts",
        name="Batch Database Writes",
        description="Group database writes for efficiency (10-50x faster)",
        category=FeatureCategory.OPTIMIZATION,
        default_enabled=False,  # OFF by default - user choice
        requirements=FeatureRequirements(
            min_ram_gb=4,
            min_cpu_cores=2,
            cpu_impact=-2,
            ram_impact=1
        ),
        has_cpu_fallback=True,
        performance_warning=None,
        compatibility_notes="Events may have 5-10 second delay before appearing in database"
    ),
}


def get_feature_config(feature_id: str) -> Optional[FeatureConfig]:
    """Get configuration for a specific feature"""
    return FEATURES.get(feature_id)


def get_features_by_category(category: FeatureCategory) -> List[FeatureConfig]:
    """Get all features in a category"""
    return [f for f in FEATURES.values() if f.category == category]


def get_all_features() -> Dict[str, FeatureConfig]:
    """Get all features"""
    return FEATURES


def get_features_for_hardware_tier(tier: HardwareTier) -> List[str]:
    """
    Get recommended features for a hardware tier

    Args:
        tier: Hardware tier level

    Returns:
        List of feature IDs recommended for this tier
    """
    recommended = []

    if tier == HardwareTier.MINIMAL:
        # Minimal: Only core features
        recommended = [
            "motion_detection",
            "recording",
            "adaptive_frame_rate",  # Critical for performance
            "frame_resolution_scaling"  # Critical for performance
        ]

    elif tier == HardwareTier.LOW:
        # Low: Core + basic detection
        recommended = [
            "motion_detection",
            "recording",
            "face_recognition_hog",  # CPU mode only
            "barcode_qr_detection",
            "adaptive_frame_rate",
            "frame_resolution_scaling",
            "batch_database_inserts"
        ]

    elif tier == HardwareTier.MEDIUM:
        # Medium: Most features, GPU optional
        recommended = [
            "motion_detection",
            "recording",
            "face_recognition_hog",  # or GPU if available
            "license_plate_recognition",
            "barcode_qr_detection",
            "badge_name_detection",
            "adaptive_frame_rate",
            "frame_resolution_scaling",
            "parallel_processing",
            "batch_database_inserts"
        ]

    elif tier == HardwareTier.HIGH_END:
        # High-end: All features enabled
        recommended = [
            "motion_detection",
            "recording",
            "face_recognition_cnn",  # GPU mode
            "object_detection",
            "weapon_detection",
            "license_plate_recognition",
            "barcode_qr_detection",
            "badge_name_detection",
            "hardware_video_encoding",
            "parallel_processing",
            "redis_caching",
            "batch_database_inserts"
        ]

    return recommended


def get_optimal_config_for_hardware(hardware_info: Dict) -> Dict:
    """
    Generate optimal configuration based on hardware

    Args:
        hardware_info: Hardware information dictionary

    Returns:
        Dict with optimal feature settings
    """
    # Determine tier
    gpu_available = hardware_info.get('gpu', {}).get('available', False)
    cpu_cores = hardware_info.get('cpu_cores', 1)
    ram_gb = hardware_info.get('ram_total_gb', 0)

    if gpu_available and cpu_cores >= 8 and ram_gb >= 32:
        tier = HardwareTier.HIGH_END
    elif (gpu_available and cpu_cores >= 4 and ram_gb >= 16) or (cpu_cores >= 8 and ram_gb >= 16):
        tier = HardwareTier.MEDIUM
    elif cpu_cores >= 2 and ram_gb >= 8:
        tier = HardwareTier.LOW
    else:
        tier = HardwareTier.MINIMAL

    # Get recommended features
    recommended_features = get_features_for_hardware_tier(tier)

    # Build config
    config = {
        'tier': tier.value,
        'features': {},
        'warnings': [],
        'recommendations': []
    }

    for feature_id, feature in FEATURES.items():
        # Should this feature be enabled?
        should_enable = feature_id in recommended_features

        # Can the hardware run it?
        can_run = True
        warnings = []

        if feature.requirements.gpu_required and not gpu_available:
            can_run = False
            warnings.append(f"{feature.name} requires GPU but none detected")

        if feature.requirements.min_ram_gb > ram_gb:
            can_run = False
            warnings.append(
                f"{feature.name} requires {feature.requirements.min_ram_gb}GB RAM "
                f"but only {ram_gb:.1f}GB available"
            )

        if feature.requirements.min_cpu_cores > cpu_cores:
            can_run = False
            warnings.append(
                f"{feature.name} requires {feature.requirements.min_cpu_cores} CPU cores "
                f"but only {cpu_cores} available"
            )

        # Add to config
        config['features'][feature_id] = {
            'enabled': should_enable and can_run,
            'can_run': can_run,
            'recommended': should_enable,
            'warnings': warnings,
            'use_gpu': gpu_available and (feature.gpu_mode_available or feature.requirements.gpu_required),
            'use_cpu': not gpu_available and feature.has_cpu_fallback
        }

    return config
