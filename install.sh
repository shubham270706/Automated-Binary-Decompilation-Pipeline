#!/bin/bash

# Enforce root privileges
if [[ $EUID -ne 0 ]]; then
   echo "[-] Error: install.sh must be run with root privileges (sudo)."
   echo "    Usage: sudo ./install.sh"
   exit 1
fi

REAL_USER=${SUDO_USER:-$USER}
REAL_HOME=$(eval echo "~$REAL_USER")
PROJECT_DIR="$REAL_HOME/Desktop/Automated-Binary-Decompilation-Pipeline"

# Code to copy to the Desktop (if not already there)
CURRENT_DIR="$PWD"
if [[ "$CURRENT_DIR" != *Desktop* ]]; then
    echo "[-] I thought I told you to install in the Desktop Directory. Fine... I'll do it myself."
    echo "[*] Copying all the files to $REAL_HOME/Desktop/"
    cp -r "$CURRENT_DIR" "$REAL_HOME/Desktop/"
fi

# Code to check for Ghidra
DIR="/snap/ghidra/current/"
if [ -d "$DIR" ]; then 
    echo "[+] Ghidra installation verified."
else
    echo "[-] Ghidra is not installed correctly. Use 'sudo snap install ghidra'"
    exit 1
fi

mkdir -p /usr/local/share/man/man1/
# Using the dynamic path instead of hardcoded ~
cp "$PROJECT_DIR/AutoBDP.1" /usr/local/share/man/man1/
# Added -f to prevent hanging on overwrite if run twice
gzip -f /usr/local/share/man/man1/AutoBDP.1

# Installing dependencies safely via apt instead of breaking pip
echo "[*] Installing python dependencies..."
apt-get update -y
apt-get install -y python3-colorama
# Note: difflib is built into Python, no installation required.

# Code to fix the Gemini API Key
echo "[*] Configuring Gemini API Key..."
read -rp "Enter your Gemini API Key: " api_key
# Injecting into the actual user's bashrc, not root's bashrc
echo "export GEMINI_API_KEY=$api_key" >> "$REAL_HOME/.bashrc"
echo "Do check out the file 'LLM_stuff.py' file and verify the LLM Model used."
echo "The functions 'LLM_request_for_c_code_analyze()' and 'LLM_request_for_error()'"

# Setting permissions and symlink
echo "[*] Finalizing installation..."
chmod +x "$PROJECT_DIR/auto-bdp.py"
ln -sf "$PROJECT_DIR/auto-bdp.py" /usr/local/bin/AutoBDP
source "$REAL_HOME/.bashrc"

echo "[+] Installation complete!"
