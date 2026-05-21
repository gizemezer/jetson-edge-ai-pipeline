from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_dir = get_package_share_directory('thermal_camera_driver')
    config = os.path.join(pkg_dir, 'config', 'camera_params.yaml')

    return LaunchDescription([
        Node(
            package='thermal_camera_driver',
            executable='thermal_camera_driver_node',
            name='thermal_camera_driver',
            parameters=[config],
            output='screen'
        ),
        Node(
            package='thermal_camera_driver',
            executable='temperature_map_node',
            name='temperature_map_node',
            parameters=[config],
            output='screen'
        ),
    ])
