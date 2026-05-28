import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

class MockDepthPublisher(Node):
    def __init__(self):
        super().__init__('mock_depth_publisher')

        # Depth camera publisher
        # Frame rate: 30fps — Intel RealSense D435 Product Brief (Intel, 2023)
        self.publisher = self.create_publisher(Image, '/camera/camera/depth/image_rect_raw', 10)
        self.timer = self.create_timer(1/30.0, self.publish_frame)

        self.get_logger().info('MockDepthPublisher started.')

    def publish_frame(self):
        msg = Image()   
        t_capture = self.get_clock().now().to_msg()
        
        msg.header.stamp = t_capture
        msg.header.frame_id = 'depth_camera' 

        # Resolution: 1280x720 — Intel RealSense D435 Product Brief (Intel, 2023)
        msg.height = 720
        msg.width = 1280

        # Encoding: 16-bit depth values in millimeters
        msg.encoding = '16UC1'
        msg.step = msg.width * 2  # 2 bytes per pixel for 16-bit

        # Controlled test pattern
        data = np.full((720, 1280), 5000, dtype=np.uint16)  # all FAR

        data[0:360,   640:1280] = 5000   # top right  → FAR (>300mm)
        data[360:720, 0:640]    = 150    # bottom left → VALID (50-300mm)
        data[300:420, 480:800]  = 150    # center      → VALID (50-300mm)

        msg.data = data.tobytes()
        self.publisher.publish(msg)
        self.get_logger().info('Depth frame published')


        # Simulated depth data (mock — real sensor data in hardware phase)
        #msg.data = (np.random.randint(0, 65535, msg.height * msg.width, dtype=np.uint16)).tobytes()

      #  self.publisher.publish(msg)
       # self.get_logger().info('Depth frame published')

def main(args=None):
    rclpy.init(args=args)
    node = MockDepthPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()