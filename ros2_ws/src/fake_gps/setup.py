from setuptools import setup

package_name = "fake_gps"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/fake_gps.launch.py"]),
        ("share/" + package_name + "/config", ["config/fake_gps.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Q250-V3-Opti Team",
    maintainer_email="user@example.com",
    description="Fake GPS publisher: converts VIO local pose to GPS_INPUT MAVLink for PX4 global position",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "fake_gps_node = fake_gps.fake_gps_node:main",
        ],
    },
)
