import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from message_filters import ApproximateTimeSynchronizer, Subscriber
from edge_ai_interfaces.msg import FusedData
from cv_bridge import CvBridge
import numpy as np

class SensorFusionNode(Node):
    def __init__(self):
        super().__init__('sensor_fusion_node')
        self.bridge    = CvBridge()
        self.frame_seq = 0

        self.thermal_sub = Subscriber(self, Image, '/thermal/image_raw16')
        self.depth_sub   = Subscriber(self, Image, '/camera/camera/depth/image_rect_raw')
        self.sync = ApproximateTimeSynchronizer(
            [self.thermal_sub, self.depth_sub],
            queue_size=10,
            slop=0.04)
        self.sync.registerCallback(self.process_fusion)
        self.fused_pub = self.create_publisher(FusedData, '/fused/output_v2', 10)
        self.get_logger().info('SensorFusionNode started.')

    def process_fusion(self, thermal_msg: Image, depth_msg: Image):
        try:
            t_capture   = thermal_msg.header.stamp
            t_fusion_in = self.get_clock().now().to_msg()

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
            fused.t_capture       = t_capture
            fused.t_fusion_in     = t_fusion_in
            fused.frame_seq       = self.frame_seq

            t_fusion_out       = self.get_clock().now().to_msg()
            fused.t_fusion_out = t_fusion_out
            fused.header.stamp = t_fusion_out

            self.fused_pub.publish(fused)
            self.get_logger().info(f'Frame #{self.frame_seq} published.')

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