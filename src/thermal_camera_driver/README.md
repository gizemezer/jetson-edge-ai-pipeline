# thermal-camera-ros2-driver
## Project Objective
This project develops a ROS2 Humble driver for the UNI-T UTi721M USB-C thermal camera, targeting deployment on a Jetson Orin Nano. The driver publishes thermal image streams as ROS2 topics and supports rosbag recording for data collection. The system is designed as the sensing layer for a UAV-based forest fire detection pipeline.
### Things to do 
- Recognizing and reading the thermal camera via the V4L2 interface in a Linux environment(ROS2_Humble).
- Publishing image data in sensor_msgs/Image format via the /thermal/image_raw topic.
- Providing support for compressed image streams with image_transport.
- Establishing a parametric and modular structure (YAML-based configuration)
- Providing real-time visualization with RViz2.
- Creating data recording and playback infrastructure with rosbag2.
- Running the system and completing the integration on the Jetson Orin Nano.
## Hardware and software
| Component | Details |
|---|---|
| OS | Ubuntu 22.04LTS |
| Target Platform | NVIDIA Jetson Orin Nano |
| Thermal Camera | UTi721M |
| ROS2 | Humble |
| Python | 3.10 |
| ROS2 Packages | cv-bridge, image-transport, sensor-msgs |
| System Tools | v4l-utils, python3-opencv |
## Development Notes
### ROS2-Humble
This project uses ROS2 Humble as the middleware layer. ROS2 handles communication between the camera driver node and other system components through its topic-based publish/subscribe architecture.  [documentation](https://docs.ros.org/en/humble/)

| Concept | Description |
|---|---|
| Node | An executable unit that performs a single function. E.g., camera reader node, image processor node|
| Topic | The communication channel between nodes. It operates using a publish/subscribe model |
| Package | In ROS2, it is the software distribution unit. It is compiled with colcon build |
| Workspace | The directory structure where packages are compiled and managed (src/, build/, install/)|
| Launch File | A configuration file that starts multiple nodes with a single command |
| Parameter | Key-value pairs that enable the configuration of nodes at runtime |
### Publisher-Subscriber structure
The driver uses ROS2's publish/subscribe pattern for data streaming. The thermal_camera_driver_node acts as a publisher, continuously capturing frames from the UTi721M and publishing them to /thermal/image_raw and /thermal/temperature_map topics. Any downstream node — such as a fire detection node — can subscribe to these topics without any direct dependency on the driver.[documentation](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Py-Publisher-And-Subscriber.html)

 thermal_camera_driver_node -> /thermal/image_raw -> fire_detector_node
 
QoS is set to SENSOR_DATA profile to prioritize low latency over guaranteed delivery, which is appropriate for real-time image streaming.
<img width="1568" height="535" alt="image" src="https://github.com/user-attachments/assets/3bef5d3f-490b-4d39-bc0d-f690e0648445" />

### sensor_msgs/Image
The driver publishes thermal frames using the sensor_msgs/Image message type. Each message carries a single frame captured from the UTi721M, encoded as bgr8, along with a timestamp and frame_id set to thermal_camera.
#### Structure of Message
(terminal code : `ros2 interface show sensor_msgs/msg/Image`) and [document](https://docs.ros.org/en/humble/p/std_msgs/)
```
std_msgs/Header header  Header timestamp should be acquisition time of image
	builtin_interfaces/Time stamp
		int32 sec
		uint32 nanosec
	string frame_id
                              Header frame_id should be optical frame of camera
                              origin of frame should be optical center of cameara
                              +x should point to the right in the image
                              +y should point down in the image
                              +z should point into to plane of the image
                              If the frame_id here and the frame_id of the CameraInfo
                              message associated with the image conflict
                              the behavior is undefined

uint32 height                 image height, that is, number of rows
uint32 width                  image width, that is, number of columns
string encoding        Encoding of pixels -- channel meaning, ordering, size
                       taken from the list of strings in include/sensor_msgs/image_encodings.hpp
uint8 is_bigendian     is this data bigendian?
uint32 step            Full row length in bytes
uint8[] data           actual matrix data, size is (step * rows)
```
### image_transport structure
Raw image data (sensor_msgs/Image) consumes significant bandwidth when transported over a network. The image_transport package provides an abstraction layer for transporting this data using various compression methods.[documentation](https://docs.ros.org/en/ros2_packages/humble/api/image_transport/)

```bash
ros2 topic list | grep thermal
```

Output:
```
/thermal/image_raw           : raw, uncompressed data
/thermal/image_raw/compressed  :JPEG/PNG compressed
/thermal/image_raw/theora      : video stream
```
### Record Data with Rosbag
During development, rosbag2 was used to record thermal data on both the laptop and Jetson Orin Nano. Recorded bags were used for calibration tests and to verify timestamp synchronization between /thermal/image_raw and /thermal/temperature_map topics.[documentation](https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html)
```bash
# Record all topics
ros2 bag record -a

# Record a specific topic
ros2 bag record /thermal/image_raw

# Play back a recording
ros2 bag play recording_folder/

# Inspect recording contents
ros2 bag info recording_folder/

# Play back at increased speed (2x)
ros2 bag play recording_folder/ --rate 2.0
```
#### Usage in the project
- Thermal image data recorded on the Jetson can be analyzed on the desktop
- The same data can be tested repeatedly during driver development
- Forest fire detection algorithms can be developed using bag files instead of live camera feeds
[referance]( https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools/Recording-And-Playing-Back-Data/Recording-And-Playing-Back-Data.html)

### Visualization with RViz2
RViz2 was used during development to visually verify that the driver was publishing correctly. The /thermal/image_raw topic was monitored in real time to confirm frame rate, encoding, and color output from the UTi721M.[referance](https://docs.ros.org/en/humble/Tutorials/Intermediate/RViz/RViz-User-Guide/RViz-User-Guide.html)
#### Usage in the project
- To visually verify that the camera driver is working correctly
- Visualization of the thermal image using a colormap
- Checking the images while Rosbag is playing.

### V4L2 and USB Camera Recognition in Linux
The UTi721M connects over USB-C and was tested for V4L2 compatibility on both the laptop and Jetson Orin Nano. Unlike standard UVC cameras, the UTi721M does not expose a standard /dev/videoX device, which required an alternative approach using OpenCV's direct capture instead of V4L2.
#### How to recognize a USB camera?
1. **UTi721M connected via USB-C**
2. **lsusb confirmed device recognition** 
3. **/dev/video0 checked via ls /dev/video*** 
4. **V4L2 compatibility tested with v4l2-ctl --list-devices** 
5. **OpenCV VideoCapture(0) used as fallback when V4L2 format was unsupported** 
#### UVC(USB Video Class)Protocol
The UTi721M was initially expected to be UVC-compatible, which would have allowed automatic recognition via the Linux kernel's uvcvideo module. However, testing showed that the camera uses a proprietary Android-oriented protocol, meaning standard UVC drivers did not apply.
The following commands were used during compatibility testing on the laptop before Jetson deployment:
#### Basic V4L2 Commands
```bash
# Install tools
sudo apt install v4l-utils
# List connected camera devices
ls /dev/video*
# Get detailed camera information
v4l2-ctl --device=/dev/video0 --info
# List supported formats
v4l2-ctl --device=/dev/video0 --list-formats-ext
# Display current settings
v4l2-ctl --device=/dev/video0 --all
# Capture a test frame
v4l2-ctl --device=/dev/video0 --stream-mmap --stream-count=1 --stream-to=test.raw
```
[referance](https://git.linuxtv.org/v4l-utils.git)
#### FPS
FPS stands for frames per second. In V4L2, it is controlled as follows:
```bash
# Display current FPS
v4l2-ctl --device=/dev/video0 --get-parm
# Set FPS
v4l2-ctl --device=/dev/video0 --set-parm=30
# List supported resolution and FPS combinations
v4l2-ctl --device=/dev/video0 --list-formats-ext
```
[general_referance]( https://www.kernel.org/doc/html/latest/userspace-api/media/v4l/v4l2.html
)
### OpenCV-ROS2 Usage(cv_bridge)
The driver uses cv_bridge to convert frames captured from the UTi721M via OpenCV into sensor_msgs/Image messages. Since the UTi721M outputs pseudocolor BGR frames, bgr8 encoding was used in the conversion.
Core conversion used in thermal_camera_driver_node.py:
```python
from cv_bridge import CvBridge
import cv2
bridge = CvBridge()
# OpenCV -> ROS2 message
ros_image = bridge.cv2_to_imgmsg(cv_frame, encoding="bgr8")
# ROS2 message -> OpenCV
cv_frame = bridge.imgmsg_to_cv2(ros_image, desired_encoding="bgr8")```

```bash
# Installation
sudo apt install ros-humble-cv-bridge
```
[referance](https://github.com/ros-perception/vision_opencv/tree/rolling/cv_bridge)

## Fake Thermal Publisher
The ROS2 package skeleton was reviewed and improvements were initiated. First, the package contents were listed using the `ls /ros2_ws/src/thermal-camera-ros2-driver/src/thermal_camera_driver/` command, which revealed that only the __init__.py file was present. Since a fake_thermal_publisher node was needed, a new file named `fake_thermal_publisher.py` was created. This node publishes fake thermal images over the `/thermal/image_raw` topic at 30 FPS using the `sensor_msgs/Image` message type. The image resolution was set to 256×192 pixels to match the UTi721M thermal camera. Each frame is generated in mono8 encoding with random pixel values ranging from 50 to 200, simulating warm and cold regions in the scene.
Next, the `fake_thermal_publisher entry` point was added to the entry_points section of `setup.py`, and the package was then compiled using colcon build:
```
cd ~/ros2_ws
colcon build --packages-select thermal_camera_driver
source install/setup.bash
```
To verify that frames were being published at 30 FPS, the following command was run:
`ros2 run thermal_camera_driver fake_thermal_publisher`
The output was as follows, confirming that frame publishing worked without any issues:
<img width="919" height="561" alt="Screenshot from 2026-04-17 17-05-46" src="https://github.com/user-attachments/assets/2d11c131-79f8-43f7-a6f8-4f8134a2ed41" />
To visualize the incoming data, RViz2 was launched in a separate terminal. In the RViz2 window, the Add -> By topic -> /thermal/image_raw -> Image steps were followed to open the image panel, and the frames from the fake node were successfully rendered on screen.
<img width="1220" height="901" alt="rviz" src="https://github.com/user-attachments/assets/f6165d9a-6eba-4493-86e7-36e7ad1a3ac1" />

## OpenCV – ROS2 Integration
Since OpenCV and ROS2 store image data in different formats, a converter is needed between them:
OpenCV -> numpy array — stores pixel data as a 2D/3D array
ROS2 -> sensor_msgs/Image — stores image data as a flat byte array with metadata
The data flow for the thermal camera driver is as follows:
1. Thermal Camera (USB)
2. Read frame with OpenCV    (numpy array)
3. Convert with cv_bridge   (sensor_msgs/Image)
4. Publish over ROS2 topic   (/thermal/image_raw)
To test this pipeline, a sample image was downloaded from the OpenCV GitHub repository:
`wget https://raw.githubusercontent.com/opencv/opencv/master/samples/data/butterfly.jpg -O ~/test_image.jpg`
A new node named `image_publisher.py` was then created to handle the OpenCV–cv_bridge integration. The `image_publisher` entry point was added to `setup.py` and the package was compiled using colcon build. An incorrect file path was initially provided, which caused a loading error. After correcting the path, the image was successfully published.
To visualize the output, RViz2 was launched in a separate terminal. By following Add -> By topic -> /camera/image_raw -> Image, the image was successfully rendered on screen. All changes were then pushed to GitHub.
<img width="952" height="901" alt="cv_bridge" src="https://github.com/user-attachments/assets/faecec08-a9bf-4c2f-b1a0-2372c8ea4e55" />
[referance](https://github.com/opencv/opencv)

## YAML-Based Configuration Setup
A YAML-based configuration file was created under the config/ directory. This allows the node to be configured without modifying the source code, making the system modular and parameter-driven. The following parameters were defined:

| Parameter | Description |
|---|---|
|frame_width|Horizontal resolution of the camera frame in pixels|
|frame_height|Vertical resolution of the camera frame in pixels|
|fps|Number of frames captured and published per second|
|topic_name|ROS2 topic name on which image data is published|
|frame_id|Coordinate frame identifier used in the image header|
|temp_min_threshold|Minimum temperature threshold for future fire detection logic|
|temp_max_threshold|Maximum temperature threshold for future fire detection logic|
[referance](https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Using-Parameters-In-A-Class-Python.html)
<img width="867" height="713" alt="image" src="https://github.com/user-attachments/assets/ce6bf1fa-ae90-4719-83b2-4b6baf969861" />
The fake_thermal_publisher node was then updated to read all parameters from this YAML file at startup, replacing previously hardcoded values. The package was rebuilt using colcon build and tested with the following command:
`ros2 run thermal_camera_driver fake_thermal_publisher --ros-args --params-file ~/ros2_ws/src/thermal-camera-ros2-driver/config/camera_params.yaml`
<img width="876" height="767" alt="Screenshot from 2026-04-18 21-00-46" src="https://github.com/user-attachments/assets/6ad1a3bb-2c3a-4ea2-bc4c-6971d5b76743" />
## Rosbag Visulization with RViz2
To test data recording, the fake_thermal_publisher node was launched and the /thermal/image_raw topic was recorded using rosbag2:
<img width="786" height="533" alt="Screenshot from 2026-04-18 21-03-38" src="https://github.com/user-attachments/assets/db593038-28e7-436f-9e93-00fb31275f40" />
After approximately 7 seconds, the recording was stopped. The bag file was then inspected using:
`ros2 bag info ~/ros2_ws/bags/rosbag2_2026_04_18-21_02_12`
<img width="876" height="808" alt="Screenshot from 2026-04-18 21-03-32" src="https://github.com/user-attachments/assets/2d80d1bc-f9ff-4abd-957b-64ac7e744d40" />
The recorded bag was then played back using:
`ros2 bag play ~/ros2_ws/bags/rosbag2_2026_04_18-21_02_12`
The playback was visualized in RViz2 by following Add -> By topic -> /thermal/image_raw -> Image, and the frames were successfully rendered on screen.
<img width="1920" height="1080" alt="Screenshot from 2026-04-18 21-04-43" src="https://github.com/user-attachments/assets/a38a64b1-43dd-4841-840f-6cf2705ce2c0" />
To prevent large bag files from being pushed to the repository, the .gitignore file was updated to exclude bags/ and *.db3 files.
