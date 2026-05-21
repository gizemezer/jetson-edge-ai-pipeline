from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    device_arg = DeclareLaunchArgument(
        'device',
        default_value='/dev/video6',
        description='Thermal camera device path'
    )

    realsense_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(
                get_package_share_directory('realsense2_camera'),
                'launch', 'rs_launch.py')
        ])
    )

    return LaunchDescription([
        device_arg,

        Node(
            package='edge_ai_fusion',
            executable='system_monitor_node',
            name='system_monitor_node',
            output='screen',
        ),

        Node(
            package='thermal_camera_driver',
            executable='thermal_camera_driver_node',
            name='thermal_camera_driver_node',
            output='screen',
            parameters=[{'device': LaunchConfiguration('device')}],
        ),

        realsense_launch,

        Node(
            package='edge_ai_fusion',
            executable='sensor_fusion_node',
            name='sensor_fusion_node',
            output='screen',
        ),

        Node(
            package='edge_ai_fusion',
            executable='decision_node',
            name='decision_node',
            output='screen',
        ),
    ])