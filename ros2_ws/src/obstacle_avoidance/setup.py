from setuptools import setup

package_name = "obstacle_avoidance"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/obstacle_avoidance.launch.py"]),
        (
            "share/" + package_name + "/config",
            ["config/teb_params.yaml", "costmap_params.yaml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Q250-V3-Opti Team",
    maintainer_email="user@example.com",
    description="Obstacle avoidance pipeline for Q250-V3-Opti",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "obstacle_distance_pub = obstacle_avoidance.obstacle_distance_pub:main",
            "safety_watchdog = obstacle_avoidance.safety_watchdog:main",
        ],
    },
)
