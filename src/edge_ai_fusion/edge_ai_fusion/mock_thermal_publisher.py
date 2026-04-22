import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

class MockThermalPublisher(Node):
    def __init__(self):
        super().__init__('mock_thermal_publisher')

        # Thermal camera publisher
        # Frame rate: 25Hz - UNI-T UTi721M
        self.publisher = self.create_publisher(Image, '/thermal/image_raw', 10)
        self.timer = self.create_timer(1/25.0, self.publish_frame)

        self.get_logger().info('MockThermalPublisher started.')

    def publish_frame(self):
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'thermal_frame'

        # Resolution: 256x192 - UNI-T
        msg.height = 192
        msg.width = 256

        # Encoding: 32FC1 (32-bit Float)
        msg.encoding = '32FC1'
        msg.step = msg.width * 4

        # Base: DANGEROUS (red) 
        data = np.full((192, 256), 70.0, dtype=np.float32)

        # Inner frame: HOT (orange)
        data[20:172, 20:236] = 50.0

        # Center vertical strips
        data[40:152, 55:75]   = 30.0   # green
        data[40:152, 75:100]  = 70.0   # red
        data[40:152, 100:115] = 50.0   # orange
        data[40:152, 115:140] = 70.0   # red
        data[40:152, 140:155] = 50.0   # orange
        data[40:152, 155:180] = 70.0   # red
        data[40:152, 180:200] = 30.0   # green

        msg.data = data.tobytes()
        self.publisher.publish(msg)
        self.get_logger().info('Thermal frame published')



"""         # Controlled test pattern ilk test denemesi
        data = np.full((192, 256), 30.0, dtype=np.float32)  # all NORMAL

        data[0:96,   128:256] = 50.0   # top right  → HOT (45-65C)
        data[96:192, 0:128]   = 70.0   # bottom left → DANGEROUS (>65C)
        data[80:112, 96:160]  = 70.0   # center      → DANGEROUS (>65C)

        msg.data = data.tobytes()
        self.publisher.publish(msg)
        self.get_logger().info('Thermal frame published')
 """

        # Simulated thermal data (mock — real sensor data in hardware phase) ilk deneme
      #  msg.data = (np.random.uniform(0.0, 100.0, msg.height * msg.width).astype(np.float32)).tobytes()

       # self.publisher.publish(msg)
       # self.get_logger().info('Thermal frame published')

def main(args=None):
    rclpy.init(args=args)
    node = MockThermalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()