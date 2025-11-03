"""
Hardware Detection & Feature Management API
Provides hardware information and feature recommendations
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel

from backend.database.session import get_db
from backend.core.auth import get_current_user
from backend.core.hardware_detector import get_hardware_detector, refresh_hardware_detection
from backend.core.feature_config import (
    get_feature_config,
    get_all_features,
    get_features_by_category,
    get_optimal_config_for_hardware,
    FeatureCategory
)

router = APIRouter()


# ===== Pydantic Schemas =====

class HardwareInfoResponse(BaseModel):
    """Hardware information response"""
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    cpu_frequency_mhz: float
    ram_total_gb: float
    ram_available_gb: float
    ram_used_percent: float
    disk_total_gb: float
    disk_free_gb: float
    disk_used_percent: float
    gpu_available: bool
    gpu_name: str
    gpu_memory_total_mb: int
    gpu_memory_free_mb: int
    cuda_version: Optional[str]
    platform: str
    os_version: str
    python_version: str


class FeatureCapabilityResponse(BaseModel):
    """Feature capability check response"""
    feature_id: str
    feature_name: str
    can_run: bool
    warnings: List[str]
    requirements: Dict
    has_cpu_fallback: bool
    has_gpu_mode: bool
    recommended: bool


class OptimalConfigResponse(BaseModel):
    """Optimal configuration recommendation"""
    hardware_tier: str
    features: Dict[str, Dict]
    warnings: List[str]
    recommendations: List[str]


# ===== API Endpoints =====

@router.get("/hardware/info")
async def get_hardware_info(
    current_user: dict = Depends(get_current_user)
) -> HardwareInfoResponse:
    """
    Get complete hardware information

    Returns detailed information about CPU, RAM, GPU, and storage
    """
    detector = get_hardware_detector()
    hw_info = detector.get_hardware_info()

    return HardwareInfoResponse(
        cpu_model=hw_info.cpu_model,
        cpu_cores=hw_info.cpu_cores,
        cpu_threads=hw_info.cpu_threads,
        cpu_frequency_mhz=hw_info.cpu_frequency_mhz,
        ram_total_gb=hw_info.ram_total_gb,
        ram_available_gb=hw_info.ram_available_gb,
        ram_used_percent=hw_info.ram_used_percent,
        disk_total_gb=hw_info.disk_total_gb,
        disk_free_gb=hw_info.disk_free_gb,
        disk_used_percent=hw_info.disk_used_percent,
        gpu_available=hw_info.gpu.available,
        gpu_name=hw_info.gpu.name,
        gpu_memory_total_mb=hw_info.gpu.memory_total_mb,
        gpu_memory_free_mb=hw_info.gpu.memory_free_mb,
        cuda_version=hw_info.gpu.cuda_version,
        platform=hw_info.platform,
        os_version=hw_info.os_version,
        python_version=hw_info.python_version
    )


@router.post("/hardware/refresh")
async def refresh_hardware_info(
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Refresh hardware detection

    Forces a new hardware scan. Use this after hardware changes.
    """
    detector = refresh_hardware_detection()
    hw_info = detector.get_hardware_info()

    return {
        "message": "Hardware detection refreshed",
        "cpu_cores": hw_info.cpu_cores,
        "ram_total_gb": hw_info.ram_total_gb,
        "gpu_available": hw_info.gpu.available,
        "gpu_name": hw_info.gpu.name if hw_info.gpu.available else None
    }


