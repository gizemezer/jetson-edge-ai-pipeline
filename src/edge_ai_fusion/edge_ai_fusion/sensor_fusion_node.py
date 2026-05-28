import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from message_filters import ApproximateTimeSynchronizer, Subscriber
from edge_ai_interfaces.msg import FusedData
from std_msgs.msg import Float32
from cv_bridge import CvBridge
import numpy as np
import csv
import os
from datetime import datetime

class SensorFusionNode(Node):
    def __init__(self):
        super().__init__('sensor_fusion_node')
        self.bridge    = CvBridge()
        self.frame_seq = 0

        # CSV Dosyası hazırlığı
        os.makedirs('/workspace/logs', exist_ok=True)
        self.csv_path = '/workspace/logs/fusion_sync_log.csv'
        self.csv_file = open(self.csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['timestamp', 'frame_seq', 'sync_error_ms'])

        self.thermal_sub = Subscriber(self, Image, '/thermal/image_raw16')
        self.depth_sub   = Subscriber(self, Image, '/camera/camera/depth/image_rect_raw')
        
        self.sync = ApproximateTimeSynchronizer(
            [self.thermal_sub, self.depth_sub], queue_size=10, slop=0.04)
        self.sync.registerCallback(self.process_fusion)
        
        self.fused_pub      = self.create_publisher(FusedData, '/fused/output_v2', 10)
        self.sync_error_pub = self.create_publisher(Float32, '/fusion/sync_error', 10)
        
        self.get_logger().info(f'SensorFusionNode started. Logging to {self.csv_path}')

    def process_fusion(self, thermal_msg: Image, depth_msg: Image):
        try:
           
            t_capture   = thermal_msg.header.stamp
            t_fusion_in = self.get_clock().now().to_msg()
            
            # Senkronizasyon hatası 
            t_therm_ns = thermal_msg.header.stamp.sec * 1e9 + thermal_msg.header.stamp.nanosec
            t_depth_ns = depth_msg.header.stamp.sec * 1e9 + depth_msg.header.stamp.nanosec
            sync_error_ms = abs(t_therm_ns - t_depth_ns) / 1e6

            #  LOG
            self.sync_error_pub.publish(Float32(data=float(sync_error_ms)))
            self.csv_writer.writerow([datetime.now().isoformat(), self.frame_seq, sync_error_ms])
            self.csv_file.flush()

           
            thermal_raw     = self.bridge.imgmsg_to_cv2(thermal_msg, desired_encoding='mono16')
            thermal_celsius = (thermal_raw.astype(float) / 64.0) - 273.15
            thermal_processed_msg        = self.bridge.cv2_to_imgmsg(
                                            thermal_celsius.astype('float32'),
                                            encoding='32FC1')
            thermal_processed_msg.header = thermal_msg.header

            self.frame_seq += 1
            fused                 = FusedData()
            fused.header.frame_id = 'fused_frame'
            fused.thermal         = thermal_processed_msg
            fused.depth           = depth_msg
            
            # Zamanları yerleştir
            fused.t_capture       = t_capture
            fused.t_fusion_in     = t_fusion_in
            fused.frame_seq       = self.frame_seq

            
            t_fusion_out       = self.get_clock().now().to_msg()
            fused.t_fusion_out = t_fusion_out
            
            
            fused.header.stamp = t_capture

            self.fused_pub.publish(fused)
            self.get_logger().info(f'Frame #{self.frame_seq} published. (Sync Error: {sync_error_ms:.2f} ms)')

        except Exception as e:
            self.get_logger().error(f'Fusion Error: {str(e)}')

    def destroy_node(self):
        self.csv_file.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = SensorFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()