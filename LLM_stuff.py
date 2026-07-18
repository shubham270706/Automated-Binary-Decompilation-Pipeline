#@author: Shubham Mahato (oopsiedoopsie)
#@github: https://github.com/shubham270706
#@LinkedIN: https://www.linkedin.com/in/shubham-mahato-0ba387299/
#@Discord: oopsie_doopsie224

import os
import subprocess
import glob
import sys
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError
from colorama import Fore,init
init(autoreset=True)

# Initialize the Gemini Client (Make sure GEMINI_API_KEY is set in the environment)
client = genai.Client()


target_workspace = ""
memory_header_path= ""
c_output_from_LLM = ""
binary_path = ""
trace_output = ""
cmpr_file_path = ""


def init_path(file_name):
    global target_workspace, binary_path, trace_output, cmpr_file_path, c_output_from_LLM, memory_header_path


    prgm_name=file_name
    target_workspace = os.path.expanduser(f"~/Desktop/{prgm_name}_folder")
    memory_header_path = os.path.join(target_workspace, "global_memory.h")
    c_output_from_LLM = os.path.join(target_workspace, "LLM_output.c")
    binary_path = os.path.join(target_workspace, "LLM_output")
    trace_output=os.path.join(target_workspace, "LLM_strace.txt")
    cmpr_file_path=os.path.join(target_workspace, "comparison_result.txt")
    


def gather_info():
    """Gathers all the necessary info needed for LLM-based workings"""
    global global_memory_context, strace_context, functions_payload

    functions_payload = []

    if os.path.exists(target_workspace)==False:
        print(Fore.RED+f"[-] Workspace directory {target_workspace} not found.")
        sys.exit(1);


    if os.path.exists(memory_header_path):
        with open(memory_header_path, 'r') as f:
            global_memory_context = f.read()


    original_trace = os.path.join(target_workspace, "strace_output.txt")

    if os.path.exists(original_trace):
        with open(original_trace, 'r') as f:
            strace_context = f.read()


    #Collect all extracted function data
    c_files = glob.glob(os.path.join(target_workspace, "C_code", "*.txt"))
        
    for c_file in c_files:
        func_name = os.path.basename(c_file).replace(".txt", "")
        asmbly_file = os.path.join(target_workspace, "asmbly_code", f"{func_name}_asmbly.txt")
            
        with open(c_file, 'r') as f:
            decompiled_c = f.read()
                
        assembly_code = ""
        if os.path.exists(asmbly_file):
            with open(asmbly_file, 'r') as f:
                assembly_code = f.read()
                    
        # Structure each function into an XML-like block for clear LLM parsing
        functions_payload.append(
            f"=== FUNCTION: {func_name} ===\n"
            f"--- DECOMPILED C ---\n{decompiled_c}\n"
            f"--- DISASSEMBLY ---\n{assembly_code}\n"
            )



def sanitize_code(raw_text):
    """Sanitizes the output from the LLM by removing stuff and retains the code"""
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("cpp"):
            raw_text = raw_text[3:]
        elif raw_text.startswith("c"):
            raw_text = raw_text[1:]
    return raw_text.strip()




def LLM_request_for_c_code_analyze():
    """Forwards the C-code, Assembly code and the Global Memory as context to the LLM"""
    gather_info()
  
    # Construct a unified system instruction and prompt payload
    system_instruction = (
        "You are an expert reverse engineer and static binary analysis agent."
        "Your task is to analyze the provided decompiled C code, disassembly, and global memory mappings "
        "to fix compilation bugs, recover variable semantics, and explain the binary logic."
    )
    
    prompt = (
        f"The global memory map layout for the binary:\n\n{global_memory_context}\n\n"
        "The program you will produce will be checked with the original file by comparing the system calls trace."
        f"You need to produce the program which mimics the 'strace' of the original file's given: \n\n{strace_context}\n\n"
        f"The individual extracted functions:\n\n" + "\n".join(functions_payload) + 
        "\n\n Analyze the data and prepare the compilation repair strategies.\n"
        "Provide only the clean program in specifically C programming language."
        "Start directly with the code syntax without conversational text or intros."
        "If it needs any flags while compiling, mention it as the last comment in the program"
        
    )


    # Fire the single payload to the LLM
    print(Fore.LIGHTYELLOW_EX+"[*] Dispatching consolidated binary context to LLM...")
    count=1
    while True:
        
        try:
            response_stream = client.models.generate_content_stream(
                #model='gemini-3.5-flash', # CHANGE THIS TO YOUR DESIRED GEMINI MODEL
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2 # Low temperature keeps binary logic reconstruction precise
                )
            )
  
            full_response_text = ""
            print("\n--- [LIVE STREAMING RESPONSE START] ---")
            for chunk in response_stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_response_text += chunk.text
            print("\n--- [LIVE STREAMING RESPONSE END] ---\n")
            return full_response_text
        
        except APIError as e:
            print(Fore.LIGHTYELLOW_EX+f"[*] API Error Status Code: {e.code}. Message: {e.message}")
            if e.code in [503,502]:
                print(Fore.LIGHTYELLOW_EX+"[*] Server busy. Sleeping for 30 seconds before retrying...")
                count+=1
                if count==4:
                    print(Fore.RED+"[-] Failed after 3 tries. Don't want to waste the Tokens.\n\t Try again after some time")
                    sys.exit(1)
                time.sleep(30)
                continue  # Retry generation payload loop
            else:
                print(Fore.RED+"[-] Fatal API Error encountered. Exiting.")
                sys.exit(1)




