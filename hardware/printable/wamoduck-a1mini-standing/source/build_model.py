"""Rebuild the one-piece, millimetre-scale Wamoduck display model from q=0 URDF."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import numpy as np
import trimesh
import vtk
import manifold3d
from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from scipy import ndimage
from skimage.measure import marching_cubes

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
ROOT = OUT.parents[2]
URDF = ROOT / 'models/wmduck/wmduck.urdf'


def origin(element):
    t = np.eye(4)
    if element is not None:
        rpy = np.fromstring(element.get('rpy', '0 0 0'), sep=' ')
        t = trimesh.transformations.euler_matrix(*rpy, axes='sxyz')
        t[:3, 3] = np.fromstring(element.get('xyz', '0 0 0'), sep=' ')
    return t


def load_pose():
    robot = ET.parse(URDF).getroot()
    transforms = {'base_link': np.eye(4)}
    pending = list(robot.findall('joint'))
    while pending:
        progress = False
        for joint in pending[:]:
            parent = joint.find('parent').get('link')
            if parent in transforms:
                transforms[joint.find('child').get('link')] = transforms[parent] @ origin(joint.find('origin'))
                pending.remove(joint)
                progress = True
        assert progress, 'Invalid joint tree'
    parts = []
    for link in robot.findall('link'):
        for visual in link.findall('visual'):
            mesh_tag = visual.find('geometry/mesh')
            src = URDF.parent / mesh_tag.get('filename')
            mesh = trimesh.load_mesh(src, process=True)
            mesh.apply_scale(np.fromstring(mesh_tag.get('scale', '1 1 1'), sep=' '))
            mesh.apply_transform(transforms[link.get('name')] @ origin(visual.find('origin')))
            mesh.apply_scale(1000)
            parts.append({'name': visual.get('name'), 'file': src.name, 'link': link.get('name'), 'mesh': mesh})
    return parts, transforms


def inspect():
    parts, transforms = load_pose()
    report = []
    for p in parts:
        m = p['mesh']
        shells = m.split(only_watertight=False)
        report.append({k: v for k, v in p.items() if k != 'mesh'} | {
            'bounds_mm': m.bounds.round(4).tolist(), 'faces': len(m.faces),
            'watertight': bool(m.is_watertight), 'volume_mm3': float(m.volume),
            'shells': [{'faces': len(s.faces), 'watertight': bool(s.is_watertight),
                        'volume_mm3': round(float(s.volume), 4)} for s in shells]})
    OUT.mkdir(parents=True, exist_ok=True)
    (HERE / 'source_geometry_audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def voxelize(mesh, pitch, grid_origin, shape):
    """Scan-convert local CAD surfaces on a common grid using VTK's solid stencil."""
    lo = np.maximum(np.floor((mesh.bounds[0] - grid_origin) / pitch).astype(int) - 2, 0)
    hi = np.minimum(np.ceil((mesh.bounds[1] - grid_origin) / pitch).astype(int) + 3, shape)
    local_shape = hi - lo
    poly = vtk.vtkPolyData()
    points = vtk.vtkPoints()
    points.SetData(numpy_to_vtk(np.asarray(mesh.vertices), deep=True))
    poly.SetPoints(points)
    cells = vtk.vtkCellArray()
    cells.SetCells(len(mesh.faces), vtk.util.numpy_support.numpy_to_vtkIdTypeArray(
        np.column_stack([np.full(len(mesh.faces), 3), mesh.faces]).astype(np.int64).ravel(), deep=True))
    poly.SetPolys(cells)
    stencil = vtk.vtkPolyDataToImageStencil()
    stencil.SetInputData(poly)
    stencil.SetOutputOrigin(grid_origin + lo * pitch)
    stencil.SetOutputSpacing(pitch, pitch, pitch)
    stencil.SetOutputWholeExtent(0, int(local_shape[0])-1, 0, int(local_shape[1])-1, 0, int(local_shape[2])-1)
    stencil.Update()
    image = vtk.vtkImageStencilToImage()
    image.SetInputConnection(stencil.GetOutputPort())
    image.SetInsideValue(1)
    image.SetOutsideValue(0)
    image.SetOutputScalarTypeToUnsignedChar()
    image.Update()
    values = vtk_to_numpy(image.GetOutput().GetPointData().GetScalars()).reshape(tuple(local_shape), order='F').astype(bool)
    return tuple(slice(int(a), int(b)) for a,b in zip(lo, hi)), values


def rounded_base(bounds, height=3.2, margin=4, radius=5):
    lower, upper = bounds.copy()
    lower[:2] -= margin
    upper[:2] += margin
    center = (lower + upper) / 2
    size = upper - lower
    items = []
    for dim in ([size[0]-2*radius, size[1], height], [size[0], size[1]-2*radius, height]):
        box = trimesh.creation.box(dim)
        box.apply_translation([center[0], center[1], height/2])
        items.append(box)
    for x in (lower[0]+radius, upper[0]-radius):
        for y in (lower[1]+radius, upper[1]-radius):
            cyl = trimesh.creation.cylinder(radius=radius, height=height, sections=64)
            cyl.apply_translation([x,y,height/2])
            items.append(cyl)
    return trimesh.boolean.union(items, engine='manifold')


