import rclpy
from rclpy.node import Node
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
import subprocess
import re
import csv
import os
from datetime import datetime

CSV_PATH = '/workspace/logs/system_monitor.csv'

class SystemMonitorNode(Node):
    def __init__(self):
        super().__init__('system_monitor_node')

        self.publisher = self.create_publisher(
            DiagnosticArray, '/system_monitor', 10)

        self.timer = self.create_timer(1.0, self.monitor_callback)

        # Start tegrastats process
        try:
            self.process = subprocess.Popen(
                ['tegrastats', '--interval', '1000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.get_logger().info('tegrastats started.')
        except FileNotFoundError:
            self.process = None
            self.get_logger().warn('tegrastats not found. Running on non-Jetson hardware.')

        # CSV setup
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        self.csv_file   = open(CSV_PATH, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp',
            'cpu_percent',
            'gpu_percent',
            'ram_used_mb',
            'ram_total_mb',
            'power_mw',
            'temp_cpu_c',
        ])

        self.get_logger().info('SystemMonitorNode started.')

    def parse_tegrastats(self, line):
        """Parse tegrastats output line."""
        data = {
            'cpu_percent' : None,
            'gpu_percent' : None,
            'ram_used_mb' : None,
            'ram_total_mb': None,
            'power_mw'    : None,
            'temp_cpu_c'  : None,
        }

        try:
            # RAM
            ram = re.search(r'RAM (\d+)/(\d+)MB', line)
            if ram:
                data['ram_used_mb']  = float(ram.group(1))
                data['ram_total_mb'] = float(ram.group(2))

            # CPU
            cpu = re.findall(r'(\d+)%@\d+', line)
            if cpu:
                data['cpu_percent'] = round(
                    sum(float(c) for c in cpu) / len(cpu), 2)

            # GPU
            gpu = re.search(r'GR3D_FREQ (\d+)%', line)
            if gpu:
                data['gpu_percent'] = float(gpu.group(1))

            # Power
            power = re.search(r'VDD_IN (\d+)mW', line)
            if power:
                data['power_mw'] = float(power.group(1))

            # Temperature
            temp = re.search(r'cpu@([\d.]+)C', line)
            if temp:
                data['temp_cpu_c'] = float(temp.group(1))

        except Exception as e:
            self.get_logger().warn(f'Parse error: {e}')

        return data

    def monitor_callback(self):
        data = None

        if self.process:
            line = self.process.stdout.readline().strip()
            if line:
                data = self.parse_tegrastats(line)
        
        if not data:
            # tegrastats not available
            data = {
                'cpu_percent' : None,
                'gpu_percent' : None,
                'ram_used_mb' : None,
                'ram_total_mb': None,
                'power_mw'    : None,
                'temp_cpu_c'  : None,
            }

        # Publish to /system_monitor
        msg    = DiagnosticArray()
        status = DiagnosticStatus()
        status.name    = 'system_monitor'
        status.level   = DiagnosticStatus.OK
        status.message = 'System metrics'
        status.values  = [
            KeyValue(key='cpu_percent',  value=str(data['cpu_percent']) if data['cpu_percent'] is not None else 'N/A'),
            KeyValue(key='gpu_percent',  value=str(data['gpu_percent']) if data['gpu_percent'] is not None else 'N/A'),
            KeyValue(key='ram_used_mb',  value=str(data['ram_used_mb']) if data['ram_used_mb'] is not None else 'N/A'),
            KeyValue(key='ram_total_mb', value=str(data['ram_total_mb']) if data['ram_total_mb'] is not None else 'N/A'),
            KeyValue(key='power_mw',     value=str(data['power_mw']) if data['power_mw'] is not None else 'N/A'),
            KeyValue(key='temp_cpu_c',   value=str(data['temp_cpu_c']) if data['temp_cpu_c'] is not None else 'N/A'),
        ]


        msg.header.stamp = self.get_clock().now().to_msg()
        msg.status       = [status]
        self.publisher.publish(msg)

        # CSV 
        self.csv_writer.writerow([
            datetime.now().isoformat(),
            data['cpu_percent']  if data['cpu_percent']  is not None else 'N/A',
            data['gpu_percent']  if data['gpu_percent']  is not None else 'N/A',
            data['ram_used_mb']  if data['ram_used_mb']  is not None else 'N/A',
            data['ram_total_mb'] if data['ram_total_mb'] is not None else 'N/A',
            data['power_mw']     if data['power_mw']     is not None else 'N/A',
            data['temp_cpu_c']   if data['temp_cpu_c']   is not None else 'N/A',
        ])
        self.csv_file.flush()

        self.get_logger().info(
            f"CPU: {data['cpu_percent'] if data['cpu_percent'] is not None else 'N/A'}%  "
            f"GPU: {data['gpu_percent'] if data['gpu_percent'] is not None else 'N/A'}%  "
            f"RAM: {data['ram_used_mb'] if data['ram_used_mb'] is not None else 'N/A'}/"
            f"{data['ram_total_mb'] if data['ram_total_mb'] is not None else 'N/A'}MB  "
            f"PWR: {data['power_mw'] if data['power_mw'] is not None else 'N/A'}mW  "
            f"TEMP: {data['temp_cpu_c'] if data['temp_cpu_c'] is not None else 'N/A'}°C"
        )

    def destroy_node(self):
        if self.process:
            self.process.terminate()
        self.csv_file.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SystemMonitorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
