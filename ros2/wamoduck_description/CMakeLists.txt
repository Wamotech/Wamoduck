cmake_minimum_required(VERSION 3.8)
project(wamoduck_description)

find_package(ament_cmake REQUIRED)
find_package(Python3 COMPONENTS Interpreter REQUIRED)

# ---------------------------------------------------------------------------
# Where the canonical model lives.
#
# The default assumes this package sits at <repo>/ros2/wamoduck_description, so
# ../../models/wmduck is <repo>/models/wmduck. Override it when only the ros2/ tree has been
# copied to another machine:
#
#     colcon build --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
#
# REALPATH matters: a common way to build without copying sources is to symlink the package
# into a workspace (src/wamoduck_description -> <repo>/ros2/wamoduck_description). CMake then
# keeps the *logical* source path, and ".." would walk up the workspace instead of the
# repository. Resolving symlinks first makes both layouts work with the same default.
#
# Nothing is copied into the source tree: the meshes are installed from wherever this points.
# ---------------------------------------------------------------------------
if(NOT DEFINED WAMODUCK_MODELS_DIR)
  get_filename_component(_wmduck_pkg_real "${CMAKE_CURRENT_SOURCE_DIR}" REALPATH)
  set(WAMODUCK_MODELS_DIR "${_wmduck_pkg_real}/../../models/wmduck")
endif()
get_filename_component(WAMODUCK_MODELS_DIR "${WAMODUCK_MODELS_DIR}" ABSOLUTE)

set(_wmduck_src_urdf "${WAMODUCK_MODELS_DIR}/wmduck.urdf")
set(_wmduck_meshes "${WAMODUCK_MODELS_DIR}/meshes")

if(NOT EXISTS "${_wmduck_src_urdf}")
  message(FATAL_ERROR
    "wamoduck_description: canonical URDF not found at '${_wmduck_src_urdf}'.\n"
    "This package intentionally does not carry its own URDF copy, so it needs the model "
    "directory. Either build inside the full repository, or point the build at the model:\n"
    "  colcon build --cmake-args -DWAMODUCK_MODELS_DIR=<dir containing wmduck.urdf>")
endif()

file(GLOB _wmduck_mesh_files "${_wmduck_meshes}/*.stl")
list(LENGTH _wmduck_mesh_files _wmduck_mesh_count)
if(_wmduck_mesh_count EQUAL 0)
  message(FATAL_ERROR
    "wamoduck_description: no *.stl meshes under '${_wmduck_meshes}'.\n"
    "The URDF references them by basename, so a missing mesh directory installs a description\n"
    "that renders as an empty robot.")
endif()
message(STATUS "wamoduck_description: source URDF ${_wmduck_src_urdf}")
message(STATUS "wamoduck_description: source meshes ${_wmduck_meshes} (${_wmduck_mesh_count} STL files)")

# ---------------------------------------------------------------------------
# Build-time URDF generation: file-relative mesh paths -> package:// mesh paths.
# ---------------------------------------------------------------------------
set(_gen_dir "${CMAKE_CURRENT_BINARY_DIR}/urdf")
set(_gen_urdf "${_gen_dir}/wmduck.urdf")
set(_gen_manifest "${_gen_dir}/wmduck.ros.manifest.json")

add_custom_command(
  OUTPUT "${_gen_urdf}" "${_gen_manifest}"
  COMMAND ${CMAKE_COMMAND} -E make_directory "${_gen_dir}"
  COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/scripts/generate_ros_urdf.py"
          --source-urdf "${_wmduck_src_urdf}"
          --meshes-dir "${_wmduck_meshes}"
          --package-name "${PROJECT_NAME}"
          --output "${_gen_urdf}"
          --manifest "${_gen_manifest}"
  DEPENDS "${_wmduck_src_urdf}"
          "${CMAKE_CURRENT_SOURCE_DIR}/scripts/generate_ros_urdf.py"
  COMMENT "wamoduck_description: generating package:// URDF from ${_wmduck_src_urdf}"
  VERBATIM
)

add_custom_target(wamoduck_urdf ALL DEPENDS "${_gen_urdf}" "${_gen_manifest}")

install(FILES "${_gen_urdf}" "${_gen_manifest}"
        DESTINATION share/${PROJECT_NAME}/urdf)

# Straight out of models/wmduck/meshes -- never stored inside ros2/.
install(DIRECTORY "${_wmduck_meshes}/"
        DESTINATION share/${PROJECT_NAME}/meshes)

install(DIRECTORY launch rviz
        DESTINATION share/${PROJECT_NAME})

ament_package()
