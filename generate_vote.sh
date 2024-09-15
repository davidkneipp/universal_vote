#!/bin/bash

### PLEASE READ THROUGH AND TAKE TIME TO UNDERSTAND THIS SCRIPT
### Don't trust a random internet script that uses your private ssh keys.

# Server URL - Change this to your actual server URL
SERVER_URL="http://localhost:5000"

# Default SSH key path
DEFAULT_SSH_KEY="~/.ssh/id_rsa"

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored text
print_color() {
    printf "${!1}%s${NC}\n" "$2"
}

# Function to fetch vote options
fetch_vote_options() {
    options=$(curl -s "${SERVER_URL}/vote_options")
    if [ $? -ne 0 ]; then
        print_color "RED" "Error: Unable to fetch vote options. Please check your internet connection and try again."
        exit 1
    fi
    echo $options | jq -r '.[]'
}

# Function to expand tilde in path
expand_tilde() {
    if [[ $1 == "~"* ]]; then
        echo "${1/#\~/$HOME}"
    else
        echo "$1"
    fi
}

# Check for required dependencies
for cmd in curl jq ssh-keygen openssl; do
    if ! command -v $cmd &> /dev/null; then
        print_color "RED" "Error: $cmd is required but not installed. Please install it and try again."
        exit 1
    fi
done

# Prompt for SSH key path
print_color "YELLOW" "Please enter the path to your SSH private key (press Enter for default: $DEFAULT_SSH_KEY):"
read ssh_key_path
ssh_key_path=${ssh_key_path:-$DEFAULT_SSH_KEY}

# Expand tilde in the path
expanded_path=$(expand_tilde "$ssh_key_path")
print_color "YELLOW" "Using SSH key at: $expanded_path"
ssh_key_path=$expanded_path

if [ ! -f "$ssh_key_path" ]; then
    print_color "RED" "Error: SSH key not found at $ssh_key_path"
    exit 1
fi

# Determine key type
key_info=$(ssh-keygen -l -f "$ssh_key_path" 2>&1)
if [ $? -ne 0 ]; then
    print_color "RED" "Error reading key information: $key_info"
    exit 1
fi
print_color "YELLOW" "Key info: $key_info"

if [[ $key_info == *"ED25519"* ]]; then
    key_type="ed25519"
elif [[ $key_info == *"RSA"* ]]; then
    key_type="rsa"
else
    print_color "RED" "Error: Unsupported key type. Please use an Ed25519 or RSA key."
    print_color "RED" "Key info: $key_info"
    exit 1
fi

print_color "GREEN" "Detected key type: $key_type"

# Fetch and display vote options
print_color "YELLOW" "Fetching available vote options..."
options=$(fetch_vote_options)

if [ -z "$options" ]; then
    print_color "RED" "Error: No vote options available. Please contact the administrator."
    exit 1
fi

print_color "GREEN" "Available vote options:"
echo "$options"

# Prompt user for their vote
while true; do
    print_color "YELLOW" "Please enter your vote from the options above:"
    read vote

    if echo "$options" | grep -qw "$vote"; then
        break
    else
        print_color "RED" "Invalid vote. Please choose from the available options."
    fi
done

# Sign the vote
print_color "YELLOW" "Signing your vote..."
if [[ $key_type == "ed25519" ]]; then
    signature=$(echo -n "$vote" | ssh-keygen -Y sign -n "vote" -f "$ssh_key_path" 2>&1)
    if [ $? -ne 0 ]; then
        print_color "RED" "Error signing with Ed25519 key: $signature"
        exit 1
    fi
    signature=$(echo "$signature" | base64 -w 0)
else
    signature=$(echo -n "$vote" | openssl dgst -sha256 -sign "$ssh_key_path" 2>&1 | base64 -w 0)
    if [ $? -ne 0 ]; then
        print_color "RED" "Error signing with RSA key: $signature"
        exit 1
    fi
fi

print_color "GREEN" "Vote signed successfully."

# Get the public key
public_key=$(ssh-keygen -y -f "$ssh_key_path" 2>&1)
if [ $? -ne 0 ]; then
    print_color "RED" "Error getting public key: $public_key"
    exit 1
fi
public_key=$(echo "$public_key" | base64 -w 0)

# Combine vote, signature, public key, and key type
vote_package=$(echo -n "${vote}:${signature}:${public_key}:${key_type}" | base64 -w 0)

# Display the vote package and instructions
print_color "YELLOW" "Your signed vote package is:"
echo
echo $vote_package
echo

print_color "YELLOW" "Instructions:"
echo "1. Copy the signed vote package above (the long string of characters)."
echo "2. Go to ${SERVER_URL}/vote.html in your browser."
echo "3. Paste the signed vote package into the 'Your Signed Vote' field."
echo "4. Click the 'Submit Vote' button."

print_color "GREEN" "Thank you for voting!"