@router.get("/hardware/tier")
async def get_hardware_tier(
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get hardware tier classification

    Returns:
        - tier: minimal, low, medium, or high_end
        - max_cameras: Recommended maximum cameras
        - recommendations: List of recommendations
    """
    detector = get_hardware_detector()
    recommendations = detector.get_recommended_config()

    return {
        "tier": recommendations['hardware_tier'],
        "max_cameras": recommendations['max_cameras'],
        "processing_resolution": recommendations['processing_resolution'],
        "recommendations": recommendations
    }


@router.get("/features/all")
async def list_all_features(
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    List all available features with their requirements

    Returns complete feature catalog with hardware requirements
    """
    features = get_all_features()

    features_list = []
    for feature_id, feature in features.items():
        features_list.append({
            'feature_id': feature.feature_id,
            'name': feature.name,
            'description': feature.description,
            'category': feature.category.value,
            'default_enabled': feature.default_enabled,
            'requirements': {
                'min_ram_gb': feature.requirements.min_ram_gb,
                'min_cpu_cores': feature.requirements.min_cpu_cores,
                'gpu_required': feature.requirements.gpu_required,
                'gpu_recommended': feature.requirements.gpu_recommended,
                'min_gpu_memory_mb': feature.requirements.min_gpu_memory_mb,
            },
            'has_cpu_fallback': feature.has_cpu_fallback,
            'cpu_mode_available': feature.cpu_mode_available,
            'gpu_mode_available': feature.gpu_mode_available,
            'performance_impact': {
                'cpu': feature.requirements.cpu_impact,
                'ram': feature.requirements.ram_impact,
                'gpu': feature.requirements.gpu_impact,
                'disk': feature.requirements.disk_impact,
            },
            'performance_warning': feature.performance_warning,
            'compatibility_notes': feature.compatibility_notes
        })

    return {
        'features': features_list,
        'total': len(features_list)
    }


@router.get("/features/category/{category}")
async def list_features_by_category(
    category: str,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    List features by category

    Categories: core, detection, optimization, recording, advanced
    """
    try:
        cat_enum = FeatureCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {[c.value for c in FeatureCategory]}"
        )

    features = get_features_by_category(cat_enum)

    features_list = []
    for feature in features:
        features_list.append({
            'feature_id': feature.feature_id,
            'name': feature.name,
            'description': feature.description,
            'default_enabled': feature.default_enabled,
            'has_cpu_fallback': feature.has_cpu_fallback
        })

    return {
        'category': category,
        'features': features_list,
        'total': len(features_list)
    }


@router.get("/features/{feature_id}/check")
async def check_feature_capability(
    feature_id: str,
    current_user: dict = Depends(get_current_user)
) -> FeatureCapabilityResponse:
    """
    Check if hardware can run a specific feature

    Returns:
        - can_run: Whether hardware meets minimum requirements
        - warnings: List of warnings/issues
        - recommended: Whether feature is recommended for this hardware
    """
    feature = get_feature_config(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    detector = get_hardware_detector()

    # Check if hardware can run this feature
    can_run, warnings = detector.can_run_feature({
        'min_ram_gb': feature.requirements.min_ram_gb,
        'min_cpu_cores': feature.requirements.min_cpu_cores,
        'gpu_required': feature.requirements.gpu_required,
        'min_gpu_memory_mb': feature.requirements.min_gpu_memory_mb,
        'min_disk_free_gb': feature.requirements.min_disk_free_gb
    })

    # Get optimal config to see if feature is recommended
    hw_info = detector.get_hardware_dict()
    optimal = get_optimal_config_for_hardware(hw_info)
    recommended = optimal['features'].get(feature_id, {}).get('recommended', False)

    return FeatureCapabilityResponse(
        feature_id=feature.feature_id,
        feature_name=feature.name,
        can_run=can_run,
        warnings=warnings,
        requirements={
            'min_ram_gb': feature.requirements.min_ram_gb,
            'min_cpu_cores': feature.requirements.min_cpu_cores,
            'gpu_required': feature.requirements.gpu_required,
            'gpu_recommended': feature.requirements.gpu_recommended,
            'min_gpu_memory_mb': feature.requirements.min_gpu_memory_mb,
        },
        has_cpu_fallback=feature.has_cpu_fallback,
        has_gpu_mode=feature.gpu_mode_available,
        recommended=recommended
    )


@router.get("/features/optimal-config")
async def get_optimal_configuration(
    current_user: dict = Depends(get_current_user)
) -> OptimalConfigResponse:
    """
    Get optimal feature configuration for current hardware

    Returns recommended settings for all features based on detected hardware
    """
    detector = get_hardware_detector()
    hw_info = detector.get_hardware_dict()

    optimal = get_optimal_config_for_hardware(hw_info)

    # Generate user-friendly recommendations
    recommendations = []

    tier = optimal['tier']
    recommendations.append(f"Your hardware is classified as: {tier}")

    if tier == "minimal":
        recommendations.append("Consider upgrading RAM to 8GB for better performance")
        recommendations.append("Enable Adaptive Frame Rate and Resolution Scaling to reduce CPU usage")
    elif tier == "low":
        recommendations.append("Adding a GPU (GTX 1660 or better) would enable GPU-accelerated features")
        recommendations.append("Consider enabling optimization features for better performance")
    elif tier == "medium":
        recommendations.append("Your hardware can handle most features comfortably")
        if not hw_info.get('gpu', {}).get('available'):
            recommendations.append("Adding a GPU would enable real-time object detection")
    elif tier == "high_end":
        recommendations.append("Your hardware can run all features at maximum quality")
        recommendations.append("Consider enabling all advanced detection features")

    # GPU-specific recommendations
    if hw_info.get('gpu', {}).get('available'):
        gpu_mem = hw_info['gpu']['memory_total_mb']
        if gpu_mem >= 8192:
            recommendations.append("Your GPU has sufficient memory for all AI features")
        elif gpu_mem >= 6144:
            recommendations.append("Your GPU can handle object detection and license plate recognition")
        elif gpu_mem >= 4096:
            recommendations.append("Your GPU is suitable for face recognition in GPU mode")
        else:
            recommendations.append("Your GPU has limited memory - stick with CPU mode for detection")

    return OptimalConfigResponse(
        hardware_tier=tier,
        features=optimal['features'],
        warnings=optimal.get('warnings', []),
        recommendations=recommendations
    )


@router.get("/features/{feature_id}/impact")
async def get_feature_impact(
    feature_id: str,
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get detailed performance impact of enabling a feature

    Returns estimated CPU/RAM/GPU impact
    """
    feature = get_feature_config(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    detector = get_hardware_detector()
    hw_info = detector.get_hardware_info()

    # Calculate estimated impact
    impact = {
        'feature_name': feature.name,
        'performance_impact': {
            'cpu_impact': feature.requirements.cpu_impact,
            'ram_impact': feature.requirements.ram_impact,
            'gpu_impact': feature.requirements.gpu_impact,
            'disk_impact': feature.requirements.disk_impact,
            'network_impact': feature.requirements.network_impact
        },
        'estimated_resource_usage': {
            'cpu_usage_percent': min(100, feature.requirements.cpu_impact * 10),
            'ram_usage_mb': feature.requirements.ram_impact * 500,
            'gpu_usage_percent': min(100, feature.requirements.gpu_impact * 10) if hw_info.gpu.available else 0
        },
        'current_hardware_status': {
            'ram_available_gb': hw_info.ram_available_gb,
            'ram_sufficient': hw_info.ram_total_gb >= feature.requirements.min_ram_gb,
            'cpu_cores': hw_info.cpu_cores,
            'cpu_sufficient': hw_info.cpu_cores >= feature.requirements.min_cpu_cores,
            'gpu_available': hw_info.gpu.available,
            'gpu_required': feature.requirements.gpu_required,
            'gpu_recommended': feature.requirements.gpu_recommended
        },
        'warnings': []
    }

    # Add warnings
    if feature.requirements.gpu_required and not hw_info.gpu.available:
        impact['warnings'].append("This feature requires a GPU but none was detected")

    if feature.requirements.cpu_impact >= 7:
        impact['warnings'].append("This feature is CPU-intensive and may affect other processes")

    if feature.requirements.ram_impact >= 5:
        impact['warnings'].append("This feature uses significant RAM")

    if hw_info.ram_available_gb < feature.requirements.min_ram_gb:
        impact['warnings'].append(
            f"Insufficient RAM: {hw_info.ram_available_gb:.1f}GB available, "
            f"{feature.requirements.min_ram_gb}GB required"
        )

    return impact


@router.get("/optimization/stats")
async def get_optimization_stats(
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get current optimization statistics

    Returns statistics for adaptive frame rate and resolution scaling if enabled
    """
    # TODO: Implement statistics collection from running cameras
    # For now, return placeholder
    return {
        "message": "Optimization statistics will be available once cameras are running with optimizations enabled",
        "available_optimizations": [
            "adaptive_frame_rate",
            "resolution_scaling",
            "hardware_encoding",
            "parallel_processing",
            "batch_database_inserts",
            "redis_caching"
        ]
    }
