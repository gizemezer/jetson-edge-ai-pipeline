"""
pipeline_mock.launch.py
-----------------------
Launches the full Edge AI pipeline using MOCK sensors (no hardware required).
Use this for local development and testing.

Nodes started:
  - mock_thermal_publisher   : simulated thermal camera (256x192, 25Hz, 32FC1)
  - mock_depth_publisher     : simulated depth camera (1280x720, 30Hz, 16UC1)
  - sensor_fusion_node       : fuses thermal + depth via ApproximateTimeSynchronizer
  - decision_node            : bitmap generation, alert publishing, CSV logging
  - diagnostics_node         : ROS2 diagnostics health monitoring
  - system_monitor_node      : CPU / memory monitoring
  - power_benchmark_node     : power mode and performance benchmarking
  - resolution_node          : resolution alignment benchmark (optional)
  - calibration_node         : calibration utilities

Usage:
  ros2 launch edge_ai_fusion pipeline_mock.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import LogInfo
import os
from launch.actions import ExecuteProcess, LogInfo 

def generate_launch_description():

    return LaunchDescription([

        LogInfo(msg='=== Edge AI Pipeline (MOCK MODE) Starting ==='),

        ExecuteProcess(
            cmd=['ros2', 'run', 'rqt_robot_monitor', 'rqt_robot_monitor'],
            output='screen',
            additional_env={'DISPLAY': 'host.docker.internal:0.0'},
        ),
        # ── MOCK SENSORS ──────────────────────────────────────────────────────
        Node(
            package='edge_ai_fusion',
            executable='mock_thermal_publisher',
            name='mock_thermal_publisher',
            output='screen',
            parameters=[],
        ),

        Node(
            package='edge_ai_fusion',
            executable='mock_depth_publisher',
            name='mock_depth_publisher',
            output='screen',
            parameters=[],
        ),

        # ── FUSION ────────────────────────────────────────────────────────────
        Node(
            package='edge_ai_fusion',
            executable='sensor_fusion_node',
            name='sensor_fusion_node',
            output='screen',
            parameters=[],
        ),

        # ── DECISION ──────────────────────────────────────────────────────────
        Node(
            package='edge_ai_fusion',
            executable='decision_node',
            name='decision_node',
            output='screen',
            parameters=[],
        ),

        # ── DIAGNOSTICS & MONITORING ──────────────────────────────────────────
        Node(
            package='edge_ai_fusion',
            executable='diagnostics_node',
            name='diagnostics_node',
            output='screen',
        ),

        Node(
            package='edge_ai_fusion',
            executable='system_monitor_node',
            name='system_monitor_node',
            output='screen',
        ),

        ExecuteProcess(
            cmd=['rqt'],
            output='screen',
        ),
        LogInfo(msg='=== All nodes launched (MOCK MODE) ==='),
    ])
