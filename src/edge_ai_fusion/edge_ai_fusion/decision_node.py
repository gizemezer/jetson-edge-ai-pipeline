import rclpy
from rclpy.node import Node
from edge_ai_interfaces.msg import FusedData
from sensor_msgs.msg import Image
from std_msgs.msg import String
import numpy as np
import csv
import os
import cv2
from datetime import datetime

# Thermal thresholds (Float32 Celsius)
THERMAL_HOT       = 45.0  # 45C
THERMAL_DANGEROUS = 65.0  # 65C

# Depth thresholds (mm)
DEPTH_TOO_CLOSE = 50   # 5cm
DEPTH_MAX_VALID = 300  # 30cm

CSV_PATH = '/workspace/logs/decision_log.csv'

class DecisionNode(Node):
    def __init__(self):
        super().__init__('decision_node')

        self.fused_sub = self.create_subscription(
            FusedData, '/fused/output', self.decision_callback, 10)

        self.bitmap_pub = self.create_publisher(Image,  '/decision/thermal_bitmap', 10)
        self.alert_pub  = self.create_publisher(String, '/decision/alert',           10)

        # Track previous state per region_id
        self.previous_regions = {}

        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        self.csv_file   = open(CSV_PATH, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow([
            'timestamp', 'alert_type', 'region_id', 'detail',
            'region_pixels', 'closest_mm', 'center_x', 'center_y'
        ])

        self.get_logger().info('DecisionNode started.')

    def process_regions(self, mask, depth_array, alert_type_label, detail_prefix):
        """Detect connected regions, return list of region dicts."""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8)

        regions = []
        for i in range(1, num_labels):  # 0 = background
            region_mask   = (labels == i)
            region_pixels = int(np.sum(region_mask))

            if region_pixels < 5:  # ignore noise
                continue

            depths        = depth_array[region_mask]
            valid_mask    = (depths >= DEPTH_TOO_CLOSE) & (depths <= DEPTH_MAX_VALID)
            far_mask      = depths > DEPTH_MAX_VALID
            tooclose_mask = depths < DEPTH_TOO_CLOSE

            cx = int(centroids[i][0])
            cy = int(centroids[i][1])

            if valid_mask.any():
                closest_mm = int(np.min(depths[valid_mask]))
                detail     = f'{detail_prefix} in valid range | closest={closest_mm}mm | center=({cx},{cy})'
                alert_type = alert_type_label
            elif far_mask.all():
                closest_mm = -1
                detail     = f'{detail_prefix} BUT FAR | monitoring'
                alert_type = 'WARNING'
            elif tooclose_mask.all():
                closest_mm = -1
                detail     = f'{detail_prefix} | TOO CLOSE | sensor range invalid'
                alert_type = 'WARNING'
            else:
                closest_mm = int(np.min(depths[valid_mask])) if valid_mask.any() else -1
                detail     = f'{detail_prefix} | MIXED RANGE | closest={closest_mm}mm | center=({cx},{cy})'
                alert_type = alert_type_label

            regions.append({
                'alert_type'   : alert_type,
                'detail'       : detail,
                'region_pixels': region_pixels,
                'closest_mm'   : closest_mm,
                'center_x'     : cx,
                'center_y'     : cy,
            })

        return regions

    def should_write(self, region_id, region):
        """Write if region is new or state changed significantly."""
        prev = self.previous_regions.get(region_id)
        if prev is None:
            return True
        if region['alert_type'] != prev['alert_type']:
            return True
        if abs(region['closest_mm'] - prev['closest_mm']) > 10:
            return True
        if (abs(region['center_x'] - prev['center_x']) > 5 or
                abs(region['center_y'] - prev['center_y']) > 5):
            return True
        return False

    def decision_callback(self, fused_msg: FusedData):

        # --- 1. THERMAL ARRAY (float32, Celsius) ---
        thermal_array = np.frombuffer(fused_msg.thermal.data, dtype=np.float32)
        thermal_array = thermal_array.reshape((fused_msg.thermal.height, fused_msg.thermal.width))

        # --- 2. THERMAL BITMAP (0=NORMAL, 1=HOT, 2=DANGEROUS) ---
        bitmap = np.zeros_like(thermal_array, dtype=np.uint8)
        bitmap[thermal_array > THERMAL_HOT]       = 1
        bitmap[thermal_array > THERMAL_DANGEROUS] = 2

        # Bitmap visualization (green=NORMAL, orange=HOT, red=DANGEROUS)
        bitmap_color = np.zeros((bitmap.shape[0], bitmap.shape[1], 3), dtype=np.uint8)
        bitmap_color[bitmap == 0] = [0,   255, 0]    # green
        bitmap_color[bitmap == 1] = [0,   165, 255]  # orange
        bitmap_color[bitmap == 2] = [0,   0,   255]  # red

        bitmap_msg          = Image()
        bitmap_msg.header   = fused_msg.thermal.header
        bitmap_msg.height   = bitmap_color.shape[0]
        bitmap_msg.width    = bitmap_color.shape[1]
        bitmap_msg.encoding = 'bgr8'
        bitmap_msg.step     = bitmap_msg.width * 3
        bitmap_msg.data     = bitmap_color.tobytes()
        self.bitmap_pub.publish(bitmap_msg)

        # Save first frame as PNG for visual inspection
        if not hasattr(self, '_bitmap_saved'):
            scale_factor = 4
            bitmap_large = np.kron(
                bitmap_color,
                np.ones((scale_factor, scale_factor, 1), dtype=np.uint8)
            )
            cv2.imwrite('/workspace/logs/bitmap_test.png', bitmap_large)
            self.get_logger().info('Bitmap PNG saved: /workspace/logs/bitmap_test.png')
            self._bitmap_saved = True

        # --- 3. DEPTH ARRAY — Method A: downsample to thermal resolution (256x192) ---
        depth_raw   = np.frombuffer(fused_msg.depth.data, dtype=np.uint16)
        depth_raw   = depth_raw.reshape((fused_msg.depth.height, fused_msg.depth.width))
        depth_array = cv2.resize(
            depth_raw,
            (bitmap.shape[1], bitmap.shape[0]),  # (256, 192)
            interpolation=cv2.INTER_NEAREST
        )

        # --- 4. CONNECTED COMPONENTS per threat level ---
        dangerous_regions = self.process_regions(
            bitmap == 2, depth_array, 'CRITICAL', 'DANGEROUS region')

        hot_regions = self.process_regions(
            bitmap == 1, depth_array, 'WARNING', 'HOT region')

        all_regions = dangerous_regions + hot_regions

        # --- 5. PUBLISH ALERT ---
        if not all_regions:
            alert_msg      = String()
            alert_msg.data = 'SAFE'
            self.alert_pub.publish(alert_msg)
            self.get_logger().info('SAFE')
            self.previous_regions = {}
            return

        # Highest priority alert
        if any(r['alert_type'] == 'CRITICAL' for r in all_regions):
            top_alert = 'CRITICAL'
        else:
            top_alert = 'WARNING'

        alert_msg      = String()
        alert_msg.data = f'{top_alert} | {len(all_regions)} regions detected'
        self.alert_pub.publish(alert_msg)
        self.get_logger().info(alert_msg.data)

        # --- 6. CSV per region ---
        timestamp = datetime.now().isoformat()
        current_region_ids = set()

        for idx, region in enumerate(all_regions):
            region_id = f'{region["alert_type"]}_{region["center_x"]}_{region["center_y"]}_{region["region_pixels"]}'
            current_region_ids.add(region_id)

            if self.should_write(region_id, region):
                self.csv_writer.writerow([
                    timestamp,
                    region['alert_type'],
                    region_id,
                    region['detail'],
                    region['region_pixels'],
                    region['closest_mm'],
                    region['center_x'],
                    region['center_y']
                ])
                self.csv_file.flush()
                self.previous_regions[region_id] = region

        # Remove regions that no longer exist
        self.previous_regions = {
            k: v for k, v in self.previous_regions.items()
            if k in current_region_ids
        }

    def destroy_node(self):
        self.csv_file.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DecisionNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()