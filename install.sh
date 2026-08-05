#!/bin/bash
if [[ $EUID -ne 0 ]]; then
   echo "[-] Error: install.sh must be run with root privileges (sudo)."
   echo "    Usage: sudo ./install.sh"
   exit 1
fi

#Code to copy to the Desktop
name=$PWD"/"
if [[ $name != *Desktop* ]]; then
    echo "[-]I thought I told to install in the Desktop Directory. Fine... I'll do it myself."
    echo "[*]Copying all the files to Desktop"
    cp -r "$name"/ "$HOME"/Desktop/
fi

#Code to check for Ghidra
DIR="/snap/ghidra/current/"
if [ -d "$DIR" ]; then true;
else
    echo "[-]Ghidra is not installed correctly. Use "sudo snap install ghidra""
    exit 1
fi

#Defining the Manual
mkdir -p /usr/local/share/man/man1/
cp ~/Desktop/Automated-Binary-Decompilation-Pipeline/AutoBDP.1 /usr/local/share/man/man1/
gzip /usr/local/share/man/man1/AutoBDP.1

#Installing pip dependencies
pip install colorama --break-system-packages
pip install difflab --break-system-packages

#Code to fix the Gemini API Key
read -rp "Enter your Gemini API Key:" api_key
echo "export GEMINI_API_KEY=$api_key" >> "$HOME"/.bashrc
echo "Do check out the file 'LLM_stuff.py' file and verify the LLM Model used."
echo "The functions 'LLM_request_for_c_code_analyze()' and 'LLM_request_for_error()'"


chmod +x auto-bdp.py
sudo ln -s /home/shubham/Desktop/Automated-Binary-Decompilation-Pipeline/auto-bdp.py /usr/local/bin/AutoBDP