def build():
    parts, transforms = load_pose()
    original = trimesh.util.concatenate([p['mesh'] for p in parts])
    np.testing.assert_allclose(original.extents, [181.507506716,221.205006024,390.830005534], atol=0.002)
    # 156 mm robot + 3.2 mm base, allowing a small surface-thickening margin.
    scale = 156.0 / original.extents[2]
    shift = np.array([-original.bounds[:,0].mean()*scale, 0, 2.8-original.bounds[0,2]*scale])
    geometry = []
    for p in parts:
        if p['file'] == 'IMU_YB-MRA02.stl':
            continue  # Zero-thickness internal sensor sheet is not printable.
        m = p['mesh'].copy()
        m.apply_scale(scale)
        m.apply_translation(shift)
        p['print_mesh'] = m
        geometry.append(m)
    feet = trimesh.util.concatenate([p['print_mesh'] for p in parts if p['file'] in ('Left_feet.stl','Right_feet.stl')])
    base = rounded_base(feet.bounds)
    geometry.append(base)
    # Lock all 15 articulated axes with hidden solid pins (4.8 mm diameter).
    robot = ET.parse(URDF).getroot()
    pins = []
    for joint in robot.findall('joint'):
        if joint.get('type') == 'fixed':
            continue
        t = transforms[joint.find('child').get('link')]
        center = t[:3,3] * 1000 * scale + shift
        axis = t[:3,:3] @ np.fromstring(joint.find('axis').get('xyz'), sep=' ')
        pin = trimesh.creation.cylinder(radius=2.4, segment=[center-axis*3.5, center+axis*3.5], sections=48)
        geometry.append(pin)
        pins.append({'joint':joint.get('name'), 'center_mm':center.tolist(),'diameter_mm':4.8,'length_mm':7})
    pitch = 0.20
    all_bounds = np.array([m.bounds for m in geometry])
    grid_origin = np.floor((all_bounds[:,0].min(axis=0)-2)/pitch)*pitch
    shape = np.ceil((all_bounds[:,1].max(axis=0)+2-grid_origin)/pitch).astype(int)+1
    solid = np.zeros(tuple(shape), dtype=bool)
    print('grid', shape, 'million voxels', solid.size/1e6, flush=True)
    for i,m in enumerate(geometry):
        sl, vox = voxelize(m, pitch, grid_origin, shape)
        solid[sl] |= vox
        print('voxelized',i+1,len(geometry),flush=True)
    # Grow by 0.4 mm to reinforce thin CAD plates and close press-fit gaps.
    solid = ndimage.binary_dilation(solid, iterations=2)
    solid = ndimage.binary_closing(solid, iterations=3)
    solid = ndimage.binary_fill_holes(solid)
    labels, count = ndimage.label(solid)
    sizes = np.bincount(labels.ravel())
    print('components',count,'sizes',sorted(sizes[1:],reverse=True)[:30],flush=True)
    keep = int(np.argmax(sizes[1:])+1)
    removed = int(sizes[1:].sum()-sizes[keep])
    assert removed * pitch**3 < 30, f'Significant disconnected parts: {removed*pitch**3} mm3'
    solid = labels == keep
    del labels
    # Cut pedestal perfectly flat at the build plate; keep a closed bottom cap.
    k = int(round((0-grid_origin[2])/pitch))
    solid[:,:,:k] = False
    vertices, faces, _, _ = marching_cubes(solid, level=0.5, spacing=(pitch,pitch,pitch), allow_degenerate=False)
    vertices += grid_origin
    mesh = trimesh.Trimesh(vertices, faces, process=True)
    print('marching mesh',len(mesh.faces),mesh.is_watertight,mesh.is_winding_consistent,flush=True)
    trimesh.smoothing.filter_taubin(mesh, lamb=0.5, nu=0.53, iterations=10)
    mesh.fix_normals()
    # fix_normals may leave global inversion when touching edges mean the
    # marching mesh is not yet watertight. Plane clipping needs positive volume.
    if mesh.volume < 0:
        mesh.invert()
    print('smoothed mesh',len(mesh.faces),mesh.is_watertight,mesh.is_winding_consistent,flush=True)
    # CAD micro-slits can leave six touching edges in marching-cubes output.
    # Manifold resolves coincident topology and caps the bottom plane robustly.
    manifold = manifold3d.Manifold(manifold3d.Mesh64(mesh.vertices,mesh.faces.astype(np.uint64)))
    assert manifold.status() == manifold3d.Error.NoError
    manifold = manifold.trim_by_plane([0,0,1],0.05).simplify(0.035)
    result = manifold.to_mesh64()
    mesh = trimesh.Trimesh(result.vert_properties[:,:3],result.tri_verts,process=True)
    print('cut mesh',len(mesh.faces),mesh.is_watertight,mesh.is_winding_consistent,flush=True)
    mesh.apply_translation([0,0,-0.05])
    # Give the delivered model an exact nominal height.
    mesh.apply_scale(160.0/mesh.extents[2])
    mesh.merge_vertices()
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals(multibody=True)
    # STL stores float32 coordinates. Canonicalize at that precision before
    # delivery so tiny coplanar slivers cannot collapse into zero-area faces.
    final_manifold = manifold3d.Manifold(manifold3d.Mesh(
        mesh.vertices.astype(np.float32), mesh.faces.astype(np.uint32))).simplify(0.005)
    assert final_manifold.status() == manifold3d.Error.NoError
    final_data = final_manifold.to_mesh()
    mesh = trimesh.Trimesh(final_data.vert_properties[:,:3],final_data.tri_verts,process=True)
    mesh.fix_normals(multibody=True)
    assert mesh.is_volume, 'The final mesh must be watertight with outward normals and positive volume'
    assert len(mesh.split()) == 1
    path = OUT / 'Wamoduck_Standing_160mm.stl'
    mesh.export(path)
    mesh.export(OUT / 'Wamoduck_Standing_160mm.3mf')
    mesh = trimesh.load_mesh(path,process=True)
    assert mesh.is_volume and len(mesh.split()) == 1
    assert np.all(mesh.area_faces > 1e-10), 'Float32 STL must not contain collapsed triangles'
    bottom_faces = np.max(np.abs(mesh.triangles[:,:,2]),axis=1) < 1e-6
    assert np.all(mesh.face_normals[bottom_faces,2] < -0.999), 'Flat cap must face down'
    source_report = {
        'source_urdf': str(URDF.relative_to(ROOT)), 'source_pose':'all 15 revolute joints q=0',
        'source_bounds_mm':original.bounds.tolist(), 'source_scale':scale,
        'voxel_pitch_mm_before_final_scale':pitch,'surface_growth_mm_before_final_scale':0.4,
        'mesh_simplification_tolerance_mm_before_final_scale':0.035,
        'stl_float32_simplification_tolerance_mm':0.005,
        'removed_small_disconnected_volume_mm3':removed*pitch**3, 'joint_pins':pins,
        'omitted_meshes':['IMU_YB-MRA02.stl'], 'base_nominal_height_mm':3.2,
        'final_size_xyz_mm':mesh.extents.tolist(),'vertices':len(mesh.vertices),'triangles':len(mesh.faces),
        'watertight':bool(mesh.is_watertight),'winding_consistent':bool(mesh.is_winding_consistent),
        'volume_mm3':float(mesh.volume),'connected_shells':len(mesh.split()),
        'positive_volume':bool(mesh.is_volume),'degenerate_triangles':int(np.sum(mesh.area_faces<=1e-10)),
        'bottom_cap_area_mm2':float(mesh.area_faces[bottom_faces].sum()),
        'bottom_cap_all_normals_down':bool(np.all(mesh.face_normals[bottom_faces,2]<-0.999)),
    }
    import hashlib
    source_report['stl_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    source_report['urdf_sha256'] = hashlib.sha256(URDF.read_bytes()).hexdigest()
    (OUT/'geometry_validation.json').write_text(json.dumps(source_report,indent=2),encoding='utf-8')
    print(json.dumps(source_report,indent=2),flush=True)


def render():
    import pyvista as pv
    mesh = pv.read(OUT/'Wamoduck_Standing_160mm.stl')
    p = pv.Plotter(off_screen=True,window_size=(1800,1400),shape=(1,2),border=False)
    for index,camera in enumerate(([270,-380,240],[0,-440,130])):
        p.subplot(0,index)
        p.set_background('#f4f2ed')
        p.add_mesh(mesh,color='#aeb5bf',smooth_shading=True,specular=0.3,specular_power=35)
        p.add_mesh(pv.Plane(center=(0,0,-0.15),direction=(0,0,1),i_size=240,j_size=240),color='#e4e0d8')
        p.camera_position = [camera,[0,0,78],[0,0,1]]
        p.enable_parallel_projection()
        p.camera.parallel_scale=94
        p.enable_anti_aliasing('ssaa')
        p.add_text('WAMODUCK  /  160 mm' if index==0 else 'Standing pose / one piece',position='upper_left',font_size=13,color='#30363e')
    p.screenshot(OUT/'preview.png')
    p.close()


if __name__ == '__main__':
    import sys
    {'inspect':inspect,'build':build,'render':render}[sys.argv[1] if len(sys.argv)>1 else 'inspect']()
