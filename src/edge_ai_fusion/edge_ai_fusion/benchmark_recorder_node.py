import rclpy
from rclpy.node import Node
import csv
import os
from edge_ai_interfaces.msg import DecisionResult

class BenchmarkRecorder(Node):
    def __init__(self):
        super().__init__('benchmark_recorder')
        
        # Log dizinini hazırla
        self.log_dir = '/workspace/logs'
        os.makedirs(self.log_dir, exist_ok=True)
        self.csv_path = f'{self.log_dir}/benchmark.csv'
        
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.writer = csv.writer(self.csv_file)
        # CSV Başlıkları: Latency kırılımı (ms)
        self.writer.writerow(['timestamp', 'acq', 'proc', 'trans', 'dec', 'e2e'])

        # Subscriber
        self.create_subscription(DecisionResult, '/decision/latency_detail', self.lat_cb, 10)
        
        # Zamanlayıcılar
        self.start_time = self.get_clock().now()
        self.duration = 600 # 600 saniye (10 dk)
        self.timer = self.create_timer(1.0, self.check_time)
        
        self.get_logger().info(f'Benchmark Recorder active. {self.duration}')

    def lat_cb(self, msg):
        # t_capture referans alarak farkları hesapla (t_capture = msg.header.stamp)
        t_cap = rclpy.time.Time.from_msg(msg.header.stamp)
        t_fus_in = rclpy.time.Time.from_msg(msg.t_fusion_in)
        t_fus_out = rclpy.time.Time.from_msg(msg.t_fusion_out)
        t_dec_in = rclpy.time.Time.from_msg(msg.t_decision_in)
        t_dec_out = rclpy.time.Time.from_msg(msg.t_decision_out)

        # Farkları ms'ye çevir
        self.writer.writerow([
            self.get_clock().now().nanoseconds,
            (t_fus_in - t_cap).nanoseconds / 1e6,    # Acquisition
            (t_fus_out - t_fus_in).nanoseconds / 1e6, # Fusion Processing
            (t_dec_in - t_fus_out).nanoseconds / 1e6, # Transport/Wait
            (t_dec_out - t_dec_in).nanoseconds / 1e6, # Decision Making
            (t_dec_out - t_cap).nanoseconds / 1e6     # End-to-End
        ])
        self.csv_file.flush()

    def check_time(self):
        elapsed = (self.get_clock().now() - self.start_time).nanoseconds / 1e9
        if elapsed >= self.duration:
            self.get_logger().info('Done.')
            self.csv_file.close()
            rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    node = BenchmarkRecorder()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()

if __name__ == '__main__':
    main()