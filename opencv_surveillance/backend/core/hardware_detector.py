# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Hardware Detection System
Detects available hardware resources and recommends optimal configurations
"""

import platform
import psutil
import os
import subprocess
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU information"""
    available: bool
    name: str
    memory_total_mb: int
    memory_free_mb: int
    cuda_version: Optional[str]
    compute_capability: Optional[str]


@dataclass
class HardwareInfo:
    """Complete hardware information"""
    # CPU
    cpu_model: str
    cpu_cores: int
    cpu_threads: int
    cpu_frequency_mhz: float

    # Memory
    ram_total_gb: float
    ram_available_gb: float
    ram_used_percent: float

    # Storage
    disk_total_gb: float
    disk_free_gb: float
    disk_used_percent: float

    # GPU
    gpu: GPUInfo

    # System
    platform: str
    os_version: str
    python_version: str


class HardwareDetector:
    """
    Detects available hardware and provides recommendations
    """

    def __init__(self):
        self.hardware_info: Optional[HardwareInfo] = None
        self.detect_hardware()

    def detect_hardware(self) -> HardwareInfo:
        """
        Detect all available hardware

        Returns:
            HardwareInfo object with complete hardware details
        """
        logger.info("Detecting hardware...")

        # Detect CPU
        cpu_info = self._detect_cpu()

        # Detect Memory
        memory_info = self._detect_memory()

        # Detect Storage
        storage_info = self._detect_storage()

        # Detect GPU
        gpu_info = self._detect_gpu()

        # System info
        system_info = self._detect_system()

        # Combine all info
        self.hardware_info = HardwareInfo(
            **cpu_info,
            **memory_info,
            **storage_info,
            gpu=gpu_info,
            **system_info
        )

        logger.info(f"Hardware detection complete: {self.hardware_info.cpu_cores} cores, "
                   f"{self.hardware_info.ram_total_gb:.1f}GB RAM, "
                   f"GPU: {self.hardware_info.gpu.name if self.hardware_info.gpu.available else 'None'}")

        return self.hardware_info

    def _detect_cpu(self) -> Dict:
        """Detect CPU information"""
        try:
            cpu_freq = psutil.cpu_freq()

            return {
                'cpu_model': platform.processor() or "Unknown CPU",
                'cpu_cores': psutil.cpu_count(logical=False) or 1,
                'cpu_threads': psutil.cpu_count(logical=True) or 1,
                'cpu_frequency_mhz': cpu_freq.current if cpu_freq else 0.0
            }
        except Exception as e:
            logger.warning(f"Error detecting CPU: {e}")
            return {
                'cpu_model': "Unknown",
                'cpu_cores': 1,
                'cpu_threads': 1,
                'cpu_frequency_mhz': 0.0
            }

    def _detect_memory(self) -> Dict:
        """Detect memory information"""
        try:
            mem = psutil.virtual_memory()

            return {
                'ram_total_gb': mem.total / (1024 ** 3),
                'ram_available_gb': mem.available / (1024 ** 3),
                'ram_used_percent': mem.percent
            }
        except Exception as e:
            logger.warning(f"Error detecting memory: {e}")
            return {
                'ram_total_gb': 0.0,
                'ram_available_gb': 0.0,
                'ram_used_percent': 0.0
            }

    def _detect_storage(self, path: str = "/") -> Dict:
        """Detect storage information"""
        try:
            disk = psutil.disk_usage(path)

            return {
                'disk_total_gb': disk.total / (1024 ** 3),
                'disk_free_gb': disk.free / (1024 ** 3),
                'disk_used_percent': disk.percent
            }
        except Exception as e:
            logger.warning(f"Error detecting storage: {e}")
            return {
                'disk_total_gb': 0.0,
                'disk_free_gb': 0.0,
                'disk_used_percent': 0.0
            }

    def _detect_gpu(self) -> GPUInfo:
        """
        Detect GPU information (NVIDIA, AMD, Intel)

        Returns:
            GPUInfo object
        """
        # Try NVIDIA CUDA first
        nvidia_gpu = self._detect_nvidia_gpu()
        if nvidia_gpu.available:
            return nvidia_gpu

        # Try AMD ROCm (future)
        # amd_gpu = self._detect_amd_gpu()
        # if amd_gpu.available:
        #     return amd_gpu

        # Try Intel (future)
        # intel_gpu = self._detect_intel_gpu()
        # if intel_gpu.available:
        #     return intel_gpu

        # No GPU detected
        return GPUInfo(
            available=False,
            name="No GPU detected",
            memory_total_mb=0,
            memory_free_mb=0,
            cuda_version=None,
            compute_capability=None
        )

    def _detect_nvidia_gpu(self) -> GPUInfo:
        """Detect NVIDIA GPU via CUDA"""
        try:
            # Try importing torch first (most reliable)
            import torch

            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                if device_count > 0:
                    # Get first GPU info
                    device = torch.cuda.get_device_properties(0)

                    # Get memory info
                    mem_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 2)
                    mem_free = (torch.cuda.get_device_properties(0).total_memory -
                               torch.cuda.memory_allocated(0)) / (1024 ** 2)

                    return GPUInfo(
                        available=True,
                        name=device.name,
                        memory_total_mb=int(mem_total),
                        memory_free_mb=int(mem_free),
                        cuda_version=torch.version.cuda,
                        compute_capability=f"{device.major}.{device.minor}"
                    )
        except ImportError:
            logger.debug("PyTorch not installed, trying alternative GPU detection")
        except Exception as e:
            logger.debug(f"PyTorch GPU detection failed: {e}")

        # Fallback: Try nvidia-smi command
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if lines:
                    # Parse first GPU
                    parts = lines[0].split(',')
                    if len(parts) >= 3:
                        return GPUInfo(
                            available=True,
                            name=parts[0].strip(),
                            memory_total_mb=int(float(parts[1].strip())),
                            memory_free_mb=int(float(parts[2].strip())),
                            cuda_version="Unknown",
                            compute_capability="Unknown"
                        )
        except FileNotFoundError:
            logger.debug("nvidia-smi not found")
        except Exception as e:
            logger.debug(f"nvidia-smi detection failed: {e}")

        # No NVIDIA GPU found
        return GPUInfo(
            available=False,
            name="No NVIDIA GPU detected",
            memory_total_mb=0,
            memory_free_mb=0,
            cuda_version=None,
            compute_capability=None
        )

    def _detect_system(self) -> Dict:
        """Detect system information"""
        try:
            return {
                'platform': platform.system(),
                'os_version': platform.version(),
                'python_version': platform.python_version()
            }
        except Exception as e:
            logger.warning(f"Error detecting system info: {e}")
            return {
                'platform': "Unknown",
                'os_version': "Unknown",
                'python_version': "Unknown"
            }

    def get_hardware_info(self) -> HardwareInfo:
        """Get current hardware information"""
        if self.hardware_info is None:
            self.detect_hardware()
        return self.hardware_info

    def get_hardware_dict(self) -> Dict:
        """Get hardware information as dictionary"""
        if self.hardware_info is None:
            self.detect_hardware()

        info_dict = asdict(self.hardware_info)
        return info_dict

    def can_run_feature(self, feature_requirements: Dict) -> tuple[bool, List[str]]:
        """
        Check if hardware can run a feature

        Args:
            feature_requirements: Dict with requirements like:
                {
                    'min_ram_gb': 8,
                    'min_cpu_cores': 4,
                    'gpu_required': False,
                    'min_gpu_memory_mb': 4096,
                    'min_disk_free_gb': 10
                }

        Returns:
            (can_run: bool, warnings: List[str])
        """
        if self.hardware_info is None:
            self.detect_hardware()

        warnings = []
        can_run = True

        # Check RAM
        if 'min_ram_gb' in feature_requirements:
            required_ram = feature_requirements['min_ram_gb']
            if self.hardware_info.ram_total_gb < required_ram:
                warnings.append(
                    f"Insufficient RAM: {self.hardware_info.ram_total_gb:.1f}GB available, "
                    f"{required_ram}GB required"
                )
                can_run = False

        # Check CPU cores
        if 'min_cpu_cores' in feature_requirements:
            required_cores = feature_requirements['min_cpu_cores']
            if self.hardware_info.cpu_cores < required_cores:
                warnings.append(
                    f"Insufficient CPU cores: {self.hardware_info.cpu_cores} available, "
                    f"{required_cores} required"
                )
                can_run = False

        # Check GPU
        if feature_requirements.get('gpu_required', False):
            if not self.hardware_info.gpu.available:
                warnings.append("GPU required but not detected")
                can_run = False
            elif 'min_gpu_memory_mb' in feature_requirements:
                required_gpu_mem = feature_requirements['min_gpu_memory_mb']
                if self.hardware_info.gpu.memory_total_mb < required_gpu_mem:
                    warnings.append(
                        f"Insufficient GPU memory: {self.hardware_info.gpu.memory_total_mb}MB available, "
                        f"{required_gpu_mem}MB required"
                    )
                    can_run = False

        # Check disk space
        if 'min_disk_free_gb' in feature_requirements:
            required_disk = feature_requirements['min_disk_free_gb']
            if self.hardware_info.disk_free_gb < required_disk:
                warnings.append(
                    f"Insufficient disk space: {self.hardware_info.disk_free_gb:.1f}GB free, "
                    f"{required_disk}GB required"
                )
                can_run = False

        return can_run, warnings

    def get_recommended_config(self) -> Dict:
        """
        Get recommended configuration based on available hardware

        Returns:
            Dict with recommended settings for various features
        """
        if self.hardware_info is None:
            self.detect_hardware()

        recommendations = {
            'hardware_tier': self._get_hardware_tier(),
            'max_cameras': self._recommend_max_cameras(),
            'processing_resolution': self._recommend_processing_resolution(),
            'face_detection_method': self._recommend_face_detection_method(),
            'enable_face_recognition': self._recommend_face_recognition(),
            'enable_object_detection': self._recommend_object_detection(),
            'enable_license_plate_recognition': self._recommend_lpr(),
            'frame_skip_idle': self._recommend_frame_skip(),
            'recording_quality': self._recommend_recording_quality(),
            'max_recording_duration': self._recommend_recording_duration(),
        }

        return recommendations

    def _get_hardware_tier(self) -> str:
        """Classify hardware tier"""
        gpu_available = self.hardware_info.gpu.available
        cpu_cores = self.hardware_info.cpu_cores
        ram_gb = self.hardware_info.ram_total_gb

        if gpu_available and cpu_cores >= 8 and ram_gb >= 32:
            return "high_end"
        elif (gpu_available and cpu_cores >= 4 and ram_gb >= 16) or \
             (cpu_cores >= 8 and ram_gb >= 16):
            return "medium"
        elif cpu_cores >= 2 and ram_gb >= 8:
            return "low"
        else:
            return "minimal"

    def _recommend_max_cameras(self) -> int:
        """Recommend maximum number of cameras"""
        tier = self._get_hardware_tier()

        if tier == "high_end":
            return 20
        elif tier == "medium":
            return 10
        elif tier == "low":
            return 4
        else:
            return 2

    def _recommend_processing_resolution(self) -> str:
        """Recommend processing resolution"""
        tier = self._get_hardware_tier()

        if tier == "high_end":
            return "1920x1080"  # Full HD
        elif tier == "medium":
            return "1280x720"   # 720p
        else:
            return "854x480"    # 480p

    def _recommend_face_detection_method(self) -> str:
        """Recommend face detection method (hog or cnn)"""
        if self.hardware_info.gpu.available and self.hardware_info.gpu.memory_total_mb >= 4096:
            return "cnn"  # GPU-accelerated
        else:
            return "hog"  # CPU-friendly

    def _recommend_face_recognition(self) -> bool:
        """Recommend enabling face recognition"""
        tier = self._get_hardware_tier()
        return tier in ["high_end", "medium", "low"]

    def _recommend_object_detection(self) -> bool:
        """Recommend enabling object detection"""
        # Only recommend if GPU available with sufficient memory
        return (self.hardware_info.gpu.available and
                self.hardware_info.gpu.memory_total_mb >= 6144)

    def _recommend_lpr(self) -> bool:
        """Recommend enabling license plate recognition"""
        tier = self._get_hardware_tier()
        return tier in ["high_end", "medium"]

    def _recommend_frame_skip(self) -> int:
        """Recommend frame skip factor when idle"""
        tier = self._get_hardware_tier()

        if tier == "high_end":
            return 2  # Process every 2nd frame
        elif tier == "medium":
            return 3  # Every 3rd frame
        elif tier == "low":
            return 5  # Every 5th frame
        else:
            return 10  # Every 10th frame

    def _recommend_recording_quality(self) -> str:
        """Recommend recording quality preset"""
        tier = self._get_hardware_tier()

        if tier == "high_end":
            return "high"
        elif tier == "medium":
            return "medium"
        else:
            return "low"

    def _recommend_recording_duration(self) -> int:
        """Recommend max recording duration (seconds)"""
        disk_free = self.hardware_info.disk_free_gb

        if disk_free >= 500:
            return 600  # 10 minutes
        elif disk_free >= 100:
            return 300  # 5 minutes
        else:
            return 120  # 2 minutes


# Global hardware detector instance
_hardware_detector: Optional[HardwareDetector] = None


def get_hardware_detector() -> HardwareDetector:
    """Get or create global hardware detector instance"""
    global _hardware_detector

    if _hardware_detector is None:
        _hardware_detector = HardwareDetector()

    return _hardware_detector


def refresh_hardware_detection():
    """Force refresh hardware detection"""
    global _hardware_detector
    _hardware_detector = HardwareDetector()
    return _hardware_detector
