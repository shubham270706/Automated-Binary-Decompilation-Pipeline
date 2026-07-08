import re
import os

###------------------------------------------------Awaiting future changes which will include more robust compaprison and mismatch calculation-----------------------------------------------------###
def normalize_strace(filepath, target_workspace):
    cleaned_lines = []
    
    filepath = os.path.expanduser(f"{target_workspace}/{filepath}")

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Drop strace attachment messages/empty lines
            if not line or line.startswith("+++") or line.startswith("---") or line.startswith("???"):
                continue
                
            # --- SPECIFIC PATTERN MATCHING FIRST (Before general hex wiping) ---

            # 1. Fine-tune execve: Strip binary path, array references, and environment variable counts
            if line.startswith("execve("):
                line = re.sub(r'execve\([^,]+, \[[^\]]+\], [^)]+\)', 'execve("./BINARY", ["./BINARY"], 0x... /* # vars */)', line)
                
            # 2. Fine-tune set_tid_address: Strip the returned PID/TID value
            elif line.startswith("set_tid_address("):
                line = re.sub(r'= [0-9]+', '= PID', line)
                
            # 3. Fine-tune getrandom: Strip actual random hex payload and its length return
            elif "getrandom(" in line:
                line = re.sub(r'getrandom\("[^"]+",\s*([0-9]+)[^)]*\)\s*=\s*[0-9]+', 'getrandom("RANDOM_BYTES", \1) = STATUS', line)
                
            # 4. Fine-tune fstat/makedev: Standardize minor device constraints before hex conversion
            if "makedev(" in line:
                line = re.sub(r'makedev\(0x[0-9a-fA-F]+, [^)]+\)', 'makedev(0x..., 0)', line)

            # 5. Normalize generic File Descriptors (e.g., openat/read/close handling targets)
            # Normalizes "= 3", "= 4" return values to "= FD" to prevent cascade mismatches
            line = re.sub(r'\s*=\s*[3-9][0-9]*($|\s)', ' = FD ', line)
            # Also catch the descriptor mapping inside arguments (like close(3) or read(3, ...))
            line = re.sub(r'\((3|4|5|6|7|8|9),', '(FD,', line)
            line = re.sub(r'\(3\)', '(FD)', line) # Handles single-argument calls like close(3)

            # --- GENERAL CLEANUP LAST ---

            # 6. Normalize hex addresses/pointers (e.g., 0x7b4cb48f2000 -> 0x...)
            line = re.sub(r'0x[0-9a-fA-F]+', '0x...', line)

            cleaned_lines.append(line)
            
    return cleaned_lines

def compare_traces(orig_path, llm_path, target_workspace):
    orig_trace = normalize_strace(orig_path,target_workspace)
    llm_trace = normalize_strace(llm_path,target_workspace)
    
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
        min_len = min(len(orig_trace), len(llm_trace))
        print(f"\n[Warning] Log length mismatch! Streams separated after line {min_len}")
        mismatches += abs(len(orig_trace) - len(llm_trace))
        
        # Quick look into the overflow drift
        longer_trace = orig_trace if len(orig_trace) > len(llm_trace) else llm_trace
        label = "ORIG" if len(orig_trace) > len(llm_trace) else "LLM"
        print(f"  Next few lines from the longer stream ({label}):")
        for extra_line in longer_trace[min_len:min_len+3]:
            print(f"    -> {extra_line}")

    if mismatches == 0 and len(orig_trace) == len(llm_trace):
        print(" Success: Both binaries executed identical system call sequences!")
    else:
        print(f"\n Found {mismatches} distinct behavior deviations.")
        print(f"Mismatch percentage: {100*mismatches/max(len(orig_trace),len(llm_trace))}")

