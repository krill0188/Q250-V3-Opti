<launch>
    <arg name="air_unit_ip" default="192.168.10.11" description="Silvus Air Unit IP address"/>
    
    <node pkg="your_pkg" exec="silvus_monitor" name="silvus_monitor" output="screen">
        <param name="air_unit_ip" value="$(var air_unit_ip)"/>
    </node>
</launch>
