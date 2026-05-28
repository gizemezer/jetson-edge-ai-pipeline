import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np

class MockThermalPublisher(Node):
    def __init__(self):
        super().__init__('mock_thermal_publisher')

        # Thermal camera publisher
        # Frame rate: 25Hz - UNI-T UTi721M
        self.publisher = self.create_publisher(Image, '/thermal/image_raw16', 10)
        self.timer = self.create_timer(1/25.0, self.publish_frame)

        self.get_logger().info('MockThermalPublisher started.')

    def publish_frame(self):
        msg = Image()
        t_capture = self.get_clock().now().to_msg()
        
        msg.header.stamp = t_capture
        msg.header.frame_id = 'thermal_camera'
        # Resolution: 256x192 - UNI-T
        msg.height = 192
        msg.width = 256

        # Normal termalin yaydığı formata (mono16) ayarlandı
        msg.encoding = 'mono16'
        msg.step = msg.width * 2  # mono16 olduğu için genişlik * 2 byte
    

        # Base: DANGEROUS (red) -> 70°C
        data = np.full((192, 256), 21961, dtype=np.uint16)

        # Inner frame: HOT (orange) -> 50°C
        data[20:172, 20:236] = 20681

        # Center vertical strips
        data[40:152, 55:75]   = 19401  # green (30°C)
        data[40:152, 75:100]  = 21961  # red (70°C)
        data[40:152, 100:115] = 20681  # orange (50°C)
        data[40:152, 115:140] = 21961  # red (70°C)
        data[40:152, 140:155] = 20681  # orange (50°C)
        data[40:152, 155:180] = 21961  # red (70°C)
        data[40:152, 180:200] = 19401  # green (30°C)

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