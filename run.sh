#!/bin/bash

# Path to your Python script and its directory
CURRENT_FOLDER_PATH="/Users/advancedai/Desktop/UniIssue/comp3221/A1"
SCRIPT_PATH="COMP3221_A1_Routing.py"
CONFIG_DIR="spec"

time_to_print=60

# List of node identifiers and their corresponding port numbers
nodes_ports=("A 6000" "B 6001" "C 6002" "D 6003" "E 6004" "F 6005" "G 6006" "H 6007" "I 6008" "J 6009")
# nodes_ports=("A 6000" "B 6001" "C 6002")
# Iterate over the nodes_ports array
for np in "${nodes_ports[@]}"
do
    # Splitting node and port
    read node port <<< "$np"
    config_file="$CONFIG_DIR/${node}config.txt"

    # Using osascript to run the command in a new Terminal tab
    osascript <<EOF
tell application "Terminal"
    activate
    do script "cd $CURRENT_FOLDER_PATH && python3 $SCRIPT_PATH $node $port $config_file $time_to_print"
end tell
EOF

    # Add a slight delay to prevent any race conditions with opening terminals
    sleep 0.5
done
