from setuptools import setup

package_name = "llm_mission_planner"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/mission_planner.launch.py"]),
        ("share/" + package_name + "/config", ["config/mission_planner.yaml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Q250-V3-Opti Team",
    maintainer_email="user@example.com",
    description="LLM-based high-level mission planner: converts natural language missions to waypoints/constraints JSON for PX4",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "mission_planner_node = llm_mission_planner.mission_planner_node:main",
            "mission_validator_node = llm_mission_planner.mission_validator_node:main",
        ],
    },
)
