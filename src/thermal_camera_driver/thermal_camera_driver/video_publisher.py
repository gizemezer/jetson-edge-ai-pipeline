import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

class VideoPublisher(Node):
    def __init__(self):
        super().__init__('video_publisher')

        self.declare_parameter('video_path', 'video.mp4')
        self.declare_parameter('topic_name', '/thermal/image_raw')
        self.declare_parameter('frame_id', 'thermal_camera')
        self.declare_parameter('loop', True)

        video_path = self.get_parameter('video_path').get_parameter_value().string_value
        topic_name = self.get_parameter('topic_name').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.loop = self.get_parameter('loop').get_parameter_value().bool_value

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.get_logger().error(f'Could not open video: {video_path}')
            return

        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 12.3
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.get_logger().info(f'Video: {video_path}')
        self.get_logger().info(f'Resolution: {width}x{height}, FPS: {fps:.1f}, Frames: {total_frames}')
        self.get_logger().info(f'Publishing to: {topic_name}')

        self.bridge = CvBridge()
        self.publisher = self.create_publisher(Image, topic_name, 10)
        self.timer = self.create_timer(1.0 / fps, self.publish_frame)

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            if self.loop:
                self.get_logger().info('Video ended, looping...')
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    return
            else:
                self.get_logger().info('Video ended.')
                self.timer.cancel()
                return

        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = VideoPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