def LLM_request_for_error(error):
    """Forwards the Error, and all necessary details to the LLM to fix the compilation problem"""
    gather_info()
    
    code_path = os.path.join(target_workspace, "LLM_output.c")
    code = ""

    #Reading the code from the file which will be sent again to the LLM if there's any compilation error
    if os.path.exists(code_path):
        with open(code_path, 'r') as f:
            code = f.read()

    system_instruction= (
        "You are an expert and highly experienced coder with extra-ordinary error resolving skills."
        "You are being given a code with an attached error message which occurs when tried to compile the code."
        "Your job is to fix the error without changing the main logic structure and the conditions already present in the code."
    )

    prompt = (
        f"The faulty code: {code}\n\n"
        f"The global memory map layout for the binary:\n\n{global_memory_context}\n\n"
        f"The individual extracted functions:\n\n" + "\n".join(functions_payload) + 
        "\n\n"
        f"The error while compiling the faulty code: {error}\n\n"
        f"Produce the program which mimics the 'strace' of the original file's given: \n\n{strace_context}\n\n"
        "Use the original files trace calls to produce the closest file to the original ones"
        "Fix the error while maintaining the underlying binary logic structure. "
        "Provide only the clean program in specificaly C programming language starting directly with the syntax."
        "If it needs any flags while compiling, mention it as the last comment in the program"
    )


    count=1
    while True: 
        try:
            response_stream = client.models.generate_content_stream(
                #model='gemini-3.5-flash', # CHANGE THIS TO YOUR DESIRED GEMINI MODEL
                model='gemini-3-flash-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2 # Low temperature keeps binary logic reconstruction precise
                )
            )
            

            full_response_text = ""
            print("\n--- [LIVE STREAMING RESPONSE START] ---")
            for chunk in response_stream:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_response_text += chunk.text
            print("\n--- [LIVE STREAMING RESPONSE END] ---\n")
            
            return full_response_text
    
        except APIError as e:
            print(Fore.LIGHTYELLOW_EX+f"[*] API Error Status Code: {e.code}. Message: {e.message}")
            if e.code in [503,502]:
                print(Fore.LIGHTYELLOW_EX+"[*] Server busy. Sleeping for 30 seconds before retrying...")
                count+=1
                if count==4:
                    print(Fore.RED+"[-] Failed after 3 tries. Dont want to waste the Tokens.\n\t Try again after some time")
                    sys.exit(1)
                time.sleep(30)
                continue  # Retry generation payload loop
            else:
                print(Fore.RED+"[-] Fatal API Error encountered. Exiting.")
                sys.exit(1)




def getting_c_prgm_from_LLM():
    """Uses the LLM to produce the C file"""
    # Running the script
    analysis_result = LLM_request_for_c_code_analyze()
    analysis_result=sanitize_code(analysis_result)
    
    with open(c_output_from_LLM, 'w') as f:
        f.write(analysis_result)
    file_given=True




def syntax_error_check():
    """Compiles the c code and checks for any syntax errors. Inlcudes the LLM loop incase there's any syntax error"""
    count =0
    while(count<3): #CHNAGE THIS TO MODIFY THE NUMBER OF ATTEMPTS
        print(Fore.LIGHTYELLOW_EX+"Enter any additional flags for gcc: ")
        options=input()

        #Checking for syntax errors in the code given by the LLM
        print("-"*50)
        print("\t\tCOMPILING\n")
        
        cmd = f"gcc {c_output_from_LLM} -o {os.path.join(target_workspace, 'LLM_output')} {options}"

        #Compiling the code from the LLM
        result=subprocess.run(cmd,shell=True,capture_output=True,text=True)

        if result.returncode == 0:
            print(Fore.GREEN+"[+] Compilation Successful!")
            break

        else:
            count += 1
            print(Fore.RED+f"[-] Error detected (Attempt {count}/3)... Forwarding to LLM.")
            print(f"The error is: {result.stderr}")
            analysis_result =LLM_request_for_error(result.stderr)
            analysis_result=sanitize_code(analysis_result)

            # Saving the fixed code inline
            with open(c_output_from_LLM, 'w') as f:
                f.write(analysis_result)
        
    else:
        print(Fore.RED+"[-] Reached maximum compilation repair attempts without resolving errors.")




def run_strace():
    """Runs 'strace' on the LLM-produced C file and compares with the originals file's strace."""
    try:
        # strace logs system calls to stderr by default
        result = subprocess.run(
            ["strace", binary_path], 
            input=b"0\n",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10 
        )
        
        stderr_str = result.stderr.decode('utf-8', errors='ignore')

        with open(trace_output, "w") as f:
            f.write(stderr_str)
        print(Fore.GREEN+f"[+] strace output successfully saved to {trace_output}")

    except subprocess.TimeoutExpired as e:
        print(Fore.LIGHTYELLOW_EX+"[*] strace timed out (likely waiting for user input), saving partial trace.")
        if e.stderr:
            partial_stderr = e.stderr.decode('utf-8', errors='ignore')
        else:
            partial_stderr = "// Trace timed out before data could be captured.\n"
            
        with open(trace_output, "w") as f:
            f.write(partial_stderr)                
        
    except Exception as e:
        print(Fore.RED+f"[-] Failed to run strace: {str(e)}")

