# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Hardware-Aware Feature Management System

Automatically enables/disables features based on detected hardware capabilities.
- Scans hardware on startup
- Configures features based on compatibility
- Tracks hardware changes over time
- Allows user overrides with warnings
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from backend.core.hardware_detector import get_hardware_detector
from backend.core.feature_config import (
    get_all_features,
    get_feature_config,
    get_optimal_config_for_hardware
)
from backend.database.models import FeatureState, HardwareScanHistory
from backend.database.session import SessionLocal

logger = logging.getLogger(__name__)


class FeatureManager:
    """
    Manages feature states based on hardware capabilities
    """

    def __init__(self):
        self.hardware_detector = get_hardware_detector()
        self.features = get_all_features()

    def scan_and_configure_features(
        self,
        scan_type: str = "startup",
        scanned_by: str = "system",
        notify_changes: bool = True
    ) -> Dict:
        """
        Scan hardware and auto-configure features

        Args:
            scan_type: Type of scan (startup, manual, scheduled, triggered)
            scanned_by: Username or "system"
            notify_changes: Whether to notify about changes

        Returns:
            Dictionary with scan results and actions taken
        """
        logger.info(f"Starting hardware scan ({scan_type})...")

        db = SessionLocal()
        try:
            # Get current hardware information
            hw_info = self.hardware_detector.get_hardware_info()
            hw_dict = self.hardware_detector.get_hardware_dict()

            # Get last scan for comparison
            last_scan = db.query(HardwareScanHistory).order_by(
                HardwareScanHistory.scanned_at.desc()
            ).first()

            # Detect changes
            changes_detected, changes_summary = self._detect_hardware_changes(
                last_scan, hw_dict
            )

            # Get optimal configuration for current hardware
            optimal_config = get_optimal_config_for_hardware(hw_dict)

            # Configure features based on hardware
            enabled_count, disabled_count, feature_changes = self._configure_features(
                db, optimal_config, hw_dict
            )

            # Create scan history record
            scan_record = HardwareScanHistory(
                scan_type=scan_type,
                cpu_cores=hw_info.cpu_cores,
                ram_total_gb=hw_info.ram_total_gb,
                gpu_available=hw_info.gpu.available,
                gpu_name=hw_info.gpu.name if hw_info.gpu.available else None,
                gpu_memory_mb=hw_info.gpu.memory_total_mb if hw_info.gpu.available else None,
                hardware_tier=optimal_config['tier'],
                changes_detected=changes_detected,
                changes_summary=json.dumps(changes_summary) if changes_summary else None,
                features_enabled=enabled_count,
                features_disabled=disabled_count,
                scanned_by=scanned_by
            )
            db.add(scan_record)
            db.commit()
            db.refresh(scan_record)

            result = {
                "scan_id": scan_record.id,
                "scan_type": scan_type,
                "hardware_tier": optimal_config['tier'],
                "changes_detected": changes_detected,
                "changes_summary": changes_summary,
                "features_enabled": enabled_count,
                "features_disabled": disabled_count,
                "feature_changes": feature_changes,
                "hardware_summary": {
                    "cpu_cores": hw_info.cpu_cores,
                    "ram_gb": hw_info.ram_total_gb,
                    "gpu_available": hw_info.gpu.available,
                    "gpu_name": hw_info.gpu.name if hw_info.gpu.available else "None"
                }
            }

            if notify_changes and changes_detected:
                logger.warning(f"Hardware changes detected: {changes_summary}")

            logger.info(
                f"Hardware scan complete: {enabled_count} features enabled, "
                f"{disabled_count} disabled (tier: {optimal_config['tier']})"
            )

            return result

        except Exception as e:
            logger.error(f"Error during hardware scan: {e}", exc_info=True)
            db.rollback()
            raise
        finally:
            db.close()

    def _detect_hardware_changes(
        self,
        last_scan: Optional[HardwareScanHistory],
        current_hw: Dict
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Compare current hardware with last scan to detect changes

        Returns:
            (changes_detected: bool, changes_summary: dict or None)
        """
        if not last_scan:
            return False, None

        changes = {}

        # Check CPU cores
        if current_hw.get('cpu', {}).get('cores') != last_scan.cpu_cores:
            changes['cpu_cores'] = {
                'old': last_scan.cpu_cores,
                'new': current_hw.get('cpu', {}).get('cores')
            }

        # Check RAM
        current_ram = current_hw.get('ram', {}).get('total_gb', 0)
        if abs(current_ram - last_scan.ram_total_gb) > 0.5:  # Tolerance for rounding
            changes['ram_gb'] = {
                'old': last_scan.ram_total_gb,
                'new': current_ram
            }

        # Check GPU availability
        current_gpu = current_hw.get('gpu', {}).get('available', False)
        if current_gpu != last_scan.gpu_available:
            changes['gpu_available'] = {
                'old': last_scan.gpu_available,
                'new': current_gpu
            }

        # Check GPU model (if available)
        if current_gpu and last_scan.gpu_available:
            current_gpu_name = current_hw.get('gpu', {}).get('name', '')
            if current_gpu_name != last_scan.gpu_name:
                changes['gpu_model'] = {
                    'old': last_scan.gpu_name,
                    'new': current_gpu_name
                }

        return len(changes) > 0, changes if changes else None

    def _configure_features(
        self,
        db: Session,
        optimal_config: Dict,
        hw_dict: Dict
    ) -> Tuple[int, int, List[Dict]]:
        """
        Configure features based on hardware compatibility

        Returns:
            (enabled_count, disabled_count, feature_changes)
        """
        enabled_count = 0
        disabled_count = 0
        feature_changes = []

        for feature_id, feature_info in optimal_config['features'].items():
            feature = get_feature_config(feature_id)
            if not feature:
                continue

            # Check if feature state already exists
            feature_state = db.query(FeatureState).filter(
                FeatureState.feature_id == feature_id
            ).first()

            # Determine if feature should be enabled
            is_compatible = feature_info.get('recommended', False)
            warnings = feature_info.get('warnings', [])

            # Build compatibility reason
            compatibility_reason = None
            if not is_compatible and warnings:
                compatibility_reason = "; ".join(warnings)
            elif not is_compatible:
                # Check specific requirements
                if feature.requirements.gpu_required and not hw_dict.get('gpu', {}).get('available'):
                    compatibility_reason = "Requires GPU (not detected)"
                elif feature.requirements.min_ram_gb > hw_dict.get('ram', {}).get('total_gb', 0):
                    compatibility_reason = f"Requires {feature.requirements.min_ram_gb}GB RAM (have {hw_dict.get('ram', {}).get('total_gb', 0):.1f}GB)"
                elif feature.requirements.min_cpu_cores > hw_dict.get('cpu', {}).get('cores', 0):
                    compatibility_reason = f"Requires {feature.requirements.min_cpu_cores} CPU cores (have {hw_dict.get('cpu', {}).get('cores', 0)})"
                else:
                    compatibility_reason = "Hardware does not meet recommended specifications"

            if feature_state:
                # Feature exists - update only if auto-configured (no user override)
                if not feature_state.user_override:
                    old_enabled = feature_state.enabled
                    feature_state.enabled = is_compatible and feature.default_enabled
                    feature_state.hardware_compatible = is_compatible
                    feature_state.compatibility_reason = compatibility_reason
                    feature_state.last_checked_at = datetime.utcnow()
                    feature_state.updated_at = datetime.utcnow()

                    if old_enabled != feature_state.enabled:
                        if feature_state.enabled:
                            enabled_count += 1
                        else:
                            disabled_count += 1

                        feature_changes.append({
                            'feature_id': feature_id,
                            'feature_name': feature.name,
                            'action': 'enabled' if feature_state.enabled else 'disabled',
                            'reason': compatibility_reason or "Hardware compatible"
                        })
                else:
                    # User override exists - just update compatibility info
                    feature_state.hardware_compatible = is_compatible
                    feature_state.compatibility_reason = compatibility_reason
                    feature_state.last_checked_at = datetime.utcnow()
            else:
                # New feature - create with auto-configuration
                # Default enabled features: only enable if hardware compatible
                # Default disabled features: keep disabled unless hardware is high-end
                should_enable = is_compatible and feature.default_enabled

                feature_state = FeatureState(
                    feature_id=feature_id,
                    enabled=should_enable,
                    auto_configured=True,
                    user_override=False,
                    hardware_compatible=is_compatible,
                    compatibility_reason=compatibility_reason
                )
                db.add(feature_state)

                if should_enable:
                    enabled_count += 1
                    feature_changes.append({
                        'feature_id': feature_id,
                        'feature_name': feature.name,
                        'action': 'enabled',
                        'reason': "Hardware compatible, enabled by default"
                    })

        db.commit()
        return enabled_count, disabled_count, feature_changes

    def get_feature_states(self, db: Session) -> List[Dict]:
        """
        Get all feature states with detailed information

        Returns:
            List of feature state dictionaries
        """
        states = db.query(FeatureState).all()
        result = []

        for state in states:
            feature = get_feature_config(state.feature_id)
            if not feature:
                continue

            result.append({
                'feature_id': state.feature_id,
                'feature_name': feature.name,
                'description': feature.description,
                'category': feature.category.value,
                'enabled': state.enabled,
                'hardware_compatible': state.hardware_compatible,
                'compatibility_reason': state.compatibility_reason,
                'user_override': state.user_override,
                'auto_configured': state.auto_configured,
                'requirements': {
                    'gpu_required': feature.requirements.gpu_required,
                    'gpu_recommended': feature.requirements.gpu_recommended,
                    'min_ram_gb': feature.requirements.min_ram_gb,
                    'min_cpu_cores': feature.requirements.min_cpu_cores
                },
                'has_cpu_fallback': feature.has_cpu_fallback,
                'last_checked_at': state.last_checked_at.isoformat() if state.last_checked_at else None
            })

        return result

    def toggle_feature(
        self,
        db: Session,
        feature_id: str,
        enabled: bool,
        user_override: bool = True
    ) -> Dict:
        """
        Toggle a feature on/off

        Args:
            db: Database session
            feature_id: Feature identifier
            enabled: New enabled state
            user_override: Mark as user override (default True)

        Returns:
            Dictionary with result and any warnings
        """
        feature = get_feature_config(feature_id)
        if not feature:
            raise ValueError(f"Feature not found: {feature_id}")

        feature_state = db.query(FeatureState).filter(
            FeatureState.feature_id == feature_id
        ).first()

        if not feature_state:
            # Create new feature state
            feature_state = FeatureState(
                feature_id=feature_id,
                enabled=enabled,
                user_override=user_override,
                auto_configured=not user_override
            )
            db.add(feature_state)
        else:
            feature_state.enabled = enabled
            feature_state.user_override = user_override
            feature_state.updated_at = datetime.utcnow()

        db.commit()

        warnings = []
        if enabled and not feature_state.hardware_compatible:
            warnings.append(
                f"Warning: {feature.name} may not work properly. "
                f"Reason: {feature_state.compatibility_reason}"
            )

        return {
            'feature_id': feature_id,
            'feature_name': feature.name,
            'enabled': enabled,
            'user_override': user_override,
            'warnings': warnings
        }

    def get_scan_history(self, db: Session, limit: int = 10) -> List[Dict]:
        """
        Get hardware scan history

        Args:
            db: Database session
            limit: Maximum number of records to return

        Returns:
            List of scan history dictionaries
        """
        scans = db.query(HardwareScanHistory).order_by(
            HardwareScanHistory.scanned_at.desc()
        ).limit(limit).all()

        result = []
        for scan in scans:
            result.append({
                'id': scan.id,
                'scan_type': scan.scan_type,
                'hardware_tier': scan.hardware_tier,
                'cpu_cores': scan.cpu_cores,
                'ram_gb': scan.ram_total_gb,
                'gpu_available': scan.gpu_available,
                'gpu_name': scan.gpu_name,
                'changes_detected': scan.changes_detected,
                'changes_summary': json.loads(scan.changes_summary) if scan.changes_summary else None,
                'features_enabled': scan.features_enabled,
                'features_disabled': scan.features_disabled,
                'scanned_at': scan.scanned_at.isoformat(),
                'scanned_by': scan.scanned_by
            })

        return result


# Global instance
_feature_manager: Optional[FeatureManager] = None


def get_feature_manager() -> FeatureManager:
    """Get or create global feature manager instance"""
    global _feature_manager
    if _feature_manager is None:
        _feature_manager = FeatureManager()
    return _feature_manager
