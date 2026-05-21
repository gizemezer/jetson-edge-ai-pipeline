import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class ThermalCameraDriver(Node):
    def __init__(self):
        super().__init__('thermal_camera_driver')
        
        # Dinamik parametre tanımı (Varsayılan olarak video6)
        self.declare_parameter('device', '/dev/video6')
        device_path = self.get_parameter('device').get_parameter_value().string_value
        
        self.publisher_ = self.create_publisher(Image, '/thermal/image_raw', 10)
        self.raw_publisher = self.create_publisher(Image, '/thermal/image_raw16', 10)
        self.bridge = CvBridge()
        
        # Sabit video0 yerine dinamik port ataması
        self.cap = cv2.VideoCapture(device_path, cv2.CAP_V4L2)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', 'V'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 256)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 384)
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        
        self.timer = self.create_timer(0.04, self.publish_frame)
        self.get_logger().info(f'Thermal Camera Driver started on {device_path}!')

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().error('Failed to capture frame!')
            return
        
        # Üst yarı: Renkli görsel verinin Y kanalı (Gri tonlama)
        top_y = frame[0:192, :, 0]
        top_bgr = cv2.cvtColor(top_y, cv2.COLOR_GRAY2BGR)
        
        # Alt yarı: Ham sıcaklık verisi ve bellek hizalaması (ascontiguousarray)
        bottom_half = frame[192:384, :, :]
        raw16 = np.ascontiguousarray(bottom_half).view(np.uint16).reshape(192, 256)
        
        stamp = self.get_clock().now().to_msg()
        
        visual_msg = self.bridge.cv2_to_imgmsg(top_bgr, encoding='bgr8')
        visual_msg.header.stamp = stamp
        visual_msg.header.frame_id = 'thermal_camera'
        self.publisher_.publish(visual_msg)
        
        raw16_msg = self.bridge.cv2_to_imgmsg(raw16, encoding='mono16')
        raw16_msg.header.stamp = stamp
        raw16_msg.header.frame_id = 'thermal_camera'
        self.raw_publisher.publish(raw16_msg)

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = ThermalCameraDriver()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()


