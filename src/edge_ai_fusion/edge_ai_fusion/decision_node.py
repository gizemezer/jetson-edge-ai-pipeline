import rclpy
from rclpy.node import Node
from edge_ai_interfaces.msg import FusedData
from std_msgs.msg import String
import numpy as np

class DecisionNode(Node):
    def __init__(self):
        super().__init__('decision_node')

        # Subscribe to fused output from sensor_fusion_node
        self.fused_sub = self.create_subscription(
            FusedData, '/fused/output', self.decision_callback, 10)

        # Publish decision result
        self.decision_pub = self.create_publisher(String, '/decision/output', 10)

        self.get_logger().info('DecisionNode started.')

    def decision_callback(self, fused_msg: FusedData):
        # Extract thermal data
        thermal_array = np.frombuffer(fused_msg.thermal.data, dtype=np.uint8)
        thermal_array = thermal_array.reshape((fused_msg.thermal.height, fused_msg.thermal.width))

        # Extract depth data
        depth_array = np.frombuffer(fused_msg.depth.data, dtype=np.uint16)
        depth_array = depth_array.reshape((fused_msg.depth.height, fused_msg.depth.width))

        # Mock threshold-based decision will cahnged 
        avg_thermal = int(np.mean(thermal_array))
        avg_depth = int(np.mean(depth_array))

        if avg_thermal > 200 and avg_depth < 30000:
            decision = 'warn'
        else:
            decision = 'safe'

        self.get_logger().info(
            f'Decision: {decision} | avg_thermal: {avg_thermal} | avg_depth: {avg_depth}mm')


def main(args=None):
    rclpy.init(args=args)
    node = DecisionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()