#!/usr/bin/env python3
"""One command to watch the robot walk the reference gait in RViz.

    ros2 launch wamoduck_ros2 gait_display.launch.py
    ros2 launch wamoduck_ros2 gait_display.launch.py csv_path:=/abs/gait_walk_1m_10Hz.csv
    ros2 launch wamoduck_ros2 gait_display.launch.py loop:=false

Composition
-----------
``wamoduck_description/display.launch.py`` (robot_state_publisher + RViz) plus
``gait_player``, with joint_state_publisher switched **off**: two publishers on
``/joint_states`` would interleave zero poses with the gait and look like a broken player.

NO PHYSICS. Nothing here simulates the robot. RViz integrates no dynamics, checks no contact
and applies no gravity, so a gait that looks plausible on screen has proven only that the
description animates. MuJoCo remains the physics reference.

The RViz configuration is chosen from ``publish_base_tf``:

* ``publish_base_tf:=true`` (default) -- gait_player broadcasts ``world -> base_link`` from
  the CSV's base_x / base_y / base_z / base_roll_rad, so ``wamoduck_world.rviz``
  (Fixed Frame ``world``) is used and the base trajectory is visible as well.
* ``publish_base_tf:=false`` -- nothing publishes ``world``, so RViz could not place the
  robot at all; ``wamoduck.rviz`` (Fixed Frame ``base_link``) is selected instead.

That choice is made here rather than left as a trap for whoever flips the flag.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _launch_setup(context, *args, **kwargs):
    description_share = get_package_share_directory('wamoduck_description')

    publish_base_tf = LaunchConfiguration('publish_base_tf').perform(context).strip().lower()
    base_tf_enabled = publish_base_tf in ('true', '1', 'yes')

    rviz_config = LaunchConfiguration('rviz_config').perform(context).strip()
    if not rviz_config:
        rviz_config = os.path.join(
            description_share, 'rviz',
            'wamoduck_world.rviz' if base_tf_enabled else 'wamoduck.rviz',
        )

    csv_path = LaunchConfiguration('csv_path').perform(context).strip()
    if not os.path.isfile(csv_path):
        raise RuntimeError(
            f'gait_display.launch.py: gait CSV not found: {csv_path}\n'
            'The default is the copy of tools/matlab/data/gait_cycle_2s_50Hz.csv installed '
            'into share/wamoduck_ros2/data. Pass csv_path:=<file> to use another one.'
        )

    display = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(description_share, 'launch', 'display.launch.py')
        ),
        launch_arguments={
            'rviz': LaunchConfiguration('rviz'),
            'rviz_config': rviz_config,
            'urdf_file': LaunchConfiguration('urdf_file'),
            'use_joint_state_publisher': 'false',
            'use_gui': 'false',
        }.items(),
    )

    gait_player = Node(
        package='wamoduck_ros2',
        executable='gait_player',
        name='gait_player',
        output='screen',
        parameters=[{
            'csv_path': csv_path,
            'loop': LaunchConfiguration('loop'),
            'time_scale': LaunchConfiguration('time_scale'),
            'start_delay_s': LaunchConfiguration('start_delay_s'),
            'publish_base_tf': base_tf_enabled,
            'urdf_path': LaunchConfiguration('urdf_file'),
        }],
    )

    return [display, gait_player]


def generate_launch_description():
    default_csv = os.path.join(
        get_package_share_directory('wamoduck_ros2'), 'data', 'gait_cycle_2s_50Hz.csv'
    )
    return LaunchDescription([
        DeclareLaunchArgument(
            'csv_path', default_value=default_csv,
            description='Gait CSV to replay. Defaults to the installed copy of '
                        'tools/matlab/data/gait_cycle_2s_50Hz.csv. Use '
                        'gait_walk_1m_10Hz.csv for the 1 m / 10 Hz track.'),
        DeclareLaunchArgument(
            'loop', default_value='true',
            description='Repeat the track forever (default true, so the window does not '
                        'freeze while nobody is looking).'),
        DeclareLaunchArgument(
            'time_scale', default_value='1.0',
            description='Playback rate multiplier; 1.0 is the rate recorded in the file.'),
        DeclareLaunchArgument(
            'start_delay_s', default_value='1.0',
            description='Wait this long before the first sample, so RViz has time to load '
                        'the meshes and the viewer sees the robot move from the start.'),
        DeclareLaunchArgument(
            'publish_base_tf', default_value='true',
            description='Broadcast world -> base_link from the CSV base columns.'),
        DeclareLaunchArgument(
            'rviz', default_value='true', description='Start RViz.'),
        DeclareLaunchArgument(
            'rviz_config', default_value='',
            description='RViz config. Empty selects wamoduck_world.rviz when '
                        'publish_base_tf is true, otherwise wamoduck.rviz.'),
        DeclareLaunchArgument(
            'urdf_file', default_value='',
            description='URDF to publish; empty uses the one installed by '
                        'wamoduck_description.'),
        OpaqueFunction(function=_launch_setup),
    ])
