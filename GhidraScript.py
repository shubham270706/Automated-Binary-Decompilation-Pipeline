#@author Shubham Mahato (oopsiedoopsie)
#@category _NEW_
#@keybinding 
#@menupath 
#@toolbar 
#@runtime PyGhidra

import os
from ghidra.app.decompiler.flatapi import FlatDecompilerAPI
from ghidra.program.flatapi import FlatProgramAPI
from ghidra.program.model.listing import CodeUnitFormat
import re
import subprocess

prgm_name = currentProgram.getName()
target_dir = os.path.expanduser(f"~/Desktop/{prgm_name}_folder")
C_dir = os.path.expanduser(f"~/Desktop/{prgm_name}_folder/C_code")
asmbly_dir = os.path.expanduser(f"~/Desktop/{prgm_name}_folder/asmbly_code")

prgm_path = currentProgram.getExecutablePath()

flat_api = FlatProgramAPI(currentProgram)

if not os.path.exists(target_dir):
    os.makedirs(target_dir)




output_path = os.path.join(target_dir, "strace_output.txt")
subprocess.run(["chmod","+x",prgm_path])    

try:
    # strace logs system calls to stderr by default
    result = subprocess.run(
        ["strace", prgm_path], 
        input=b"0\n",                  # <-- Sends the character '0' and a newline as raw bytes
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=10
    )

    stderr_str = result.stderr.decode('utf-8', errors='ignore')
    with open(output_path, "w") as f:
        f.write(stderr_str)


except subprocess.TimeoutExpired as e: # <-- Capture the exception object 'e'
    if e.stderr:
        partial_stderr = e.stderr.decode('utf-8', errors='ignore')
    else:
        partial_stderr = "// Trace timed out before data could be captured.\n"
        
    with open(output_path, "w") as f:
        f.write(partial_stderr)
        

def export_global_memory_segments(target_dir):
    memory = currentProgram.getMemory()
    header_content = "// Global Memory Segment Address Mapping Dump\n\n"
    
    for block in memory.getBlocks():
        if block.getName() in [".data", ".rodata"]:
            start_addr = block.getStart()
            size = block.getSize()
            
            try:
                raw_bytes = flat_api.getBytes(start_addr, int(size))
                if raw_bytes:
                    hex_vals = [hex(b & 0xff) for b in raw_bytes]
                    
                    block_clean = block.getName().replace('.', '')
                    header_content += f"// START_SEGMENT: {block.getName()}\n"
                    header_content += f"// BASE_ADDRESS: {start_addr}\n"
                    header_content += f"// SIZE: {size} bytes\n"
                    header_content += f"unsigned char MEM_{block_clean}[] = {{ {', '.join(hex_vals)} }};\n"
                    header_content += f"#define BASE_{block_clean} 0x{str(start_addr)}\n\n"
                    
            except Exception as e:
                header_content += f"// Failed to export block {block.getName()}: {str(e)}\n\n"
                
    output_path = os.path.join(target_dir, "global_memory.h")
    with open(output_path, 'w') as f:
        f.write(header_content)



export_global_memory_segments(target_dir)

if not os.path.exists(C_dir):
    os.makedirs(C_dir)
    
if not os.path.exists(asmbly_dir):
    os.makedirs(asmbly_dir)

flat_dec = FlatDecompilerAPI(flat_api)
functions_iterator = currentProgram.getFunctionManager().getFunctionsNoStubs(True)


code_unit_formatter = CodeUnitFormat.DEFAULT

BOILERPLATE_NAMES = {
    "_start", "_init", "_fini", "frame_dummy", 
    "register_tm_clones", "deregister_tm_clones", 
    "__do_global_dtors_aux", "_cxa_finalize"
}

for func in functions_iterator:
    name = func.getName()
    if func.isThunk():
        continue

    if name in BOILERPLATE_NAMES:
        continue

    if name.startswith("__") and name != "__cmain":
        if "scanf" in name or "fail" in name or "printf" in name:
            continue

    if currentProgram.getMemory().getBlock(func.getEntryPoint()).getName() in [".plt", "EXTERNAL"]:
        continue

    path_file_C_code=os.path.expanduser(f"~/Desktop/{prgm_name}_folder/C_code/{name}.txt")
    path_file_asmbly=os.path.expanduser(f"~/Desktop/{prgm_name}_folder/asmbly_code/{name}_asmbly.txt")
    
    instructions = currentProgram.getListing().getInstructions(func.getBody(), True)
       
    #Saving the decompiled C code
    with open((path_file_C_code), 'w') as file:
        file.write('#include "global_memory.h"\n\n')
        file.write(flat_dec.decompile(func))
    

    #Saving the assembly code
    with open((path_file_asmbly),'w') as file:
        for inst in instructions:
            addr = inst.getAddress()
    
            raw_bytes = inst.getBytes()
            hex_bytes = " ".join(f"{b & 0xff:02x}" for b in raw_bytes)
            
            assembly_string = code_unit_formatter.getRepresentationString(inst)
            
            file.write(f"{addr}  {hex_bytes:<14}  {assembly_string}\n")
