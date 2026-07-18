#@author: Shubham Mahato (oopsiedoopsie)
#@github: https://github.com/shubham270706
#@LinkedIN: https://www.linkedin.com/in/shubham-mahato-0ba387299/
#@Discord: oopsie_doopsie224

from LLM_stuff import *
from strace_check import compare_traces
import LLM_stuff

def compare():compare_traces("strace_output.txt", "LLM_strace.txt",f"{LLM_stuff.target_workspace}")

def check_func():
    """Runs pre-checks to find if the file has been analysed already"""
    if(os.path.exists(LLM_stuff.cmpr_file_path) and os.path.exists(LLM_stuff.trace_output) and os.path.exists(LLM_stuff.binary_path) and os.path.exists(LLM_stuff.c_output_from_LLM)):
        print(Fore.LIGHTYELLOW_EX+"[*] A comparison of the original and LLM-produced program is availabe. Select: \n\t(1) Start from the beginning \n\t(2) Start from syntax checking \n\t(3) Compare again")
        option=input()
        print()
        match option:
            case "1":
                getting_c_prgm_from_LLM()
                syntax_error_check()
                run_strace()
                compare()
            
            case "2":
                syntax_error_check()
                run_strace()
                compare()

            case "3":
                run_strace()
                compare()
        return True


    if(os.path.exists(LLM_stuff.trace_output) and os.path.exists(LLM_stuff.binary_path) and os.path.exists(LLM_stuff.c_output_from_LLM)):
        print(Fore.LIGHTYELLOW_EX+"[*] The 'strace' result of the LLM-produced program is availabe. Select: \n\t(1) Start from the beginning \n\t(2) Start from syntax checking \n\t(3) Run strace again \n\t(4) Check strace similarity")
        option=input()
        print()
        match option:
            case "1":
                
                getting_c_prgm_from_LLM()
                syntax_error_check()
                run_strace()
                compare()
            
            case "2":
                
                syntax_error_check()
                run_strace()
                compare()

            case "3":
                run_strace()
                compare()

            case "4":
                compare()
        return True


    if(os.path.exists(LLM_stuff.binary_path) and os.path.exists(LLM_stuff.c_output_from_LLM)):
        print(Fore.LIGHTYELLOW_EX+"[*] Program from LLM is present and compiled. Select: \n\t(1) Start from the beginning \n\t(2) Compile Again \n\t(3) Continue from strace checking")
        option=input()
        print()
        match option:
            case "1":
                getting_c_prgm_from_LLM()
                syntax_error_check()
                run_strace()
                compare()

            case "2":
                syntax_error_check()
                run_strace()
                compare()

            case "3":
                run_strace()
                compare()
        return True


    if(os.path.exists(LLM_stuff.c_output_from_LLM)):
        print(Fore.LIGHTYELLOW_EX+"[*] Program from LLM is present but not compiled. Select: \n\t(1) Start from the beginning \n\t(2) Compile Again and/or Continue from error(compilation) checking")
        option=input()
        print()
        match option:
            case "1":
                getting_c_prgm_from_LLM()
                syntax_error_check()
                run_strace()
                compare()

            case "2":
                syntax_error_check()
                run_strace()
                compare()
        return True

def run_script():
    """The main stuff of this script/tool"""
    check=check_func()
    if(check):
        sys.exit(0)
    else:
        getting_c_prgm_from_LLM()
        syntax_error_check()
        run_strace()
        compare()
        sys.exit(0)
