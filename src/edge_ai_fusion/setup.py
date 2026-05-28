from setuptools import find_packages, setup

package_name = 'edge_ai_fusion'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/pipeline_mock.launch.py']),
        ('share/' + package_name + '/launch', ['launch/pipeline_hardware.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='gizemezer',
    maintainer_email='ezergizem3@gmail.com',
    description='Edge AI multi-sensor fusion (thermal and depth) inference pipeline',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'sensor_fusion_node = edge_ai_fusion.sensor_fusion_node:main',
             'mock_thermal_publisher = edge_ai_fusion.mock_thermal_publisher:main',
             'mock_depth_publisher = edge_ai_fusion.mock_depth_publisher:main',
             'decision_node = edge_ai_fusion.decision_node:main',
             'resolution_node = edge_ai_fusion.resolution_node:main',
             'system_monitor_node = edge_ai_fusion.system_monitor_node:main',
             'calibration_node = edge_ai_fusion.calibration_node:main',
             'power_benchmark_node = edge_ai_fusion.power_benchmark_node:main',
             'diagnostics_node = edge_ai_fusion.diagnostics_node:main',
             'merge_calibration_reports = edge_ai_fusion.merge_calibration_reports:main',
             'merge_power_reports = edge_ai_fusion.merge_power_reports:main',
             'benchmark_recorder = edge_ai_fusion.benchmark_recorder_node:main',
             'analyze_latency = edge_ai_fusion.analyze_latency:main',
        ],
    },
)
