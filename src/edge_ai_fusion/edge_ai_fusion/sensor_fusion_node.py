import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from message_filters import ApproximateTimeSynchronizer, Subscriber
from edge_ai_interfaces.msg import FusedData
from cv_bridge import CvBridge
import numpy as np
import cv2

class SensorFusionNode(Node):
    def __init__(self):
        super().__init__('sensor_fusion_node')
        self.bridge = CvBridge()
        
        # Thermal camera subscriber (~25Hz)
        self.thermal_sub = Subscriber(self, Image, '/thermal/image_raw16')
        
        # RealSense D435 depth subscriber (~30Hz)
        self.depth_sub = Subscriber(self, Image, '/camera/camera/depth/image_rect_raw')
        
        # Synchronize sensors with 100ms tolerance
        self.sync = ApproximateTimeSynchronizer(
            [self.thermal_sub, self.depth_sub],
            queue_size=10,
            slop=0.04
        )
        self.sync.registerCallback(self.process_fusion)

        # Single fused output publisher
        self.fused_pub = self.create_publisher(FusedData, '/fused/output_v2', 10)
        self.get_logger().info('SensorFusionNode started successfully.')

    def process_fusion(self, thermal_msg: Image, depth_msg: Image):
        try:
            # 1. Ham termal veriyi al ve Celsius'a çevir
            thermal_raw = self.bridge.imgmsg_to_cv2(thermal_msg, desired_encoding='mono16')
            thermal_celsius = (thermal_raw.astype(np.float32) / 64.0) - 273.15

            # 2. Celsius veriyi 32FC1 formatında hazırla
            thermal_processed_msg = self.bridge.cv2_to_imgmsg(thermal_celsius, encoding='32FC1')
            thermal_processed_msg.header = thermal_msg.header

            # 3. FusedData mesajını oluştur
            fused = FusedData()
            fused.header.stamp = self.get_clock().now().to_msg()
            fused.header.frame_id = 'fused_frame'

            fused.thermal = thermal_processed_msg
            fused.depth = depth_msg

            # 4. Yayınla
            self.fused_pub.publish(fused)
            
            # Log center temperature to verify calibration
            self.get_logger().info(f'Fused output published')

        except Exception as e:
            self.get_logger().error(f'Fusion Error: {str(e)}')

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
