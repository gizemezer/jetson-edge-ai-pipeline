import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

class MockThermalPublisher(Node):
    def __init__(self):
        super().__init__('mock_thermal_publisher')

        # Thermal camera publisher
        # Frame rate: 8.7Hz — Teledyne FLIR Lepton Series Datasheet (2023)
        self.publisher = self.create_publisher(Image, '/thermal/image_raw', 10)
        self.timer = self.create_timer(1/9.0, self.publish_frame)

        self.get_logger().info('MockThermalPublisher started.')

    def publish_frame(self):
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'thermal_frame'

        # Resolution: 160x120 — Teledyne FLIR Lepton Series Datasheet (2023)
        msg.height = 120
        msg.width = 160

        # Encoding: 8-bit AGC output — Teledyne FLIR Lepton Series Datasheet (2023)
        msg.encoding = 'mono8'
        msg.step = msg.width

        # Simulated thermal data (mock — real sensor data in hardware phase)
        msg.data = (np.random.randint(0, 255, msg.height * msg.width, dtype=np.uint8)).tobytes()

        self.publisher.publish(msg)
        self.get_logger().info('Thermal frame published')

def main(args=None):
    rclpy.init(args=args)
    node = MockThermalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()