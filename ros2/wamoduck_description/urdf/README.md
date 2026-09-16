# Why there is no `wmduck.urdf` checked in here

This directory intentionally contains no URDF file. The package builds one.

## Where the description actually comes from

| Artifact | Lives at | Stored in Git |
| --- | --- | --- |
| Canonical URDF | `models/wmduck/wmduck.urdf` | yes, once |
| 20 binary STL meshes | `models/wmduck/meshes/*.stl` | yes, once, ~11 MB |
| ROS-installable URDF | generated into the build tree, installed to `share/wamoduck_description/urdf/wmduck.urdf` | **no** |
| Build manifest | generated next to it as `wmduck.ros.manifest.json` | **no** |

`models/wmduck/` is the single source of truth. Nothing here duplicates it.

## What the build does

`CMakeLists.txt` runs `scripts/generate_ros_urdf.py` before installing, then installs the
result. The script performs exactly two things:

1. **Rewrites mesh references.** The canonical URDF says `filename="meshes/Head.stl"`.
   That path is relative to the URDF file, which is how MuJoCo-oriented tooling resolves
   it, but `robot_state_publisher` + RViz hand the string to `resource_retriever`, which
   only understands `package://`, `file://` and paths relative to the *current working
   directory*. Launch RViz from anywhere else and the robot silently renders empty. So the
   script rewrites every reference to
   `package://wamoduck_description/meshes/Head.stl`.

2. **Refuses to change anything else.** It re-parses both the source and the rewritten
   file and aborts the build if the robot name, the link count, the movable joint list (in
   document order), the fixed joint list or the root link differ. The only textual
   difference between the two files is the mesh URI prefix, which
   `wamoduck_ros2/test/test_model_contract.py` also checks independently.

No link, joint, origin, axis, limit, mass, inertia, visual or collision entry is touched, so
the ROS description and the MJCF used for training still describe the same robot.

## Why meshes are installed rather than symlinked

The alternative -- a symlink such as `meshes -> ../../models/wmduck/meshes` committed into
this package -- was rejected:

* `colcon`/`ament` install steps follow symlinks inconsistently across platforms, and
  `install(DIRECTORY)` would have to be trusted to dereference them;
* Git symlinks need `core.symlinks=true` plus the Windows "Developer Mode" / admin
  privilege to even be created on Windows, so a clone on another Windows machine can end up
  with a **text file containing a path** instead of a link. That failure mode is silent
  until RViz shows nothing.

So the build copies the meshes out of `models/wmduck/meshes` into
`share/wamoduck_description/meshes` at install time. The meshes exist exactly once inside
the Git repository; the second copy exists only in the build/install tree, which is
disposable.

## Consequence you should know about

This package needs the canonical model directory to build. Inside a full clone that
resolves automatically. If you copy only the `ros2/` subtree to another machine (for
example the RDK X5), point the build at a model directory explicitly:

```bash
colcon build --packages-select wamoduck_description \
  --cmake-args -DWAMODUCK_MODELS_DIR=/opt/wamoduck/models/wmduck
```

The build fails loudly with that instruction if `wmduck.urdf` or the mesh directory is
missing, rather than installing a description that renders an empty robot.
