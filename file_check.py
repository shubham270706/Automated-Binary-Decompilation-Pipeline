import difflib
import re
import os

###---------------------------Awaiting future changes which will include more robust compaprison and mismatch calculation-------------------------------###
def normalize_strace(filepath, target_workspace):
    """Reads an strace log and strips out volatile data like memory addresses."""
    cleaned_lines = []

    filepath = os.path.expanduser(f"{target_workspace}/{filepath}")

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Drop strace attachment messages/empty lines
            if (
                not line
                or line.startswith("+++")
                or line.startswith("---")
                or line.startswith("???")
            ):
                continue

            # SPECIFIC PATTERN MATCHING FIRST (Before general hex wiping)

            # Fine-tune execve: Strip binary path, array references, and environment variable counts
            if line.startswith("execve("):
                line = re.sub(
                    r"execve\([^,]+, \[[^\]]+\], [^)]+\)",
                    'execve("./BINARY", ["./BINARY"], 0x... /* # vars */)',
                    line,
                )

            # Fine-tune set_tid_address: Strip the returned PID/TID value
            elif line.startswith("set_tid_address("):
                line = re.sub(r"= [0-9]+", "= PID", line)

            # Fine-tune getrandom: Strip actual random hex payload and its length return
            elif "getrandom(" in line:
                line = re.sub(r'getrandom\("[^"]+",\s*([0-9]+)[^)]*\)\s*=\s*[0-9]+', r'getrandom("RANDOM_BYTES", \1) = STATUS', line)

            # Fine-tune fstat/makedev: Standardize minor device constraints before hex conversion
            if "makedev(" in line:
                line = re.sub(
                    r"makedev\(0x[0-9a-fA-F]+, [^)]+\)",
                    "makedev(0x..., 0)",
                    line,
                )

            # Normalize generic File Descriptors (e.g., openat/read/close handling targets)
            # Normalizes "= 3", "= 4" return values to "= FD" to prevent cascade mismatches
            line = re.sub(r"\s*=\s*[3-9][0-9]*($|\s)", " = FD ", line)
            # Also catch the descriptor mapping inside arguments (like close(3) or read(3, ...))
            line = re.sub(r"\((3|4|5|6|7|8|9),", "(FD,", line)
            line = re.sub(
                r"\(3\)", "(FD)", line
            )  # Handles single-argument calls like close(3)

            # Normalize hex addresses/pointers (e.g., 0x7b4cb48f2000 -> 0x...)
            line = re.sub(r"0x[0-9a-fA-F]+", "0x...", line)

            cleaned_lines.append(line)

    return cleaned_lines



def extract_syscall_token(line):
    """Safely plucks just the system call name from a normalized line."""
    match = re.match(r"^([a-zA-Z0-9_]+)\(", line)
    return match.group(1) if match else None


def calculate_fuzzy_similarity(orig_tokens, llm_tokens):
    """Calculates sequence ratio to match alignment regardless of startup library loading jitter."""
    matcher = difflib.SequenceMatcher(None, orig_tokens, llm_tokens)
    return matcher.ratio() * 100



def compare_traces(orig_path, llm_path, target_workspace):
    """Compare the system calls and prduces a similarity score"""
    orig_trace = normalize_strace(orig_path, target_workspace)
    llm_trace = normalize_strace(llm_path, target_workspace)

    print(f"Original Trace lines: {len(orig_trace)}")
    print(f"LLM Trace lines: {len(llm_trace)}")

    # Isolate system call tokens while ignoring messy arguments and addresses
    orig_tokens = [
        extract_syscall_token(line)
        for line in orig_trace
        if extract_syscall_token(line)
    ]
    llm_tokens = [
        extract_syscall_token(line)
        for line in llm_trace
        if extract_syscall_token(line)
    ]

    print("\n" + "-" * 50)
    print("        BEHAVIORAL STRUCTURAL ANALYSIS")
    
    if orig_tokens and llm_tokens:
        similarity_score = calculate_fuzzy_similarity(orig_tokens, llm_tokens)
        print(f"Total Trace Tokens (ORIG): {len(orig_tokens)}")
        print(f"Total Trace Tokens (LLM) : {len(llm_tokens)}")
        print(f"True Logic Similarity Score : {similarity_score:.2f}%")

        if similarity_score >= 85.0:
            print(
                "Verdict: HIGH STRUCTURAL SIMILARITY. Line mismatches in the file are \nlikely superficial compiler/linker loading configuration differences."
            )
        else:
            print(
                "Verdict: TRUE LOGIC DEVIATION. The binary execution paths \ndiverge significantly."
            )
    else:
        print("**Error:** Unable to extract syscall tokens for similarity score.")
    print("-" * 50 + "\n")

    print("The mismatches are saved in comparison_result.txt for reference")


    cmpr_file_path=os.path.join(target_workspace, "comparison_result.txt")
    with open(cmpr_file_path,'w') as f:

        mismatches = 0
        # Compare line by line up to the shortest log length
        for idx, (orig, llm) in enumerate(zip(orig_trace, llm_trace)):
            if orig != llm:
                f.write(f"[Mismatch at line {idx+1}]\n")
                f.write(f"  ORIG: {orig}\n")
                f.write(f"  LLM : {llm}\n")
                mismatches += 1

        if len(orig_trace) != len(llm_trace):
            min_len = min(len(orig_trace), len(llm_trace))
            f.write(
                f"\n[Warning] Log length mismatch! Streams separated after line {min_len}\n"
            )
            mismatches += abs(len(orig_trace) - len(llm_trace))

            # Quick look into the overflow drift
            longer_trace = (
                orig_trace if len(orig_trace) > len(llm_trace) else llm_trace
            )
            label = "ORIG" if len(orig_trace) > len(llm_trace) else "LLM"
            f.write(f"  Next few lines from the longer stream ({label}):\n")
            for extra_line in longer_trace[min_len : min_len + 3]:
                f.write(f"    -> {extra_line}\n")

        if mismatches == 0 and len(orig_trace) == len(llm_trace):
            f.write(" Success: Both binaries executed identical system call sequences!\n")
        else:
            f.write(f"\n Found {mismatches} distinct behavior deviations.\n")

