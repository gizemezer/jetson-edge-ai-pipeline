import rclpy
from rclpy.node import Node
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from diagnostic_msgs.msg import DiagnosticArray
from sensor_msgs.msg import Image
from std_msgs.msg import String
from rclpy.qos import QoSProfile, ReliabilityPolicy
from edge_ai_interfaces.msg import FusedData
import time

# ANSI colors for terminal
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
RESET  = '\033[0m'

class DiagnosticsNode(Node):
    def __init__(self):
        super().__init__('diagnostics_node')

        # ── Publishers ──
        self.diag_pub = self.create_publisher(
            DiagnosticArray, '/diagnostics', 10)
        # ── System monitor subscriber ──
        self.system_data = {}
        self.create_subscription(
            DiagnosticArray, '/system_monitor',
            self.system_cb, 10)

        # ── Pipeline topic subscribers ──
        self.topic_stamps = {
            '/fused/output_v2'                  : None,
            '/decision/alert'                : None,
            '/thermal/image_raw16'             : None,
            '/camera/camera/depth/image_rect_raw'   : None,
        }
        self.topic_hz = {k: 0.0 for k in self.topic_stamps}
        self.topic_counts = {k: 0 for k in self.topic_stamps}
        self.hz_window_start = time.time()

        self.create_subscription(
            FusedData, '/fused/output_v2',
            lambda m: self._topic_cb('/fused/output_v2'), 10)
        self.create_subscription(
            String, '/decision/alert',
            lambda m: self._topic_cb('/decision/alert'), 10)
        self.create_subscription(
            Image, '/thermal/image_raw16',
            lambda m: self._topic_cb('/thermal/image_raw16'), 10)
        self.create_subscription(
            Image, '/camera/camera/depth/image_rect_raw',
            lambda m: self._topic_cb('/camera/camera/depth/image_rect_raw'), 10)

        # ── Timer: publish diagnostics every second ──
        self.create_timer(1.0, self.publish_diagnostics)
        self.get_logger().info('DiagnosticsNode started.')

    def system_cb(self, msg):
        for status in msg.status:
            for kv in status.values:
                self.system_data[kv.key] = kv.value

    def _topic_cb(self, topic):
        self.topic_stamps[topic] = time.time()
        self.topic_counts[topic] += 1

    def _compute_hz(self):
        now     = time.time()
        elapsed = now - self.hz_window_start
        if elapsed >= 1.0:
            for topic in self.topic_hz:
                self.topic_hz[topic] = round(
                    self.topic_counts[topic] / elapsed, 2)
                self.topic_counts[topic] = 0
            self.hz_window_start = now

    def _make_status(self, name, kvs, level=DiagnosticStatus.OK, message=''):
        status          = DiagnosticStatus()
        status.name     = name
        status.level    = level
        status.message  = message
        status.hardware_id = 'jetson_orin_nano'
        status.values   = [KeyValue(key=k, value=str(v)) for k, v in kvs]
        return status

    def publish_diagnostics(self):
        self._compute_hz()

        # ── Status 1: System Resources ──
        sys_kvs = [
            ('cpu_percent',  self.system_data.get('cpu_percent',  'N/A')),
            ('gpu_percent',  self.system_data.get('gpu_percent',  'N/A')),
            ('ram_used_mb',  self.system_data.get('ram_used_mb',  'N/A')),
            ('ram_total_mb', self.system_data.get('ram_total_mb', 'N/A')),
            ('power_mw',     self.system_data.get('power_mw',     'N/A')),
            ('temp_cpu_c',   self.system_data.get('temp_cpu_c',   'N/A')),
        ]
        sys_level   = DiagnosticStatus.OK
        sys_message = 'System resources nominal'
        if any(v == 'N/A' for _, v in sys_kvs):
            sys_level   = DiagnosticStatus.WARN
            sys_message = 'tegrastats not available (non-Jetson hardware)'

        sys_status = self._make_status(
            'System Resources', sys_kvs, sys_level, sys_message)

        # ── Status 2: Pipeline Health ──
        now = time.time()
        pipe_kvs = []
        pipe_level   = DiagnosticStatus.OK
        pipe_message = 'Pipeline nominal'

        for topic, hz in self.topic_hz.items():
            last = self.topic_stamps[topic]
            age  = round(now - last, 2) if last else -1
            pipe_kvs.append((f'{topic}/hz',  str(hz)))
            pipe_kvs.append((f'{topic}/last_seen_sec_ago', str(age)))

            if last is None or (now - last) > 2.0:
                pipe_level   = DiagnosticStatus.WARN
                pipe_message = f'{topic} not receiving data'

        pipe_status = self._make_status(
            'Pipeline Health', pipe_kvs, pipe_level, pipe_message)

        # ── Publish ──
        msg             = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.status      = [sys_status, pipe_status]
        self.diag_pub.publish(msg)

        # ── Terminal output ──
        self._print_terminal(sys_kvs, sys_level,
                             pipe_kvs, pipe_level)

    def _print_terminal(self, sys_kvs, sys_level, pipe_kvs, pipe_level):
        def level_str(level):
            if level == DiagnosticStatus.OK:
                return f'{GREEN}✅ OK{RESET}'
            return f'{YELLOW}⚠️  WARN{RESET}'

        print('\n' + '─' * 50)
        print(f'  SYSTEM RESOURCES  {level_str(sys_level)}')
        print('─' * 50)
        for k, v in sys_kvs:
            print(f'  {k:<20} {v}')

        print('─' * 50)
        print(f'  PIPELINE HEALTH   {level_str(pipe_level)}')
        print('─' * 50)
        for k, v in pipe_kvs:
            print(f'  {k:<45} {v}')
        print('─' * 50)


def main(args=None):
    rclpy.init(args=args)
    node = DiagnosticsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()