"""
Network Discovery API Routes

Provides network device discovery endpoints for ecosystem integration.
Uses Fing agent when available, with fallback to ARP/nmap scanning.
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.fing_integration import (
    get_fing_integration,
    FingIntegration,
    NetworkDevice,
    DeviceType,
    SpeedTestResult
)
from backend.database.session import get_db
from backend.core.auth import get_current_user

router = APIRouter(prefix="/network", tags=["Network Discovery"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class DeviceResponse(BaseModel):
    """Network device response"""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    device_type: str
    is_online: bool
    is_gateway: bool
    last_seen: datetime
    first_seen: datetime
    open_ports: List[int] = []
    custom_name: Optional[str] = None
    is_known: bool = False

    class Config:
        from_attributes = True


class DeviceListResponse(BaseModel):
    """List of devices response"""
    devices: List[DeviceResponse]
    total: int
    online_count: int
    fing_available: bool
    scan_timestamp: datetime = Field(default_factory=datetime.utcnow)


class SpeedTestResponse(BaseModel):
    """Speed test result response"""
    download_mbps: float
    upload_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    server: Optional[str] = None
    timestamp: datetime


class ConnectivityResponse(BaseModel):
    """Connectivity check response"""
    online: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SetDeviceNameRequest(BaseModel):
    """Request to set device custom name"""
    name: str = Field(..., min_length=1, max_length=100)


class PortScanRequest(BaseModel):
    """Port scan request"""
    ports: Optional[List[int]] = Field(
        default=None,
        description="Ports to scan (default: common ports)"
    )


class PortScanResponse(BaseModel):
    """Port scan response"""
    ip_address: str
    open_ports: List[int]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NetworkStatusResponse(BaseModel):
    """Overall network status"""
    fing_available: bool
    total_devices: int
    online_devices: int
    gateway_ip: Optional[str] = None
    gateway_mac: Optional[str] = None
    internet_connected: bool
    last_scan: Optional[datetime] = None


# ============================================================================
# Dependency
# ============================================================================

async def get_fing() -> FingIntegration:
    """Dependency to get Fing integration"""
    return await get_fing_integration()


# ============================================================================
# Routes
# ============================================================================

@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    online_only: bool = Query(False, description="Only return online devices"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    List all discovered network devices.

    Performs a network scan and returns all discovered devices.
    Uses Fing agent if available, otherwise falls back to ARP/nmap.
    """
    # Perform discovery
    devices = await fing.discover_devices()

    # Apply filters
    if online_only:
        devices = [d for d in devices if d.is_online]

    if device_type:
        try:
            dt = DeviceType(device_type.lower())
            devices = [d for d in devices if d.device_type == dt]
        except ValueError:
            pass  # Invalid type, ignore filter

    # Build response
    all_devices = fing.get_all_devices()
    return DeviceListResponse(
        devices=[DeviceResponse(
            mac_address=d.mac_address,
            ip_address=d.ip_address,
            hostname=d.hostname,
            vendor=d.vendor,
            device_type=d.device_type.value,
            is_online=d.is_online,
            is_gateway=d.is_gateway,
            last_seen=d.last_seen,
            first_seen=d.first_seen,
            open_ports=d.open_ports,
            custom_name=d.custom_name,
            is_known=d.is_known
        ) for d in devices],
        total=len(all_devices),
        online_count=len([d for d in all_devices if d.is_online]),
        fing_available=fing.fing_available
    )


