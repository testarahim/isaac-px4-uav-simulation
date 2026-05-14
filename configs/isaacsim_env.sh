#!/usr/bin/env bash

# Isaac Sim root directory.
export ISAACSIM_PATH="${HOME}/isaacsim"

# Isaac Sim bundled Python executable.
export ISAACSIM_PYTHON="${ISAACSIM_PATH}/python.sh"

# Isaac Sim GUI launcher.
export ISAACSIM="${ISAACSIM_PATH}/isaac-sim.sh"

isaac_run() {
    if [ ! -x "$ISAACSIM_PYTHON" ]; then
        echo "Isaac Sim python.sh not found at: $ISAACSIM_PYTHON"
        return 1
    fi

    if [ ! -x "$ISAACSIM" ]; then
        echo "Isaac Sim launcher not found at: $ISAACSIM"
        return 1
    fi

    # Avoid conflicts with ROS environments that may already be sourced.
    unset ROS_VERSION ROS_PYTHON_VERSION ROS_DISTRO AMENT_PREFIX_PATH COLCON_PREFIX_PATH PYTHONPATH CMAKE_PREFIX_PATH

    local ros_path
    for ros_path in /opt/ros/humble /opt/ros/jazzy /opt/ros/iron; do
        export LD_LIBRARY_PATH="$(echo "$LD_LIBRARY_PATH" | tr ':' '\n' | grep -v "^${ros_path}" | paste -sd':' -)"
    done

    local ubuntu_version=""
    if [ -f /etc/os-release ]; then
        ubuntu_version="$(grep "^VERSION_ID=" /etc/os-release | cut -d'"' -f2)"
    fi

    if [ "$ubuntu_version" = "24.04" ]; then
        export ROS_DISTRO=jazzy
        export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
        export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${ISAACSIM_PATH}/exts/isaacsim.ros2.bridge/jazzy/lib"
        echo "Detected Ubuntu 24.04; using Isaac Sim internal ROS 2 Jazzy bridge."
    else
        export ROS_DISTRO=humble
        export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
        export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${ISAACSIM_PATH}/exts/isaacsim.ros2.bridge/humble/lib"
        echo "Detected Ubuntu ${ubuntu_version:-unknown}; using Isaac Sim internal ROS 2 Humble bridge."
    fi

    if [ "$#" -eq 0 ]; then
        echo "Launching Isaac Sim GUI."
        "$ISAACSIM"
    elif [[ "$1" == --* ]]; then
        echo "Launching Isaac Sim with options: $*"
        "$ISAACSIM" "$@"
    elif [ -f "$1" ]; then
        local script_path="$1"
        shift
        echo "Running Python script with Isaac Sim: $script_path"
        "$ISAACSIM_PYTHON" "$script_path" "$@"
    else
        echo "Unknown argument or file not found: $1"
        echo "Usage:"
        echo "  isaac_run"
        echo "  isaac_run my_script.py"
        echo "  isaac_run --headless ..."
        return 1
    fi
}
