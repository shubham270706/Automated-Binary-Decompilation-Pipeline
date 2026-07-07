import re
import sys
import os

def normalize_strace(filepath):
    #Reads an strace log and strips out volatile data like memory addresses.
    cleaned_lines = []
    
    filepath=os.path.expanduser(f"~/Desktop/output/{filepath}")

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("+++") or line.startswith("---"):
                continue
                
            # 1. Normalize hex addresses (e.g., 0x7b4cb48f2000 -> 0x...)
            line = re.sub(r'0x[0-9a-fA-F]+', '0x...', line)
            
            # 2. Fine-tune execve: Strip the binary path and environment count differences
            if line.startswith("execve("):
                line = re.sub(r'execve\([^,]+, \[[^\]]+\], [^)]+\)', 'execve("./BINARY", ["./BINARY"], 0x... /* # vars */)', line)
                
            # 3. Fine-tune set_tid_address: Strip the returned PID/TID value
            if line.startswith("set_tid_address("):
                line = re.sub(r'= [0-9]+', '= PID', line)
                
            # 4. Fine-tune getrandom: Strip the actual random hex payload strings
            if "getrandom(" in line:
                line = re.sub(r'getrandom\("[^"]+",', 'getrandom("RANDOM_BYTES",', line)
                
            # 5. Fine-tune fstat/makedev: Standardize terminal minor device numbers to 0
            if "makedev(" in line:
                line = re.sub(r'makedev\(0x\.\.\., [^)]+\)', 'makedev(0x..., 0)', line)

            cleaned_lines.append(line)
            
    return cleaned_lines

def compare_traces(orig_path, llm_path):
    orig_trace = normalize_strace(orig_path)
    llm_trace = normalize_strace(llm_path)
    
    print(f"Original Trace lines: {len(orig_trace)}")
    print(f"LLM Trace lines: {len(llm_trace)}")
    print("-" * 50)
    
    mismatches = 0
    # Compare line by line up to the shortest log length
    for idx, (orig, llm) in enumerate(zip(orig_trace, llm_trace)):
        if orig != llm:
            print(f"[Mismatch at line {idx+1}]")
            print(f"  ORIG: {orig}")
            print(f"  LLM : {llm}")
            mismatches += 1

    if len(orig_trace) != len(llm_trace):
        print(f"\n[Warning] Log length mismatch! Streams separated after line {min(len(orig_trace), len(llm_trace))}")
        mismatches += abs(len(orig_trace) - len(llm_trace))

    if mismatches == 0 and len(orig_trace) == len(llm_trace):
        print(" Success: Both binaries executed identical system call sequences!")
    else:
        print(f"\n Found {mismatches} distinct behavior deviations.")
        print(f"Mismatch percentage: {100*mismatches/max(len(orig_trace),len(llm_trace))}")

# Run the comparison
#compare_traces("original.txt", "LLM.txt")
