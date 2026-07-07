#@author Shubham Mahato (aka oopsiedoopsie)
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

#Initialize the Paths
prgm_name = currentProgram.getName()
target_dir = os.path.expanduser(f"~/Desktop/{prgm_name}")
C_dir = os.path.expanduser(f"~/Desktop/{prgm_name}/C_code")
asmbly_dir = os.path.expanduser(f"~/Desktop/{prgm_name}/asmbly_code")

flat_api = FlatProgramAPI(currentProgram)

if not os.path.exists(target_dir):
    os.makedirs(target_dir)



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

#Creates a separate directory for C codes(from the Decompiler)
if not os.path.exists(C_dir):
    os.makedirs(C_dir)

#Creates a separate directory for Assembly code(from the Decompiler) 
if not os.path.exists(asmbly_dir):
    os.makedirs(asmbly_dir)

flat_dec = FlatDecompilerAPI(flat_api)
functions_iterator = currentProgram.getFunctionManager().getFunctionsNoStubs(True)


code_unit_formatter = CodeUnitFormat.DEFAULT

# Filtering the functions
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

    path_file_C_code=os.path.expanduser(f"~/Desktop/{prgm_name}/C_code/{name}.txt")
    path_file_asmbly=os.path.expanduser(f"~/Desktop/{prgm_name}/asmbly_code/{name}_asmbly.txt")
    
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