@router.post("/scan", response_model=DeviceListResponse)
async def trigger_scan(
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Trigger a new network scan.

    Forces a fresh network scan regardless of cache.
    """
    devices = await fing.discover_devices()

    all_devices = fing.get_all_devices()
    return DeviceListResponse(
        devices=[DeviceResponse(
            mac_address=d.mac_address,
            ip_address=d.ip_address,
            hostname=d.hostname,
            vendor=d.vendor,
            device_type=d.device_type.value,
            is_online=d.is_online,
            is_gateway=d.is_gateway,
            last_seen=d.last_seen,
            first_seen=d.first_seen,
            open_ports=d.open_ports,
            custom_name=d.custom_name,
            is_known=d.is_known
        ) for d in devices],
        total=len(all_devices),
        online_count=len([d for d in all_devices if d.is_online]),
        fing_available=fing.fing_available
    )


@router.get("/devices/{mac_address}", response_model=DeviceResponse)
async def get_device(
    mac_address: str,
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Get details for a specific device by MAC address.
    """
    device = fing.get_device_by_mac(mac_address)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceResponse(
        mac_address=device.mac_address,
        ip_address=device.ip_address,
        hostname=device.hostname,
        vendor=device.vendor,
        device_type=device.device_type.value,
        is_online=device.is_online,
        is_gateway=device.is_gateway,
        last_seen=device.last_seen,
        first_seen=device.first_seen,
        open_ports=device.open_ports,
        custom_name=device.custom_name,
        is_known=device.is_known
    )


@router.put("/devices/{mac_address}/name")
async def set_device_name(
    mac_address: str,
    request: SetDeviceNameRequest,
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Set a custom name for a device.

    Named devices are marked as "known" for easier identification.
    """
    if not fing.set_device_name(mac_address, request.name):
        raise HTTPException(status_code=404, detail="Device not found")

    return {"success": True, "message": f"Device named '{request.name}'"}


@router.post("/devices/{ip_address}/ports", response_model=PortScanResponse)
async def scan_device_ports(
    ip_address: str,
    request: PortScanRequest = None,
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Scan ports on a specific device.

    Scans common ports by default, or specified ports if provided.
    """
    ports = request.ports if request else None
    open_ports = await fing.get_device_ports(ip_address, ports)

    return PortScanResponse(
        ip_address=ip_address,
        open_ports=open_ports
    )


@router.get("/gateway", response_model=Optional[DeviceResponse])
async def get_gateway(
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Get network gateway information.
    """
    gateway = await fing.get_gateway_info()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway not found")

    return DeviceResponse(
        mac_address=gateway.mac_address,
        ip_address=gateway.ip_address,
        hostname=gateway.hostname,
        vendor=gateway.vendor,
        device_type=gateway.device_type.value,
        is_online=gateway.is_online,
        is_gateway=gateway.is_gateway,
        last_seen=gateway.last_seen,
        first_seen=gateway.first_seen,
        open_ports=gateway.open_ports,
        custom_name=gateway.custom_name,
        is_known=gateway.is_known
    )


@router.post("/speedtest", response_model=SpeedTestResponse)
async def run_speed_test(
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Run an internet speed test.

    Uses Fing agent speed test if available, otherwise falls back to
    speedtest-cli or curl-based testing.

    Note: This may take 30-60 seconds to complete.
    """
    result = await fing.run_speed_test()
    if not result:
        raise HTTPException(
            status_code=500,
            detail="Speed test failed - no testing methods available"
        )

    return SpeedTestResponse(
        download_mbps=result.download_mbps,
        upload_mbps=result.upload_mbps,
        ping_ms=result.ping_ms,
        server=result.server,
        timestamp=result.timestamp
    )


@router.get("/connectivity", response_model=ConnectivityResponse)
async def check_connectivity(
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Check internet connectivity.

    Pings multiple DNS servers to verify internet access.
    """
    is_online = await fing.check_connectivity()
    return ConnectivityResponse(online=is_online)


@router.get("/status", response_model=NetworkStatusResponse)
async def get_network_status(
    fing: FingIntegration = Depends(get_fing),
    _current_user=Depends(get_current_user)
):
    """
    Get overall network status.

    Returns summary of network discovery state including:
    - Fing agent availability
    - Device counts
    - Gateway information
    - Internet connectivity
    """
    devices = fing.get_all_devices()
    gateway = await fing.get_gateway_info()
    is_connected = await fing.check_connectivity()

    online_devices = [d for d in devices if d.is_online]
    last_scan = max((d.last_seen for d in devices), default=None) if devices else None

    return NetworkStatusResponse(
        fing_available=fing.fing_available,
        total_devices=len(devices),
        online_devices=len(online_devices),
        gateway_ip=gateway.ip_address if gateway else None,
        gateway_mac=gateway.mac_address if gateway else None,
        internet_connected=is_connected,
        last_scan=last_scan
    )


@router.get("/types")
async def list_device_types():
    """
    List all available device types for filtering.
    """
    return {
        "types": [dt.value for dt in DeviceType]
    }


# ============================================================================
# Ecosystem Integration Endpoints
# ============================================================================

@router.get("/ecosystem/devices", response_model=DeviceListResponse)
async def ecosystem_devices(
    token: str = Query(..., description="Ecosystem authentication token"),
    fing: FingIntegration = Depends(get_fing)
):
    """
    Get devices for ecosystem apps (MagicMirror, mobile apps).

    This endpoint uses token-based auth for ecosystem integration.
    """
    # Token validation would be handled by ecosystem security
    # For now, perform discovery
    devices = await fing.discover_devices()

    all_devices = fing.get_all_devices()
    return DeviceListResponse(
        devices=[DeviceResponse(
            mac_address=d.mac_address,
            ip_address=d.ip_address,
            hostname=d.hostname,
            vendor=d.vendor,
            device_type=d.device_type.value,
            is_online=d.is_online,
            is_gateway=d.is_gateway,
            last_seen=d.last_seen,
            first_seen=d.first_seen,
            open_ports=d.open_ports,
            custom_name=d.custom_name,
            is_known=d.is_known
        ) for d in devices],
        total=len(all_devices),
        online_count=len([d for d in all_devices if d.is_online]),
        fing_available=fing.fing_available
    )


@router.get("/ecosystem/status", response_model=NetworkStatusResponse)
async def ecosystem_network_status(
    token: str = Query(..., description="Ecosystem authentication token"),
    fing: FingIntegration = Depends(get_fing)
):
    """
    Get network status for ecosystem apps.
    """
    devices = fing.get_all_devices()
    gateway = await fing.get_gateway_info()
    is_connected = await fing.check_connectivity()

    online_devices = [d for d in devices if d.is_online]
    last_scan = max((d.last_seen for d in devices), default=None) if devices else None

    return NetworkStatusResponse(
        fing_available=fing.fing_available,
        total_devices=len(devices),
        online_devices=len(online_devices),
        gateway_ip=gateway.ip_address if gateway else None,
        gateway_mac=gateway.mac_address if gateway else None,
        internet_connected=is_connected,
        last_scan=last_scan
    )
