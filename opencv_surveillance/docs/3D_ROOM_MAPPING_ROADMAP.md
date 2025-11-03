# 3D/2D Room Mapping - Implementation Roadmap

## Executive Summary

**Status**: Not currently implemented
**Complexity**: High (Advanced Computer Vision Feature)
**Estimated Development Time**: 8-12 weeks (1 developer)
**Hardware Requirements**: Medium to High (depends on approach)

This document outlines the requirements, approaches, and implementation plan for adding 3D/2D spatial mapping capabilities to OpenEye.

---

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Technical Approaches](#technical-approaches)
3. [Hardware Requirements](#hardware-requirements)
4. [Implementation Phases](#implementation-phases)
5. [Software Architecture](#software-architecture)
6. [Export Formats](#export-formats)
7. [Cost Analysis](#cost-analysis)
8. [Recommendations](#recommendations)

---

## Feature Overview

### Goal
Enable OpenEye to generate 3D room models from camera feeds that can be:
- Visualized in the web interface (2D floor plans & 3D models)
- Exported to professional 3D software (SketchUp, AutoCAD, Blender, etc.)
- Used for spatial analytics and planning

### Use Cases
1. **Security Planning**: Visualize camera coverage areas
2. **Space Planning**: Measure room dimensions for renovations
3. **Documentation**: Create as-built drawings of spaces
4. **Virtual Tours**: Navigate captured 3D environments
5. **AI Training**: Provide spatial context for object detection

---

## Technical Approaches

### Approach 1: Monocular Depth Estimation + Structure from Motion (SfM)
**Difficulty**: Medium
**Accuracy**: Medium (±5-10% error)
**Hardware**: Existing cameras (no additional hardware)

#### How It Works
1. **Depth Estimation**: Use AI models to estimate depth from single images
2. **Structure from Motion**: Reconstruct 3D points from multiple camera views
3. **Point Cloud Generation**: Combine depth maps into 3D point cloud
4. **Mesh Reconstruction**: Convert point cloud to surface mesh

#### Pros
- Works with existing surveillance cameras
- No additional hardware costs
- Scales to any number of cameras

#### Cons
- Less accurate than depth sensors
- Requires camera movement or multiple cameras
- Computationally intensive
- Struggles with textureless surfaces

#### Technology Stack
- **Depth Estimation**: MiDaS, DPT, or ZoeDepth (deep learning models)
- **SfM**: COLMAP or OpenCV's SfM module
- **Point Cloud**: Open3D
- **Mesh Reconstruction**: Poisson Surface Reconstruction

---

### Approach 2: Stereo Vision
**Difficulty**: Medium-High
**Accuracy**: High (±2-5% error)
**Hardware**: Stereo camera pairs

#### How It Works
1. **Stereo Calibration**: Calibrate camera pair for accurate disparity
2. **Disparity Computation**: Calculate pixel differences between left/right images
3. **Depth Map Generation**: Convert disparity to real-world depth
4. **3D Reconstruction**: Build point cloud from depth maps

#### Pros
- More accurate than monocular methods
- Real-time capable
- Well-established algorithms

#### Cons
- Requires stereo camera pairs (new hardware)
- Limited to areas visible by both cameras
- Sensitive to calibration errors

#### Technology Stack
- **Stereo Vision**: OpenCV stereo algorithms (SGBM, BM)
- **Calibration**: OpenCV camera calibration
- **Point Cloud**: Open3D or PCL

---

### Approach 3: Depth Sensors (RGB-D)
**Difficulty**: Low-Medium
**Accuracy**: Very High (±1-2% error)
**Hardware**: Depth cameras (Intel RealSense, Azure Kinect, etc.)

#### How It Works
1. **Direct Depth Capture**: Camera provides RGB + Depth streams
2. **Point Cloud Generation**: Convert depth images to 3D points
3. **SLAM**: Simultaneous Localization and Mapping for room-scale reconstruction
4. **Mesh Export**: Generate textured 3D models

#### Pros
- Highest accuracy
- Real-time performance
- Simplified implementation
- Works in low light

#### Cons
- Requires new hardware ($100-$400 per camera)
- Limited range (0.5m - 10m typically)
- Not suitable for outdoor use
- Higher power consumption

#### Technology Stack
- **SDK**: Intel RealSense SDK 2.0 / Azure Kinect SDK
- **SLAM**: ORB-SLAM3, RTAB-Map, or Open3D SLAM
- **Point Cloud**: Open3D, PCL
- **Mesh**: Open3D Reconstruction

---

### Approach 4: LiDAR (Professional Grade)
**Difficulty**: Medium
**Accuracy**: Extremely High (±1mm error)
**Hardware**: LiDAR sensors

#### How It Works
1. **Laser Scanning**: LiDAR emits laser pulses and measures return time
2. **Dense Point Cloud**: Generates millions of 3D points
3. **Registration**: Align multiple scans
4. **CAD Export**: Industry-standard formats

#### Pros
- Survey-grade accuracy
- Long range (100m+)
- Works in any lighting
- Professional outputs

#### Cons
- **Very expensive** ($1,000 - $20,000+ per sensor)
- Overkill for most use cases
- Complex calibration
- Large data files

#### Technology Stack
- **Hardware**: Velodyne, Ouster, Livox LiDAR
- **Processing**: CloudCompare, PCL
- **Export**: Direct to CAD formats

---

## Hardware Requirements

### Recommended Approach: Monocular Depth + Multi-Camera SfM

#### Minimum Hardware (Budget Option)
- **Existing Setup**: Use current surveillance cameras
- **CPU**: Intel i5/Ryzen 5 (8th gen or newer)
- **RAM**: 16GB DDR4
- **GPU**: NVIDIA GTX 1660 or better (6GB VRAM minimum)
- **Storage**: 256GB SSD for models and cache
- **Estimated Cost**: $0 (uses existing hardware)

#### Recommended Hardware (Better Performance)
- **CPU**: Intel i7/Ryzen 7 (10th gen or newer)
- **RAM**: 32GB DDR4
- **GPU**: NVIDIA RTX 3060 or better (12GB VRAM)
- **Storage**: 512GB NVMe SSD
- **Estimated Cost**: $800-$1,200 upgrade

#### High-End Hardware (Real-Time Processing)
- **CPU**: Intel i9/Ryzen 9 (12th gen or newer)
- **RAM**: 64GB DDR5
- **GPU**: NVIDIA RTX 4070 or better (12-16GB VRAM)
- **Storage**: 1TB NVMe SSD
- **Optional**: Depth cameras (Intel RealSense D435i - $300 each)
- **Estimated Cost**: $2,000-$3,000

---

### Alternative: Depth Camera Approach (Intel RealSense)

#### Hardware Requirements
- **Depth Cameras**: Intel RealSense D435i ($300 each) or D455 ($400 each)
- **CPU**: Intel i5 or better
- **RAM**: 16GB minimum
- **GPU**: Optional (helps with mesh processing)
- **Estimated Cost**: $300-$400 per camera + existing PC

#### Benefits
- Plug-and-play solution
- Lower computational requirements
- Real-time depth capture
- Easier implementation

---

## Implementation Phases

### Phase 1: Foundation (2-3 weeks)
**Goal**: Set up core infrastructure for 3D processing

#### Tasks
1. **Dependency Installation**
   - Install Open3D, PyTorch, OpenCV extras
   - Set up depth estimation models (MiDaS/DPT)
   - Configure GPU support

2. **Database Schema**
   ```sql
   CREATE TABLE spatial_maps (
     id SERIAL PRIMARY KEY,
     camera_id VARCHAR REFERENCES cameras(camera_id),
     map_type VARCHAR(20), -- '2d_floor_plan', '3d_model', 'point_cloud'
     file_path VARCHAR,
     metadata JSONB, -- dimensions, bounds, camera positions
     created_at TIMESTAMP,
     updated_at TIMESTAMP
   );

   CREATE TABLE reconstruction_sessions (
     id SERIAL PRIMARY KEY,
     name VARCHAR,
     camera_ids VARCHAR[], -- array of cameras used
     status VARCHAR(20), -- 'in_progress', 'completed', 'failed'
     progress FLOAT, -- 0.0 to 1.0
     point_count INTEGER,
     mesh_faces INTEGER,
     created_at TIMESTAMP
   );
   ```

3. **API Routes**
   - `/api/spatial/capture` - Trigger depth capture
   - `/api/spatial/reconstruct` - Start 3D reconstruction
   - `/api/spatial/maps` - List saved maps
   - `/api/spatial/export` - Export to 3D formats

#### Deliverables
- Database schema created
- API endpoints scaffolded
- Dependencies installed

---

### Phase 2: Depth Estimation (2-3 weeks)
**Goal**: Implement depth map generation from camera feeds

#### Tasks
1. **Model Integration**
   ```python
   # backend/core/depth_estimator.py
   import torch
   from transformers import DPTForDepthEstimation, DPTImageProcessor

   class DepthEstimator:
       def __init__(self):
           self.model = DPTForDepthEstimation.from_pretrained("Intel/dpt-large")
           self.processor = DPTImageProcessor.from_pretrained("Intel/dpt-large")
           self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
           self.model.to(self.device)

       def estimate_depth(self, image):
           inputs = self.processor(images=image, return_tensors="pt").to(self.device)
           with torch.no_grad():
               outputs = self.model(**inputs)
               depth = outputs.predicted_depth
           return depth.cpu().numpy()
   ```

2. **Real-Time Processing**
   - Integrate with camera streams
   - Add depth visualization overlay
   - Implement depth map caching

3. **Calibration Tools**
   - Camera intrinsic calibration UI
   - Scale calibration (using known distances)
   - Multi-camera alignment

#### Deliverables
- Depth maps generated from camera feeds
- Depth visualization in web UI
- Calibration system functional

---

### Phase 3: Point Cloud Generation (2 weeks)
**Goal**: Convert depth maps to 3D point clouds

#### Tasks
1. **Point Cloud Builder**
   ```python
   # backend/core/point_cloud_builder.py
   import open3d as o3d
   import numpy as np

   class PointCloudBuilder:
       def depth_to_pointcloud(self, depth_map, rgb_image, camera_intrinsics):
           # Convert depth map to 3D points
           height, width = depth_map.shape
           fx, fy, cx, cy = camera_intrinsics

           points = []
           colors = []

           for v in range(height):
               for u in range(width):
                   z = depth_map[v, u]
                   if z > 0:
                       x = (u - cx) * z / fx
                       y = (v - cy) * z / fy
                       points.append([x, y, z])
                       colors.append(rgb_image[v, u] / 255.0)

           pcd = o3d.geometry.PointCloud()
           pcd.points = o3d.utility.Vector3dVector(np.array(points))
           pcd.colors = o3d.utility.Vector3dVector(np.array(colors))

           return pcd

       def merge_pointclouds(self, pointclouds):
           # ICP registration for multi-view alignment
           merged = pointclouds[0]
           for pcd in pointclouds[1:]:
               # Rough alignment
               transformation = self.compute_transformation(merged, pcd)
               pcd.transform(transformation)
               merged += pcd

           # Downsample and remove outliers
           merged = merged.voxel_down_sample(voxel_size=0.05)
           merged, _ = merged.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

           return merged
   ```

2. **Multi-View Fusion**
   - Implement ICP (Iterative Closest Point) alignment
   - RANSAC for robust registration
   - Outlier removal and filtering

3. **Visualization**
   - 3D point cloud viewer in web UI (using Three.js)
   - Interactive navigation (orbit, pan, zoom)
   - Point cloud editing tools

#### Deliverables
- Point clouds generated from depth maps
- Multi-camera point clouds merged
- 3D viewer in web interface

---

### Phase 4: Mesh Reconstruction (1-2 weeks)
**Goal**: Convert point clouds to watertight 3D meshes

#### Tasks
1. **Surface Reconstruction**
   ```python
   # backend/core/mesh_reconstructor.py
   import open3d as o3d

   class MeshReconstructor:
       def reconstruct_mesh(self, pointcloud):
           # Estimate normals
           pointcloud.estimate_normals(
               search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30)
           )

           # Poisson surface reconstruction
           mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
               pointcloud, depth=9
           )

           # Remove low-density vertices
           vertices_to_remove = densities < np.quantile(densities, 0.01)
           mesh.remove_vertices_by_mask(vertices_to_remove)

           # Simplify mesh
           mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=100000)

           return mesh
   ```

2. **Mesh Optimization**
   - Quadric edge collapse decimation
   - Laplacian smoothing
   - Texture mapping from RGB images

3. **Floor Plan Extraction**
   - Slice mesh at height levels
   - Extract 2D contours
   - Generate architectural floor plans

#### Deliverables
- Watertight 3D meshes generated
- Mesh simplification and optimization
- 2D floor plan extraction

---

### Phase 5: Export & Integration (1-2 weeks)
**Goal**: Export to professional 3D formats

#### Tasks
1. **Export Formats**
   ```python
   # backend/core/model_exporter.py
   class ModelExporter:
       def export_obj(self, mesh, filepath):
           """Wavefront OBJ - Universal format"""
           o3d.io.write_triangle_mesh(filepath, mesh)

       def export_ply(self, mesh, filepath):
           """PLY - Point cloud format"""
           o3d.io.write_triangle_mesh(filepath, mesh, write_ascii=True)

       def export_stl(self, mesh, filepath):
           """STL - 3D printing format"""
           o3d.io.write_triangle_mesh(filepath, mesh)

       def export_dxf(self, floor_plan, filepath):
           """DXF - AutoCAD format (2D)"""
           # Use ezdxf library for DXF export
           import ezdxf
           doc = ezdxf.new('R2010')
           msp = doc.modelspace()

           for contour in floor_plan:
               msp.add_lwpolyline(contour, close=True)

           doc.saveas(filepath)

       def export_skp(self, mesh, filepath):
           """SketchUp format (via intermediate conversion)"""
           # Export as COLLADA (.dae) which SketchUp can import
           self.export_collada(mesh, filepath.replace('.skp', '.dae'))
   ```

2. **Supported Formats**
   - **OBJ** (Wavefront): Universal 3D format (SketchUp, Blender, 3ds Max)
   - **STL**: 3D printing, CAD software
   - **PLY**: Point cloud format
   - **DXF**: AutoCAD 2D drawings
   - **COLLADA (.dae)**: SketchUp import format
   - **glTF/GLB**: Web 3D, modern viewers
   - **FBX**: Autodesk ecosystem (AutoCAD, Revit)

3. **Frontend UI**
   - Export dialog with format selection
   - Preview before export
   - Download/email export files

#### Deliverables
- All export formats working
- One-click export to CAD software
- User documentation

---

### Phase 6: UI & Polish (1 week)
**Goal**: Professional user interface

#### Tasks
1. **Spatial Mapping Page**
   - List of saved maps
   - Reconstruction session management
   - Live preview of current reconstruction

2. **3D Viewer Enhancements**
   - Measurement tools (distance, area, volume)
   - Annotation tools
   - Camera path visualization
   - Coverage heatmap

3. **Documentation**
   - User guide for spatial mapping
   - Calibration tutorials
   - Export workflows

#### Deliverables
- Polished UI for spatial mapping
- Complete user documentation

---

## Software Architecture

### Backend Components

```
backend/
├── core/
│   ├── depth_estimator.py       # Depth estimation from images
│   ├── point_cloud_builder.py   # 3D point cloud generation
│   ├── mesh_reconstructor.py    # Surface reconstruction
│   ├── model_exporter.py        # Export to 3D formats
│   └── slam_system.py           # Camera pose estimation (optional)
├── api/
│   └── routes/
│       └── spatial.py            # Spatial mapping API
└── database/
    └── models.py                 # SpatialMap, ReconstructionSession models
```

### Frontend Components

```
frontend/src/
├── pages/
│   └── SpatialMappingPage.jsx   # Main spatial mapping interface
├── components/
│   ├── PointCloudViewer.jsx     # Three.js 3D viewer
│   ├── FloorPlanViewer.jsx      # 2D floor plan viewer
│   ├── ExportDialog.jsx         # Export format selection
│   └── CalibrationWizard.jsx    # Camera calibration tool
└── services/
    └── spatialService.js         # API client for spatial mapping
```

---

## Export Formats - Detailed Guide

### 1. Wavefront OBJ (.obj)
**Use Case**: Universal 3D format
**Compatible Software**: SketchUp, Blender, 3ds Max, Maya, Cinema 4D
**Features**: Geometry + textures (MTL file)

```python
# Export example
o3d.io.write_triangle_mesh("room_model.obj", mesh, write_vertex_colors=True)
```

**SketchUp Import**:
1. File → Import → Select OBJ file
2. Adjust scale if needed
3. Edit materials/textures

### 2. STL (.stl)
**Use Case**: 3D printing, CAD
**Compatible Software**: AutoCAD, SolidWorks, Fusion 360, 3D printers
**Features**: Geometry only (no colors/textures)

```python
o3d.io.write_triangle_mesh("room_model.stl", mesh)
```

### 3. DXF (.dxf)
**Use Case**: 2D floor plans
**Compatible Software**: AutoCAD, LibreCAD, QCAD
**Features**: 2D lines, polylines, dimensions

```python
import ezdxf

doc = ezdxf.new('R2010')
msp = doc.modelspace()

# Add floor plan contours
for wall in floor_plan_walls:
    msp.add_line(wall.start, wall.end)

doc.saveas("floor_plan.dxf")
```

**AutoCAD Workflow**:
1. Open DXF in AutoCAD
2. Add dimensions, annotations
3. Export to DWG for distribution

### 4. COLLADA (.dae)
**Use Case**: SketchUp, Unity, Unreal Engine
**Compatible Software**: SketchUp, game engines
**Features**: Geometry, materials, textures, camera positions

### 5. glTF/GLB (.gltf, .glb)
**Use Case**: Web 3D viewers, AR/VR
**Compatible Software**: Web browsers, Three.js, Babylon.js
**Features**: Optimized for web, includes animations

---

## Dependencies

### Python Packages

```txt
# 3D Processing
open3d>=0.17.0              # Point cloud and mesh processing
trimesh>=3.23.0             # Mesh utilities
pyvista>=0.42.0             # 3D visualization

# Depth Estimation
torch>=2.0.0                # PyTorch for deep learning
transformers>=4.30.0        # Hugging Face models (DPT, MiDaS)
timm>=0.9.0                 # Image models

# SLAM (Optional - for advanced reconstruction)
pyslam>=0.1.0               # Python SLAM library
g2o-python>=0.0.1           # Graph optimization

# Export Formats
ezdxf>=1.1.0                # DXF export for AutoCAD
pygltflib>=1.16.0           # glTF export
trimesh[easy]>=3.23.0       # Multiple format support

# Computer Vision
opencv-contrib-python>=4.8.0  # Already installed (includes SLAM)
```

### GPU Requirements

```bash
# NVIDIA CUDA (for GPU acceleration)
CUDA Toolkit: 11.8 or 12.1
cuDNN: 8.6+
NVIDIA Driver: 520+ (for RTX 30/40 series)

# AMD ROCm (alternative - experimental)
ROCm: 5.4+
```

---

## Cost Analysis

### Option 1: Monocular Depth (Budget)
| Item | Cost |
|------|------|
| Software dependencies | FREE (open source) |
| Pre-trained models | FREE |
| Existing cameras | $0 (already owned) |
| **TOTAL** | **$0** |

**Processing Time**: 5-10 seconds per frame
**Accuracy**: ±5-10%

---

### Option 2: Depth Cameras (Recommended)
| Item | Cost |
|------|------|
| Intel RealSense D435i (×2) | $600 |
| Software dependencies | FREE |
| **TOTAL** | **$600** |

**Processing Time**: Real-time (30 FPS)
**Accuracy**: ±2-3%

---

### Option 3: LiDAR (Professional)
| Item | Cost |
|------|------|
| Livox Mid-360 LiDAR | $1,200 |
| OR Velodyne VLP-16 | $4,000 |
| Processing workstation upgrade | $500 |
| **TOTAL** | **$1,700 - $4,500** |

**Processing Time**: Real-time
**Accuracy**: ±1mm

---

## Recommendations

### For Most Users: **Monocular Depth Estimation**
**Why**:
- Zero additional hardware cost
- Works with existing surveillance cameras
- Sufficient accuracy for most use cases
- Scalable to multiple cameras

**Best For**:
- Room layout documentation
- Security coverage planning
- General spatial awareness

**Limitations**:
- Requires GPU for reasonable performance
- Less accurate than dedicated depth sensors
- Requires good lighting

---

### For Professional Users: **Intel RealSense D435i**
**Why**:
- Excellent accuracy at reasonable cost
- Real-time performance
- Easy integration with OpenEye
- Works in low light

**Best For**:
- Precise measurements
- Real-time spatial tracking
- Indoor environments
- Professional installations

**Limitations**:
- Limited range (10m max)
- Requires mounting/installation
- Higher power consumption

---

### For Enterprise: **LiDAR Solution**
**Why**:
- Survey-grade accuracy
- Long range (100m+)
- Works in any conditions
- Professional CAD output

**Best For**:
- Large facilities
- Outdoor areas
- Critical infrastructure
- Regulatory compliance

**Limitations**:
- High cost
- Complex setup
- Overkill for most scenarios

---

## Implementation Timeline

### Conservative Estimate (1 Developer, Part-Time)
- **Phase 1**: 3 weeks (Foundation)
- **Phase 2**: 3 weeks (Depth Estimation)
- **Phase 3**: 2 weeks (Point Cloud)
- **Phase 4**: 2 weeks (Mesh Reconstruction)
- **Phase 5**: 2 weeks (Export)
- **Phase 6**: 1 week (UI Polish)
- **Total**: **13 weeks (~3 months)**

### Aggressive Estimate (2 Developers, Full-Time)
- **Total**: **6-8 weeks (~2 months)**

### Minimal Viable Product (MVP)
- Basic depth estimation
- Simple point cloud viewer
- OBJ export
- **Time**: **4-6 weeks**

---

## Next Steps

If you want to proceed with 3D room mapping, I recommend:

1. **Start with MVP** using monocular depth estimation
2. **Prototype** with existing cameras (zero cost)
3. **Evaluate** accuracy and performance
4. **Upgrade** to RealSense cameras if needed

Would you like me to:
1. **Start implementing Phase 1** (foundation)?
2. **Create a proof-of-concept** with a single camera?
3. **Focus on a different feature** instead?

---

**Document Version**: 1.0
**Created**: January 2025
**Author**: OpenEye Development Team
