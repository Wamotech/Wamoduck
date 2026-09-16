import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'wamoduck_ros2'

# ---------------------------------------------------------------------------
# Where the reference gait CSVs come from.
#
# They are NOT copied into ros2/. The canonical copies stay at tools/matlab/data/ (they are
# also what the MATLAB player in tools/matlab reads), and this build installs them into
# share/wamoduck_ros2/data so that `ros2 launch wamoduck_ros2 gait_display.launch.py` works
# with no arguments at all. Same no-duplicate rule as the meshes in wamoduck_description.
# ---------------------------------------------------------------------------
_here = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.abspath(os.path.join(_here, os.pardir, os.pardir))
_gait_dir = os.path.join(_repo_root, 'tools', 'matlab', 'data')
_gait_csvs_absolute = sorted(glob(os.path.join(_gait_dir, 'gait_*.csv')))

# colcon asserts that every data_files source is RELATIVE
# (colcon_core/task/python/__init__.py, get_data_files_mapping), and setuptools resolves
# relative sources against the working directory colcon runs setup.py in, which is this
# package directory. So the canonical CSVs outside the package are addressed with a
# relative path rather than an absolute one. This is the same "install-time copy, never
# stored twice" mechanism wamoduck_description uses for its meshes.
_gait_csvs = [os.path.relpath(path, _here) for path in _gait_csvs_absolute]

if not _gait_csvs:
    print(
        f'[wamoduck_ros2] WARNING: no gait_*.csv found under {_gait_dir}.\n'
        '  The package will still build, but gait_player has no default CSV and will need\n'
        '  -p csv_path:=<file>. This happens when only the ros2/ subtree was copied.'
    )

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        (os.path.join('share', package_name), ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'data'), _gait_csvs),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Wamotech',
    maintainer_email='872624478@qq.com',
    description='Wamoduck ROS 2 nodes: gait replay, policy skeleton and link bridge.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'gait_player = wamoduck_ros2.gait_player:main',
            'policy_node = wamoduck_ros2.policy_node:main',
            'bridge_stub = wamoduck_ros2.bridge_stub:main',
        ],
    },
)
