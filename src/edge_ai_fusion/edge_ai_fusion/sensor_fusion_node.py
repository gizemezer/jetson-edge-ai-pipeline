import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from message_filters import ApproximateTimeSynchronizer, Subscriber
from edge_ai_interfaces.msg import FusedData

class SensorFusionNode(Node):
    def __init__(self):
        super().__init__('sensor_fusion_node')

        # Thermal camera subscriber (~25Hz)
        self.thermal_sub = Subscriber(self, Image, '/thermal/image_raw')

        # RealSense D435 depth subscriber (~30Hz)
        self.depth_sub = Subscriber(self, Image, '/camera/depth/image_rect_raw')

        # Synchronize both sensors with 120ms tolerance
        self.sync = ApproximateTimeSynchronizer(
            [self.thermal_sub, self.depth_sub],
            queue_size=10,
            slop=0.06
        )
        self.sync.registerCallback(self.process_fusion)

        # Single fused output publisher
        self.fused_pub = self.create_publisher(FusedData, '/fused/output', 10)

        self.get_logger().info('SensorFusionNode started.')

    def process_fusion(self, thermal_msg: Image, depth_msg: Image):
        fused = FusedData()
        fused.header.stamp = self.get_clock().now().to_msg()
        fused.header.frame_id = 'fused_frame'
        fused.thermal = thermal_msg
        fused.depth = depth_msg

        self.fused_pub.publish(fused)
        self.get_logger().info('Fused output published')

def main(args=None):
    rclpy.init(args=args)
    node = SensorFusionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()