import os
import subprocess
import glob
import sys
from google import genai
from google.genai import types
from check import compare_traces


file_given =False

# Initialize the Gemini Client (Make sure GEMINI_API_KEY is set in your environment)
client = genai.Client()

prgm_name=input("Enter the name of the program: ") #Will change this after connecting the script directly to Ghidra
target_workspace = os.path.expanduser(f"~/Desktop/{prgm_name}")

if os.path.exists(target_workspace)==False:
    print(f"[-] Workspace directory {target_workspace} not found.")
    sys.exit();


memory_header_path = os.path.join(target_workspace, "global_memory.h")
global_memory_context = ""
if os.path.exists(memory_header_path):
    with open(memory_header_path, 'r') as f:
        global_memory_context = f.read()

    #Collect all extracted function data

functions_payload = []
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
    if "```" in raw_text:
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("cpp"):
            raw_text = raw_text[3:]
        elif raw_text.startswith("c"):
            raw_text = raw_text[1:]
    return raw_text.strip()


#Function sending all the required files to the LLM for the first run
def bundle_and_analyze():
  
#Construct a unified system instruction and prompt payload for the first run
    system_instruction = (
        "You are an expert reverse engineer and static binary analysis agent. "
        "Your task is to analyze the provided decompiled C code, disassembly, and global memory mappings "
        "to fix compilation bugs, recover variable semantics, and explain the binary logic."
    )
    
    prompt = (
        f"Here is the global memory map layout for the binary:\n\n{global_memory_context}\n\n"
        f"Here are the individual extracted functions:\n\n" + "\n".join(functions_payload) + 
        "\n\nPlease analyze the data and prepare the compilation repair strategies. \n"
        "Provide only the clean program in C++ programming language. "
        "Start directly with the code syntax without conversational text or intros."
        
    )

    #Fire the single payload to Gemini Pro

    print("[*] Dispatching consolidated binary context to Gemini Pro...")
    response_stream = client.models.generate_content_stream(
        model='gemini-3.5-flash', # Or your specific Gemini Pro tier model
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2 # Low temperature keeps binary logic reconstruction precise
        )
    )


    #This shows the response for the LLM
    #Comment it out if you dont wanna see them
    full_response_text = ""
    print("\n--- [LIVE STREAMING RESPONSE START] ---")
    for chunk in response_stream:
        if chunk.text:
            print(chunk.text, end="", flush=True)
            full_response_text += chunk.text
    print("\n--- [LIVE STREAMING RESPONSE END] ---\n")
    
    return full_response_text



#Function which uses API to send the code along with the error message
def error_check(error):
    code_path = os.path.join(target_workspace, "LLM_output.cpp")
    code = ""

    #Reading the code from the file which will be sent again to the LLM if there's any compilation error
    if os.path.exists(code_path):
        with open(code_path, 'r') as f:
            code = f.read()

    system_instruction= (
        "You are an expert and highly experienced coder with extra-ordinary error resolving skills. "
        "You are being given a code with an attached error message which occurs when tried to compile the code. "
        "Your job is to fix the error without changing the main logic structure and the conditions already present in the code. "
    )

    prompt = (
        f"Here is the faulty code: {code}\n\n"
        f"Here is the global memory map layout for the binary:\n\n{global_memory_context}\n\n"
        f"Here are the individual extracted functions:\n\n" + "\n".join(functions_payload) + 
        "\n\n"
        f"Here is the error while compiling the faulty code: {error}\n\n"
        "Fix the error while maintaining the underlying binary logic structure. "
        "Provide only the clean program in C++ programming language starting directly with the syntax."
    )

    response_stream = client.models.generate_content_stream(
        model='gemini-3.5-flash', # Or your specific Gemini Pro tier model
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2 # Low temperature keeps binary logic reconstruction precise
        )
    )

    
    #This shows the response for the LLM
    #Comment it out if you dont wanna see them
    full_response_text = ""
    print("\n--- [LIVE STREAMING RESPONSE START] ---")
    for chunk in response_stream:
        if chunk.text:
            print(chunk.text, end="", flush=True)
            full_response_text += chunk.text
    print("\n--- [LIVE STREAMING RESPONSE END] ---\n")
    
    return full_response_text



# Running the script
analysis_result = bundle_and_analyze()
analysis_result=sanitize_code(analysis_result)
output_path = os.path.join(target_workspace, "LLM_output.cpp")
with open(output_path, 'w') as f:
    f.write(analysis_result)
file_given=True



#Checking for syntax errors in the code given by the LLM
if(file_given):
    count =0
    cmd = f"g++ {os.path.join(target_workspace, 'LLM_output.cpp')} -o {os.path.join(target_workspace, 'LLM_output')}"
    while(count<3):

        #Compiling the code from the LLM

        result=subprocess.run(cmd,shell=True,capture_output=True,text=True)

        if result.returncode == 0:
            print("[+] Compilation Successful!")
            break

        else:
            count += 1
            print(f"[-] Error detected (Attempt {count}/3)... Forwarding to LLM.")
            print(f"The error is: {result.stderr}")
            analysis_result = error_check(result.stderr)
            analysis_result=sanitize_code(analysis_result)

            # Saving the fixed code inline
            output_path = os.path.join(target_workspace, 'LLM_output.cpp')
            with open(output_path, 'w') as f:
                f.write(analysis_result)
    
    else:
        print("[-] Reached maximum compilation repair attempts without resolving errors.")
