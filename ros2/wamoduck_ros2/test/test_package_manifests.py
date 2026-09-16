"""Regression tests for the package manifests themselves.

These exist because of a real bug that ``colcon build`` did **not** catch.

``wamoduck_ros2/package.xml`` originally contained a literal ``<->`` inside its
``<description>``. That makes the file invalid XML. ``catkin_pkg`` then fails to parse it,
so ``colcon``'s ROS package identification silently gives up on the package and
``colcon_python_setup_py`` classifies it as plain ``python`` instead of ``ros.ament_python``.
The build still succeeds, the node executables are still installed, and nothing looks wrong --
but no ROS environment is generated for the prefix, so the package never appears in
``ros2 pkg list``, ``ros2 launch`` cannot find it, and every node is unreachable. The only
symptom is "package not found" much later, with no hint that the manifest was the cause.

An unescaped ``<`` in any XML-ish file is the same class of error, so these tests parse every
manifest and check the two things colcon relies on: well-formed XML, and an explicit
``<build_type>`` in ``<export>``.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET

import pytest

_ROS2_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
_EXPECTED_BUILD_TYPES = {
    'wamoduck_msgs': 'ament_cmake',
    'wamoduck_description': 'ament_cmake',
    'wamoduck_ros2': 'ament_python',
}

# A bare '<' that is not the start of a tag, a comment, a CDATA section, a processing
# instruction or a closing tag. This is what a human typo looks like; XML parsers report it as
# a confusing "invalid token".
_SUSPICIOUS_LT = re.compile(r'<(?![/?!]|[A-Za-z_][\w.:-]*[\s/>])')


def _manifests() -> list[str]:
    found = []
    for entry in sorted(os.listdir(_ROS2_DIR)):
        candidate = os.path.join(_ROS2_DIR, entry, 'package.xml')
        if os.path.isfile(candidate):
            found.append(candidate)
    return found


def test_all_expected_packages_are_present():
    names = {os.path.basename(os.path.dirname(path)) for path in _manifests()}
    assert names == set(_EXPECTED_BUILD_TYPES), names


@pytest.mark.parametrize('name', sorted(_EXPECTED_BUILD_TYPES))
def test_package_xml_is_well_formed_and_declares_its_build_type(name):
    path = os.path.join(_ROS2_DIR, name, 'package.xml')
    raw = open(path, 'r', encoding='utf-8').read()

    # Parse first: this is what catkin_pkg does, and its failure mode is the silent one.
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        bare = _SUSPICIOUS_LT.findall(raw)
        raise AssertionError(
            f'{name}/package.xml is not well-formed XML: {exc}. A bare "<" in text is the '
            f'usual cause (found {len(bare)} candidate(s)); escape it as &lt; or rephrase.'
        ) from exc

    assert root.tag == 'package'
    assert root.get('format') == '3'
    assert root.findtext('name') == name
    assert root.findtext('maintainer'), 'package.xml needs a maintainer'
    assert root.findtext('license'), 'package.xml needs a license'

    export = root.find('export')
    assert export is not None, f'{name}/package.xml has no <export> element'
    assert export.findtext('build_type') == _EXPECTED_BUILD_TYPES[name], (
        f'{name}/package.xml declares build_type '
        f'{export.findtext("build_type")!r}, expected {_EXPECTED_BUILD_TYPES[name]!r}. '
        'Without this, colcon classifies the package as plain "python" or "cmake" and no ROS '
        'environment is generated for it.'
    )


@pytest.mark.parametrize('name', sorted(_EXPECTED_BUILD_TYPES))
def test_no_unescaped_angle_bracket_in_message_files(name):
    """Catch the same typo in ``.msg`` files, which are not XML-parsed.

    ``.xml`` files are covered by the parse test above, so this looks only at the message
    definitions -- and only outside comments, which are free text.
    """
    package_dir = os.path.join(_ROS2_DIR, name)
    offenders: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(package_dir):
        for filename in filenames:
            if not filename.endswith('.msg'):
                continue
            path = os.path.join(dirpath, filename)
            for line_no, line in enumerate(
                open(path, 'r', encoding='utf-8').read().splitlines(), start=1
            ):
                if line.strip().startswith('#'):
                    continue
                if _SUSPICIOUS_LT.search(line):
                    offenders.append(f'{path}:{line_no}: {line.strip()}')
    assert not offenders, 'unescaped "<" found outside a comment:\n' + '\n'.join(offenders)


def test_message_files_declare_the_link_contract_widths():
    """JointTarget must stay 14 joints plus a 3-vector twist: that is the 46-byte frame."""
    path = os.path.join(_ROS2_DIR, 'wamoduck_msgs', 'msg', 'JointTarget.msg')
    fields = [line.strip() for line in open(path, 'r', encoding='utf-8') if line.strip()]
    fields = [line for line in fields if not line.startswith('#')]
    assert 'float64[14] q_target_rad' in fields
    assert 'float64[3] twist' in fields
    assert 'std_msgs/Header header' in fields
    for mode in ('MODE_OFF', 'MODE_HOLD', 'MODE_POLICY', 'MODE_CALIB'):
        assert any(line.startswith(f'uint8 {mode}=') for line in fields), mode


def test_link_status_status_bits_match_the_protocol_module():
    """The ST_* constants are duplicated in the .msg (interfaces cannot import Python)."""
    from wamoduck_ros2 import frame_codec as fc

    path = os.path.join(_ROS2_DIR, 'wamoduck_msgs', 'msg', 'LinkStatus.msg')
    declared = {}
    for line in open(path, 'r', encoding='utf-8'):
        match = re.match(r'\s*uint16\s+(ST_\w+)=(\d+)\s*$', line)
        if match:
            declared[match.group(1)] = int(match.group(2))

    expected = {
        'ST_ENABLED': fc.ST_ENABLED,
        'ST_POLICY_MODE': fc.ST_POLICY_MODE,
        'ST_WATCHDOG': fc.ST_WATCHDOG,
        'ST_FAULT_OVERCURRENT': fc.ST_FAULT_OVERCURRENT,
        'ST_FAULT_OVERTEMP': fc.ST_FAULT_OVERTEMP,
        'ST_FAULT_ENCODER': fc.ST_FAULT_ENCODER,
        'ST_LIMIT_CLAMPED': fc.ST_LIMIT_CLAMPED,
        'ST_ESTOP': fc.ST_ESTOP,
        'ST_CAN_ERROR': fc.ST_CAN_ERROR,
        'ST_FALLEN': fc.ST_FALLEN,
    }
    assert declared == expected
