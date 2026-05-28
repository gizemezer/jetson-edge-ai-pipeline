import rclpy
from rclpy.node import Node
from diagnostic_msgs.msg import DiagnosticArray
from edge_ai_interfaces.msg import DecisionResult # Yeni mesaj tipimiz eklendi
import os
import csv
from datetime import datetime

CALIB_SEC    = 600
STEADY_START = 300
THRESHOLD    = 0.05


class CalibrationNode(Node):
    def __init__(self):
        super().__init__('calibration_node')

        self.declare_parameter('power_mode', '7W')
        self.power_mode = self.get_parameter('power_mode').get_parameter_value().string_value

        self.csv_path = f'/workspace/logs/calibration_data_{self.power_mode}.csv'

        self.subscription = self.create_subscription(
            DiagnosticArray, '/system_monitor', self.monitor_cb, 10)
        
        # Aboneliği yeni kanal ve mesaja göre güncelledik
        self.latency_sub = self.create_subscription(
            DecisionResult, '/decision/latency_detail', self.latency_cb, 10)

        self.current_data  = []
        self.latest_latency = None
        self.phase_start   = None
        self.started       = False

        self.timer = self.create_timer(0.1, self.run_calibration)

        os.makedirs('/workspace/logs', exist_ok=True)
        self.csv_file   = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp', 'power_mode', 'elapsed_sec',
            'cpu', 'gpu', 'ram_used', 'ram_total', 'power_mw', 'temp', 'latency_ms'])

        self.get_logger().info(f'CalibrationNode started. Power mode: {self.power_mode}')

    def monitor_cb(self, msg):
        data = {kv.key: (float(kv.value) if kv.value != 'N/A' else None)
                for s in msg.status for kv in s.values}
        data['timestamp'] = datetime.now().isoformat()
        data['latency_ms'] = self.latest_latency
        if self.started:
            self.current_data.append(data)

    def latency_cb(self, msg: DecisionResult):
        # Uçtan uca (End-to-End) gecikme hesabını burada yapıyoruz
        t_cap_ns  = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        t_dout_ns = msg.t_decision_out.sec * 1_000_000_000 + msg.t_decision_out.nanosec
        
        e2e_ms = (t_dout_ns - t_cap_ns) / 1_000_000.0
        
        # Son değeri güncelle
        self.latest_latency = round(e2e_ms, 2)

    def run_calibration(self):
        if not self.started:
            self.started     = True
            self.phase_start = self.get_clock().now()
            self.get_logger().info(
                f'[{self.power_mode}] Calibration started ({CALIB_SEC}s)...')
            return

        elapsed = (self.get_clock().now() - self.phase_start).nanoseconds / 1e9

        if self.current_data:
            d = self.current_data[-1]
            self.csv_writer.writerow([
                d.get('timestamp'), self.power_mode, round(elapsed, 1),
                d.get('cpu_percent'), d.get('gpu_percent'),
                d.get('ram_used_mb'), d.get('ram_total_mb'),
                d.get('power_mw'), d.get('temp_cpu_c'),
                d.get('latency_ms')])
            self.csv_file.flush()

        if self.current_data and len(self.current_data) % 60 == 0:
            self.get_logger().info(
                f'[{self.power_mode}] {elapsed:.0f}/{CALIB_SEC}s elapsed...')

        if elapsed >= CALIB_SEC:
            self.csv_file.close()
            self.get_logger().info(
                f'[{self.power_mode}] Calibration done. CSV: {self.csv_path}')
            raise SystemExit


def main(args=None):
    rclpy.init(args=args)
    node = CalibrationNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()