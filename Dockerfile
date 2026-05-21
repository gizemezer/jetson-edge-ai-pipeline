FROM osrf/ros:humble-desktop

# Temel DErleme Araçlarının kurulumu
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    nano \
    && rm -rf /var/lib/apt/lists/*

# projede kullanılacak kütüphaneler
# ROS 2 Humble'daki bilinen uyarıları çözmek için setuptools sürümü sabitlendi
RUN pip3 install setuptools==58.2.0 opencv-python numpy

# Çalışma Alanı
WORKDIR /workspace

# Her terminal açılışında ROS 2 ortamının otomatik yüklenmesi .
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
RUN echo "source /workspace/install/setup.bash" >> ~/.bashrc

#Başlangıç komutu
CMD ["bash"]