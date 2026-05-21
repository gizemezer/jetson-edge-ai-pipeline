import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2


class ImagePublisher(Node):

    def __init__(self):
        super().__init__('image_publisher')

        # Publisher: publishes sensor_msgs/Image on /camera/image_raw topic
        self.publisher_ = self.create_publisher(Image, '/camera/image_raw', 10)

        # cv_bridge: converts between OpenCV images and ROS2 Image messages
        self.bridge = CvBridge()

        # Read image from disk using OpenCV
        self.image_path = '/home/erdem/test_image.jpg'
        self.cv_image = cv2.imread(self.image_path)

        if self.cv_image is None:
            self.get_logger().error(f'Failed to load image: {self.image_path}')
            return

        self.get_logger().info(f'Image loaded: {self.cv_image.shape}')

        # Timer: publish image every 1 second
        self.timer = self.create_timer(1.0, self.publish_image)

    def publish_image(self):
        # Convert OpenCV image (numpy array / bgr8) to ROS2 Image message
        ros_image = self.bridge.cv2_to_imgmsg(self.cv_image, encoding='bgr8')

        # Set header
        ros_image.header.stamp = self.get_clock().now().to_msg()
        ros_image.header.frame_id = 'camera'

        self.publisher_.publish(ros_image)
        self.get_logger().info('Image published!')


def main(args=None):
    rclpy.init(args=args)
    node = ImagePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
