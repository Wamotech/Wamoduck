#!/usr/bin/env python3
"""Show the Wamoduck description in RViz: robot_state_publisher + (optionally) RViz.

    ros2 launch wamoduck_description display.launch.py

Scope warning -- read this before interpreting what you see
-----------------------------------------------------------
There is NO physics engine anywhere in this launch. Nothing integrates forces, nothing
collides, nothing falls. This launches a kinematic tree and paints it:

  * ``robot_state_publisher`` turns ``/robot_description`` + ``/joint_states`` into TF,
  * ``joint_state_publisher`` publishes zeros for every movable joint (this is the CAD
    standing pose, because the contract's ``default_joint_pos`` is all zeros),
  * RViz draws the meshes at those frames.

So this launch promises "the description is loadable, complete and visually coherent".
It does not promise, and cannot show, anything about dynamics. MuJoCo remains the physics
reference; the Gazebo stage comes later.

Joint-state ownership, and why it is decided here rather than with conditions
-----------------------------------------------------------------------------
Exactly one thing may publish ``/joint_states``. Two publishers would interleave two
different poses and look like a broken description rather than a configuration error, so the
choice is made explicitly from the resolved argument values:

=========================================  =========================  ==================
``use_joint_state_publisher``  ``use_gui``  publisher started
=========================================  =========================  ==================
true                           false        ``joint_state_publisher`` (zeros)
true                           true         ``joint_state_publisher_gui`` (sliders)
false                          false        none -- something else owns the topic
false                          true         ``joint_state_publisher_gui`` (sliders)
=========================================  =========================  ==================

``gait_display.launch.py`` in ``wamoduck_ros2`` includes this file with both set false,
because ``gait_player`` owns ``/joint_states`` for that launch.

Arguments
---------
rviz                       start RViz (default true)
rviz_config                .rviz file to open; empty means <share>/rviz/wamoduck.rviz
urdf_file                  URDF to publish; empty means the installed generated URDF
use_joint_state_publisher  start the zero-pose publisher (default true)
use_gui                    use the draggable-slider variant (default false)
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_TRUTHY = ('true', '1', 'yes', 'on')


def _as_bool(text: str) -> bool:
    return text.strip().lower() in _TRUTHY


def _launch_setup(context, *args, **kwargs):
    share = get_package_share_directory('wamoduck_description')

    urdf_file = LaunchConfiguration('urdf_file').perform(context).strip()
    if not urdf_file:
        urdf_file = os.path.join(share, 'urdf', 'wmduck.urdf')
    if not os.path.isfile(urdf_file):
        raise RuntimeError(
            f'display.launch.py: URDF not found: {urdf_file}\n'
            'Did the package build run? wamoduck_description generates its URDF at build '
            'time from models/wmduck/wmduck.urdf.'
        )

    rviz_config = LaunchConfiguration('rviz_config').perform(context).strip()
    if not rviz_config:
        rviz_config = os.path.join(share, 'rviz', 'wamoduck.rviz')
    if not os.path.isfile(rviz_config):
        raise RuntimeError(f'display.launch.py: RViz config not found: {rviz_config}')

    use_joint_state_publisher = _as_bool(
        LaunchConfiguration('use_joint_state_publisher').perform(context)
    )
    use_gui = _as_bool(LaunchConfiguration('use_gui').perform(context))

    with open(urdf_file, 'r', encoding='utf-8') as handle:
        robot_description = handle.read()

    nodes = [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': robot_description,
                # Meshes use package:// URIs, so no extra mesh search path is needed.
                'publish_frequency': 30.0,
            }],
        ),
    ]

    if use_gui:
        nodes.append(Node(
            package='joint_state_publisher_gui',
            executable='joint_state_publisher_gui',
            name='joint_state_publisher_gui',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ))
    elif use_joint_state_publisher:
        nodes.append(Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ))

    nodes.append(Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('rviz')),
    ))
    return nodes


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'rviz', default_value='true', description='Start RViz.'),
        DeclareLaunchArgument(
            'rviz_config', default_value='',
            description='RViz .rviz file. Empty means <share>/rviz/wamoduck.rviz '
                        '(Fixed Frame: base_link). Use rviz/wamoduck_world.rviz when '
                        'something publishes a world -> base_link transform.'),
        DeclareLaunchArgument(
            'urdf_file', default_value='',
            description='URDF to publish. Defaults to '
                        '<share>/wamoduck_description/urdf/wmduck.urdf, which is generated '
                        'at build time from models/wmduck/wmduck.urdf.'),
        DeclareLaunchArgument(
            'use_joint_state_publisher', default_value='true',
            description='Start joint_state_publisher (publishes zeros = CAD standing pose). '
                        'Set false when gait_player or a policy owns /joint_states.'),
        DeclareLaunchArgument(
            'use_gui', default_value='false',
            description='Use joint_state_publisher_gui for draggable joint sliders instead '
                        'of the zero-pose publisher.'),
        OpaqueFunction(function=_launch_setup),
    ])
