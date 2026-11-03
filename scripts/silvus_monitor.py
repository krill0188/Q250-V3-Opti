#!/usr/bin/env python3
# silvus_monitor.py - 실버스 Air Unit 링크 상태 모니터링 ROS2 노드
# 실행: python3 silvus_monitor.py --air-unit-ip 192.168.10.11

import argparse

import rclpy
import requests
from rclpy.node import Node
from std_msgs.msg import Float32, Int32


class SilvusMonitor(Node):
    def __init__(self, air_unit_ip="192.168.10.11"):
        super().__init__("silvus_monitor")
        self.air_unit_ip = air_unit_ip
        self.pub_rssi = self.create_publisher(Float32, "/silvus/rssi", 10)
        self.pub_snr = self.create_publisher(Float32, "/silvus/snr", 10)
        self.pub_throughput = self.create_publisher(Float32, "/silvus/throughput_mbps", 10)
        self.pub_hops = self.create_publisher(Int32, "/silvus/hops", 10)
        self.pub_neighbors = self.create_publisher(Int32, "/silvus/neighbor_count", 10)
        self.timer = self.create_timer(1.0, self.poll)
        self.get_logger().info(f"Silvus Monitor started for Air Unit: {air_unit_ip}")

    def poll(self):
        try:
            # 실버스 Air Unit 로컬 API (펌웨어 버전별 엔드포인트 확인 필요)
            # 일반적인 엔드포인트 예시:
            r = requests.get(f"http://{self.air_unit_ip}/api/v1/link/status", timeout=0.5)
            data = r.json()

            # 예상 JSON 구조 (펌웨어 버전에 따라 필드명 다를 수 있음)
            # {"rssi": -45, "snr": 25, "throughput_mbps": 85.3, "hops": 1, "neighbor_count": 3}

            self.pub_rssi.publish(Float32(data=float(data.get("rssi", -99))))
            self.pub_snr.publish(Float32(data=float(data.get("snr", 0))))
            self.pub_throughput.publish(Float32(data=float(data.get("throughput_mbps", 0))))
            self.pub_hops.publish(Int32(data=int(data.get("hops", 0))))
            self.pub_neighbors.publish(Int32(data=int(data.get("neighbor_count", 0))))

        except requests.exceptions.Timeout:
            self.get_logger().warn(f"Silvus API timeout for {self.air_unit_ip}")
        except requests.exceptions.ConnectionError:
            self.get_logger().warn(f"Silvus connection failed for {self.air_unit_ip}")
        except Exception as e:
            self.get_logger().warn(f"Silvus poll failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Silvus Air Unit Link Monitor")
    parser.add_argument("--air-unit-ip", default="192.168.10.11", help="Air Unit IP address")
    args = parser.parse_args()

    rclpy.init()
    node = SilvusMonitor(air_unit_ip=args.air_unit_ip)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
