#!/usr/bin/env python3
# AutoBDP - Automated Binary Decompiler Pipeline
# Copyright (C) 2026 Shubham Mahato (oopsiedoopsie)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA


#@github: https://github.com/shubham270706
#@LinkedIN: https://www.linkedin.com/in/shubham-mahato-0ba387299/
#@Discord: oopsie_doopsie224



import subprocess
import os
import sys
from colorama import Fore,init
from pathlib import Path
from pre_run_checks import run_script
import LLM_stuff
import shutil

init(autoreset=True)

def print_banner():
    banner=Fore.RED+r""" 
              _               _                 ______   ______   _______   
             / \             / |_              |_   _ \ |_   _ `.|_   __ \  
            / _ \    __   _ `| |-' .--.   ______ | |_) |  | | `. \ | |__) | 
           / ___ \  [  | | | | | / .'`\ \|______||  __'.  | |  | | |  ___/  
         _/ /   \ \_ | \_/ |,| |,| \__. |       _| |__) |_| |_.' /_| |_     
        |____| |____|'.__.'_/\__/ '.__.'       |_______/|______.'|_____|    
                                                                       
                                                                                                
                                                    
            Automated RE Framework v1.1
            Created by: Shubham Mahato (oopsiedoopsie)
            Github: https://github.com/shubham270706
            Discord: oopsie_doopsie224"""
    print(f"{banner}\n\n")

print_banner()

print(Fore.LIGHTYELLOW_EX+"[*] Enter the name of the executable(along with path): ")
path=input().strip().strip("\'").strip("\"")
path = Path(path).expanduser().absolute()

#Initialising paths
file_name = path.name
script_path=os.path.expanduser("~/Desktop/Automated-Binary-Decompilation-Pipeline/GhidraScript.py")
project_path=os.path.expanduser("~")

#Required for usage of paths of different files
LLM_stuff.init_path(file_name)

option1="1"

if(os.path.exists(LLM_stuff.target_workspace)):
    print(Fore.LIGHTYELLOW_EX+"[*] The executable file has probably been analysed by the Ghidra script before. Select: \n\t(1) Analyse again \n\t(2) Continue from here")
    option1=input()
    match option1:
        case "1":
            print(Fore.LIGHTYELLOW_EX+"[*] Deleting the pre-existing directory...")
            shutil.rmtree(os.path.expanduser(LLM_stuff.target_workspace))
            cmd1 = f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless {project_path} new_project -import {path} -overwrite"

            cmd2 = f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless {project_path} new_project -process {file_name} -postScript {script_path}"

            print(Fore.LIGHTYELLOW_EX+"[*] Importing the file in Ghidra...")
            result1=subprocess.run(cmd1, shell=True, capture_output=True, text=True)
            if result1.returncode==0:
                print(Fore.GREEN+"[+] Import was Successful...")
            print(Fore.LIGHTYELLOW_EX+"[*] Running Ghidra Headless Analyzer and Extractor...")
            result2=subprocess.run(cmd2, shell=True, capture_output=True, text=True)
            if result2.returncode==0:
                print(Fore.GREEN+"[+] Analysis and Extraction was Successful...")
            
            if(result1.returncode!=0 or result2.returncode!=0):
                print(result1.stderr)
                print(result2.stderr)
                sys.exit(1)
            
                
        case "2":
            run_script()
            

else:
    cmd1 = f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless {project_path} new_project -import {path} -overwrite"

    cmd2 = f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless {project_path} new_project -process {file_name} -postScript {script_path}"

    print(Fore.LIGHTYELLOW_EX+"[*] Importing the file in Ghidra...")
    result1=subprocess.run(cmd1, shell=True, capture_output=True, text=True)
    if result1.returncode==0:
        print(Fore.GREEN+"[+] Import Successful...")
    print(Fore.LIGHTYELLOW_EX+"[*] Running Ghidra Headless Analyzer and Extractor...")
    result2=subprocess.run(cmd2, shell=True, capture_output=True, text=True)
    if result2.returncode==0:
        print(Fore.GREEN+"[+] Analysis and Extraction was Successful...")
    
    if(result1.returncode!=0 or result2.returncode!=0):
        print(result1.stderr)
        print(result2.stderr)
        sys.exit(1)

if(option1!="2"):
    print(Fore.LIGHTYELLOW_EX+"[*] Ghidra has done it's work. Select: \n\t(1) Continue with LLM \n\t(2) Exit")
    option2=input()
    match option2:
        case "1":
            run_script()
        case "2":
            print(Fore.LIGHTYELLOW_EX+"[*] Exiting...")
            sys.exit(0)
