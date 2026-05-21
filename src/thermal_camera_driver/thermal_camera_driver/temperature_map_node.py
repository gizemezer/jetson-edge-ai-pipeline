import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import numpy as np

class TemperatureMapNode(Node):
	def __init__(self):
		super().__init__('temperature_map_node')
		self.declare_parameter('input_topic', '/thermal/image_raw16')
		self.declare_parameter('output_topic', '/thermal/temperature_map')
		input_topic = self.get_parameter('input_topic').get_parameter_value().string_value
		output_topic = self.get_parameter('output_topic').get_parameter_value().string_value
		self.bridge = CvBridge()
		self.subscription = self.create_subscription(Image, input_topic, self.image_callback, 10)
		self.publisher = self.create_publisher(Image, output_topic, 10)
		self.visual_publisher = self.create_publisher(Image, output_topic + '/visual', 10)
		self.get_logger().info('Temperature Map Node started! T = raw16/64 - 273.15')

	def add_colorbar(self, frame, t_min, t_max):
		h = frame.shape[0]
		bar_w = 15
		label_w = 40
		bar = np.zeros((h, bar_w, 3), dtype=np.uint8)
		for i in range(h):
			val = int(255 * (1.0 - i / h))
			color = cv2.applyColorMap(np.array([[val]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0]
			bar[i, :] = color
		labels = np.zeros((h, label_w, 3), dtype=np.uint8)
		for i in range(6):
			y = int(10 +  i * (h-20)/5)
			temp = t_max - i * (t_max - t_min) / 5
			cv2.putText(labels, f'{temp:.1f}C', (2, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)
		return np.hstack([frame, bar, labels])

	def image_callback(self, msg):
		raw16 = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono16')
		temp_map = raw16.astype(np.float32) / 64.0 - 273.15
		actual_min = float(np.min(temp_map))
		actual_max = float(np.max(temp_map))
		temp_normalized = cv2.normalize(temp_map, None, 0, 255, cv2.NORM_MINMAX)
		temp_uint8 = temp_normalized.astype(np.uint8)
		temp_colormap = cv2.applyColorMap(temp_uint8, cv2.COLORMAP_JET)
		temp_colormap = self.add_colorbar(temp_colormap, actual_min, actual_max)
		temp_colormap = cv2.resize(temp_colormap, (512, 384))
		out_msg = self.bridge.cv2_to_imgmsg(temp_map, encoding='32FC1')
		out_msg.header = msg.header
		self.publisher.publish(out_msg)
		visual_msg = self.bridge.cv2_to_imgmsg(temp_colormap, encoding='bgr8')
		visual_msg.header = msg.header
		self.visual_publisher.publish(visual_msg)

def main(args=None):
	rclpy.init(args=args)
	node = TemperatureMapNode()
	rclpy.spin(node)
	node.destroy_node()
	rclpy.shutdown()

if __name__ == '__main__':
	main()
