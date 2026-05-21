import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import numpy as np


class FakeThermalPublisher(Node):

    def __init__(self):
        super().__init__('fake_thermal_publisher')

        # Declare parameters with default values 
        self.declare_parameter('frame_width', 256)
        self.declare_parameter('frame_height', 192)
        self.declare_parameter('fps', 30.0)
        self.declare_parameter('topic_name', '/thermal/image_raw')
        self.declare_parameter('frame_id', 'thermal_camera')
        self.declare_parameter('encoding', 'mono8')
        self.declare_parameter('temp_min_threshold', 50.0)
        self.declare_parameter('temp_max_threshold', 200.0)

        # Read parameters
        self.width = self.get_parameter('frame_width').value
        self.height = self.get_parameter('frame_height').value
        self.fps = self.get_parameter('fps').value
        self.topic_name = self.get_parameter('topic_name').value
        self.frame_id = self.get_parameter('frame_id').value
        self.encoding = self.get_parameter('encoding').value
        self.temp_min = self.get_parameter('temp_min_threshold').value
        self.temp_max = self.get_parameter('temp_max_threshold').value

        # Publisher: topic name and encoding read from parameters
        self.publisher_ = self.create_publisher(Image, self.topic_name, 10)

        # Timer: period calculated from fps parameter
        timer_period = 1.0 / self.fps
        self.timer = self.create_timer(timer_period, self.publish_frame)

        self.frame_count = 0
        self.get_logger().info(f'Fake Thermal Publisher started!')
        self.get_logger().info(f'Resolution: {self.width}x{self.height} @ {self.fps} FPS')
        self.get_logger().info(f'Topic: {self.topic_name} | Frame ID: {self.frame_id}')
        self.get_logger().info(f'Temperature thresholds: {self.temp_min} - {self.temp_max}')

    def publish_frame(self):
        msg = Image()

        # Header: timestamp and coordinate frame name from parameters
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id

        # Image dimensions from parameters
        msg.height = self.height
        msg.width = self.width
        msg.encoding = self.encoding
        msg.is_bigendian = False

        # Step: number of bytes per row (width x bytes_per_pixel)
        msg.step = self.width

        # Generate fake thermal frame with random pixel values
        # Values range simulates thermal intensity (temp_min to temp_max)
        frame = np.random.randint(
            int(self.temp_min),
            int(self.temp_max),
            (self.height, self.width),
            dtype=np.uint8
        )

        # Flatten 2D array to 1D list as required by sensor_msgs/Image
        msg.data = frame.flatten().tolist()

        self.publisher_.publish(msg)
        self.get_logger().info(f'Published frame #{self.frame_count} ({self.width}x{self.height})')
        self.frame_count += 1


def main(args=None):
    rclpy.init(args=args)
    node = FakeThermalPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
