from setuptools import setup

package_name = "swarm_comm"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/swarm_comm.launch.py"]),
        ("share/" + package_name + "/config", ["config/swarm_comm.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Q250-V3-Opti Team",
    maintainer_email="user@example.com",
    description="Swarm communication: Fast-DDS real-time position broadcast + collision avoidance",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "position_broadcaster = swarm_comm.position_broadcaster:main",
            "collision_avoidance = swarm_comm.collision_avoidance:main",
            "swarm_coordinator = swarm_comm.swarm_coordinator:main",
        ],
    },
)
