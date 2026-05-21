import rclpy
from rclpy.node import Node
from diagnostic_msgs.msg import DiagnosticArray
from std_msgs.msg import Float32
import numpy as np
import csv
import os
from datetime import datetime

STABILITY_THRESHOLD = 0.08
MEASURE_SEC         = 60
N_RUNS              = 5
COOLDOWN_SEC        = 180
WINDOW_SEC          = 10


class PowerBenchmarkNode(Node):
    def __init__(self):
        super().__init__('power_benchmark_node')

        self.declare_parameter('power_mode', '7W')
        self.power_mode = self.get_parameter('power_mode').get_parameter_value().string_value

        self.csv_path = f'/workspace/logs/power_benchmark_{self.power_mode}.csv'

        self.subscription = self.create_subscription(
            DiagnosticArray, '/system_monitor', self.monitor_cb, 10)
        self.latency_sub = self.create_subscription(
            Float32, '/decision/latency', self.latency_cb, 10)

        self.current_data   = []
        self.latency_data   = []
        self.phase          = 'idle'
        self.run_idx        = 0

        os.makedirs('/workspace/logs', exist_ok=True)
        self.csv_file   = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp', 'power_mode', 'phase', 'run',
            'cpu', 'gpu', 'ram_used', 'ram_total', 'power_mw', 'temp', 'latency_ms'])

        self.timer       = self.create_timer(0.1, self.run_benchmark)
        self.started     = False
        self.phase_start = None
        self.get_logger().info(f'PowerBenchmarkNode started. Mode: {self.power_mode}')

    def monitor_cb(self, msg):
        data = {kv.key: (float(kv.value) if kv.value != 'N/A' else None)
                for s in msg.status for kv in s.values}
        data['timestamp'] = datetime.now().isoformat()
        data['latency_ms'] = self.latency_data[-1] if self.latency_data else None
        if self.phase != 'idle':
            self.current_data.append(data)

    def latency_cb(self, msg):
        self.latency_data.append(msg.data)

    def get_vals(self, data, key):
        return [d[key] for d in data if d.get(key) is not None]

    def is_stable(self, data):
        vals = self.get_vals(data, 'cpu_percent')
        if len(vals) < WINDOW_SEC * 2:
            return False
        r = np.mean(vals[-WINDOW_SEC:])
        p = np.mean(vals[-WINDOW_SEC*2:-WINDOW_SEC])
        return abs(r - p) / abs(p) < STABILITY_THRESHOLD if p != 0 else False

    def log_csv(self, phase, run=0):
        if not self.current_data:
            return
        d = self.current_data[-1]
        self.csv_writer.writerow([
            d.get('timestamp'), self.power_mode, phase, run,
            d.get('cpu_percent'), d.get('gpu_percent'),
            d.get('ram_used_mb'), d.get('ram_total_mb'),
            d.get('power_mw'), d.get('temp_cpu_c'),
            d.get('latency_ms')])
        self.csv_file.flush()

    def _next_phase(self, phase):
        self.phase        = phase
        self.current_data = []
        self.latency_data = []
        self.phase_start  = self.get_clock().now()

    def run_benchmark(self):
        if not self.started:
            self.started     = True
            self.phase_start = self.get_clock().now()
            self._next_phase('warmup')
            self.get_logger().info(f'[{self.power_mode}] Warmup started (threshold: {STABILITY_THRESHOLD*100:.0f}%)...')
            return

        elapsed = (self.get_clock().now() - self.phase_start).nanoseconds / 1e9

        if self.phase == 'warmup':
            self.log_csv('warmup')
            if self.is_stable(self.current_data):
                self.get_logger().info(f'[{self.power_mode}] Warmup done. {elapsed:.1f}s')
                self.run_idx = 0
                self._next_phase('measure')
                self.get_logger().info(f'[{self.power_mode}] Run 1/{N_RUNS} started...')

        elif self.phase == 'measure':
            self.log_csv('measure', self.run_idx + 1)
            if elapsed >= MEASURE_SEC:
                self.run_idx += 1
                self.get_logger().info(f'[{self.power_mode}] Run {self.run_idx}/{N_RUNS} done.')
                if self.run_idx < N_RUNS:
                    self._next_phase('measure')
                    self.get_logger().info(
                        f'[{self.power_mode}] Run {self.run_idx+1}/{N_RUNS} started...')
                else:
                    self._next_phase('cooldown')
                    self.get_logger().info(
                        f'[{self.power_mode}] Cool-down started ({COOLDOWN_SEC}s)...')

        elif self.phase == 'cooldown':
            self.log_csv('cooldown')
            if elapsed >= COOLDOWN_SEC:
                self.csv_file.close()
                self.get_logger().info(
                    f'[{self.power_mode}] Done. CSV: {self.csv_path}')
                self.get_logger().info(
                    'done all of this')
                raise SystemExit

    def destroy_node(self):
        if not self.csv_file.closed:
            self.csv_file.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PowerBenchmarkNode()
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()