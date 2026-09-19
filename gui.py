#!/usr/bin/env python3
# AutoBDP GUI - Graphical front-end for the Automated Binary Decompiler Pipeline
# Copyright (C) 2026 Shubham Mahato (oopsiedoopsie)
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.

import os
import re
import sys
import time
import queue
import shutil
import threading
import subprocess
import tkinter as tk
from colorama import Fore,init
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
init(autoreset=True)

# ---------------------------------------------------------------------------
# ANSI (colorama) -> Tk tag translation
# ---------------------------------------------------------------------------
ANSI_RE = re.compile(r"\x1b\[(\d+)m")
ANSI_TAG_MAP = {
    "31": "red",
    "91": "red",
    "32": "green",
    "92": "green",
    "93": "yellow",
    "33": "yellow",
    "0": "reset",
}


class TextRedirector:
    """A file-like object that pushes text into a thread-safe queue for the GUI to drain."""

    def __init__(self, out_queue):
        self.out_queue = out_queue
        self._buf = ""

    def write(self, s):
        if s:
            self.out_queue.put(s)

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# Thread-safe stand-in for the builtin input()
# ---------------------------------------------------------------------------
class GuiInput:
    """
    Replaces the builtin input() used throughout pre_run_checks.py / LLM_stuff.py /
    strace_check.py. Worker-thread calls block on a queue; the main Tk thread is
    polled periodically and pops up a small dialog to collect the answer.
    """

    def __init__(self, app):
        self.app = app
        self.request_q = queue.Queue()
        self.response_q = queue.Queue()

    def __call__(self, prompt=""):
        self.request_q.put(prompt)
        return self.response_q.get()  # blocks the worker thread until answered


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class AutoBDPGui:
    POLL_MS = 80

    def __init__(self, root):
        self.root = root
        self.root.title("AutoBDP - Automated Binary Decompiler Pipeline")
        self.root.geometry("980x640")
        self.root.minsize(760, 480)

        self.out_queue = queue.Queue()
        self.gui_input = GuiInput(self)
        self.worker_thread = None
        self._dialog_open = False
        self._active_dialog = None
        self.stop_event = threading.Event()
        self.current_proc = None

        self._build_menu()
        self._build_layout()
        self._install_hooks()
        self._print_banner()

        self.root.after(self.POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Set Gemini API Key...", command=self._set_api_key)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_layout(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Target executable:").grid(row=0, column=0, sticky="w")
        self.path_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.path_var, width=70)
        entry.grid(row=0, column=1, padx=6, sticky="we")
        top.columnconfigure(1, weight=1)

        ttk.Button(top, text="Browse...", command=self._browse_file).grid(row=0, column=2, padx=4)

        btn_row = ttk.Frame(self.root, padding=(10, 0))
        btn_row.pack(side=tk.TOP, fill=tk.X)

        self.start_btn = ttk.Button(btn_row, text="Start Pipeline", command=self._start_pipeline)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(btn_row, text="Stop", command=self._stop_pipeline, state="disabled")
        self.stop_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.exit_btn = ttk.Button(btn_row, text="Exit", command=self._exit_app)
        self.exit_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(btn_row, textvariable=self.status_var, foreground="#555").pack(side=tk.LEFT, padx=12)

        # Console
        console_frame = ttk.Frame(self.root, padding=10)
        console_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.console = tk.Text(
            console_frame, bg="#0d0d0d", fg="#e6e6e6", insertbackground="#e6e6e6",
            wrap="word", state="disabled", font=("Consolas", 10)
        )
        self.console.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(console_frame, command=self.console.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.console.config(yscrollcommand=scrollbar.set)

        self.console.tag_config("red", foreground="#ff5f5f")
        self.console.tag_config("green", foreground="#5fff87")
        self.console.tag_config("yellow", foreground="#ffe066")
        self.console.tag_config("reset", foreground="#e6e6e6")

    # ------------------------------------------------------------------
    # stdout / input hooking
    # ------------------------------------------------------------------
    def _install_hooks(self):
        sys.stdout = TextRedirector(self.out_queue)
        sys.stderr = TextRedirector(self.out_queue)
        import builtins
        builtins.input = self.gui_input

    def _print_banner(self):
        banner = Fore.RED + r""" 
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

    # ------------------------------------------------------------------
    # Periodic poll (runs on the Tk main thread)
    # ------------------------------------------------------------------
    def _poll(self):
        # Drain console output
        drained = False
        while True:
            try:
                chunk = self.out_queue.get_nowait()
            except queue.Empty:
                break
            self._append_console(chunk)
            drained = True

        # Handle pending input requests
        if not self._dialog_open:
            try:
                prompt = self.gui_input.request_q.get_nowait()
            except queue.Empty:
                prompt = None
            if prompt is not None:
                self._dialog_open = True
                self._show_input_dialog(prompt)

        self.root.after(self.POLL_MS, self._poll)

    def _append_console(self, chunk):
        self.console.config(state="normal")
        pos = 0
        current_tag = "reset"
        for m in ANSI_RE.finditer(chunk):
            text_piece = chunk[pos:m.start()]
            if text_piece:
                self.console.insert("end", text_piece, current_tag)
            code = m.group(1)
            current_tag = ANSI_TAG_MAP.get(code, "reset")
            pos = m.end()
        tail = chunk[pos:]
        if tail:
            self.console.insert("end", tail, current_tag)
        self.console.see("end")
        self.console.config(state="disabled")

    def _show_input_dialog(self, prompt):
        """Pops up a small entry dialog. The console behind it already shows full colored context."""
        dlg = tk.Toplevel(self.root)
        dlg.title("AutoBDP - input needed")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)
        self._active_dialog = dlg

        # Anchor near the bottom-right of the main window so the colored
        # console stays visible behind it instead of being covered.
        self.root.update_idletasks()
        rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        dlg.geometry(f"+{rx + rw - 420}+{ry + rh - 160}")

        ttk.Label(dlg, text="The pipeline is waiting for your input:", padding=(10, 10, 10, 6)).pack(anchor="w")

        var = tk.StringVar()
        entry = ttk.Entry(dlg, textvariable=var, width=50)
        entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        entry.focus_set()

        def submit(event=None):
            value = var.get()
            self._dialog_open = False
            self._active_dialog = None
            dlg.destroy()
            self.gui_input.response_q.put(value)

        ttk.Button(dlg, text="Submit", command=submit).pack(pady=(0, 10))
        entry.bind("<Return>", submit)
        dlg.protocol("WM_DELETE_WINDOW", submit)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------
    def _set_api_key(self):
        current = os.environ.get("GEMINI_API_KEY", "")
        key = simpledialog.askstring(
            "Gemini API Key",
            "Enter your Gemini API Key:",
            initialvalue=current,
            show="*",
            parent=self.root,
        )
        if key:
            os.environ["GEMINI_API_KEY"] = key
            messagebox.showinfo("AutoBDP", "API key set for this session.")

    def _show_about(self):
        messagebox.showinfo(
            "About AutoBDP",
            "AutoBDP - Automated Binary Decompiler Pipeline\n"
            "GUI front-end\n\n"
            "Pairs headless Ghidra extraction with LLM code synthesis,\n"
            "a GCC compilation-repair loop, and strace-based behavioral diffing.\n\n"
            "Created by Shubham Mahato (oopsiedoopsie)",
        )

    def _browse_file(self):
        chosen = filedialog.askopenfilename(title="Select target executable")
        if chosen:
            self.path_var.set(chosen)

    # ------------------------------------------------------------------
    # Pipeline driver (runs on a background thread)
    # ------------------------------------------------------------------
    def _start_pipeline(self):
        raw_path = self.path_var.get().strip()
        if not raw_path:
            messagebox.showwarning("AutoBDP", "Please choose an executable first.")
            return
        if not os.path.exists(raw_path):
            messagebox.showerror("AutoBDP", f"File not found:\n{raw_path}")
            return
        if os.environ.get("GEMINI_API_KEY", "") == "":
            if not messagebox.askyesno(
                "AutoBDP",
                "GEMINI_API_KEY is not set for this session.\n"
                "You can set it under Settings > Set Gemini API Key.\n\n"
                "Continue anyway (Ghidra extraction still works, LLM step will fail)?",
            ):
                return

        self.stop_event.clear()
        import cancel
        cancel.reset()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Running...")

        self.worker_thread = threading.Thread(target=self._run_pipeline, args=(raw_path,), daemon=True)
        self.worker_thread.start()
        self._watch_worker()

    def _watch_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(300, self._watch_worker)
        else:
            self.start_btn.config(state="normal")
            self.stop_btn.config(state="disabled")
            self.status_var.set("Idle")

    def _stop_pipeline(self):
        """
        Best-effort stop: kills the currently running Ghidra subprocess (if any)
        immediately, and sets a flag checked between pipeline stages so nothing
        new is started. It cannot forcibly interrupt a blocking call already in
        progress inside pre_run_checks.py / LLM_stuff.py (e.g. a live Gemini
        request or compiler invocation) - Python threads can't be killed from
        the outside - but if the worker is waiting on an input dialog, that
        dialog is closed and answered with an empty value so the pipeline can
        reach its next checkpoint and exit there.
        """
        if not (self.worker_thread and self.worker_thread.is_alive()):
            return
        from colorama import Fore
        import cancel
        self.stop_event.set()
        cancel.request_stop()
        self.status_var.set("Stopping...")
        print(Fore.RED + "\n[!] Stop requested by user...")

        proc = self.current_proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                print(Fore.RED + "[!] Terminated the running Ghidra subprocess.")
            except Exception:
                pass

        if self._dialog_open and self._active_dialog is not None:
            try:
                self._active_dialog.destroy()
            except Exception:
                pass
            self._dialog_open = False
            self._active_dialog = None
            self.gui_input.response_q.put("")

    def _exit_app(self):
        if self.worker_thread and self.worker_thread.is_alive():
            if not messagebox.askyesno(
                "AutoBDP", "The pipeline is still running. Stop it and exit anyway?"
            ):
                return
            self._stop_pipeline()
        self.root.destroy()

    def _run_subprocess(self, cmd):
        """Runs a shell command as a trackable, terminable subprocess."""
        proc = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        self.current_proc = proc
        while proc.poll() is None:
            if self.stop_event.is_set():
                try:
                    proc.terminate()
                except Exception:
                    pass
                break
            time.sleep(0.15)
        stdout, stderr = proc.communicate()
        self.current_proc = None
        return proc.returncode, stdout, stderr

    def _run_pipeline(self, raw_path):
        """
        Mirrors the logic of auto-bdp.py, using the browsed path directly instead
        of prompting for it. All downstream menu choices still go through the
        GUI input dialog because pre_run_checks.py / LLM_stuff.py call input().
        """
        try:
            from colorama import Fore
            import cancel
            path = Path(raw_path).expanduser().absolute()
            file_name = path.name

            script_dir = os.path.dirname(os.path.realpath(__file__))
            script_path = os.path.join(script_dir, "GhidraScript.py")
            project_path = os.path.expanduser("~")
            
            if not os.path.exists(script_path):
                print(Fore.RED + f"[-] GhidraScript.py not found at {script_path}")
                print(Fore.RED + "    -postScript will silently fail to run if this path is wrong.")
                return
            
            import LLM_stuff
            from pre_run_checks import run_script

            LLM_stuff.init_path(file_name)

            option1 = "1"

            def do_fresh_analysis():
                cmd1 = (
                    f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless "
                    f"{project_path} new_project -import {path} -overwrite"
                )
                cmd2 = (
                    f"/snap/ghidra/current/ghidra/support/pyghidraRun --headless "
                    f"{project_path} new_project -process {file_name} -postScript {script_path}"
                )

                if self.stop_event.is_set():
                    return False

                print(Fore.LIGHTYELLOW_EX + "[*] Importing the file in Ghidra...")
                rc1, out1, err1 = self._run_subprocess(cmd1)
                if rc1 == 0:
                    print(Fore.GREEN + "[+] Import was Successful...")

                if self.stop_event.is_set():
                    print(Fore.RED + "[!] Stopped before analysis step.")
                    return False

                print(Fore.LIGHTYELLOW_EX + "[*] Running Ghidra Headless Analyzer and Extractor...")
                rc2, out2, err2 = self._run_subprocess(cmd2)
                if rc2 == 0:
                    print(Fore.GREEN + "[+] Analysis and Extraction was Successful...")

                if rc1 != 0 or rc2 != 0:
                    print(err1)
                    print(err2)
                    return False
                return True

            if os.path.exists(LLM_stuff.target_workspace):
                print(
                    Fore.LIGHTYELLOW_EX
                    + "[*] The executable file has probably been analysed by the Ghidra script before. Select: \n"
                    "\t(1) Analyse again \n\t(2) Continue from here"
                )
                option1 = input()
                if self.stop_event.is_set():
                    print(Fore.RED + "[!] Stopped.")
                    return
                if option1 == "1":
                    print(Fore.LIGHTYELLOW_EX + "[*] Deleting the pre-existing directory...")
                    shutil.rmtree(os.path.expanduser(LLM_stuff.target_workspace))
                    if not do_fresh_analysis():
                        self._pipeline_failed()
                        return
                elif option1 == "2":
                    run_script()
            else:
                if not do_fresh_analysis():
                    self._pipeline_failed()
                    return

            if self.stop_event.is_set():
                print(Fore.RED + "[!] Stopped.")
                return

            if option1 != "2":
                print(
                    Fore.LIGHTYELLOW_EX
                    + "[*] Ghidra has done it's work. Select: \n\t(1) Continue with LLM \n\t(2) Exit"
                )
                option2 = input()
                if self.stop_event.is_set():
                    print(Fore.RED + "[!] Stopped.")
                    return
                if option2 == "1":
                    run_script()
                else:
                    print(Fore.LIGHTYELLOW_EX + "[*] Exiting...")

            print(Fore.GREEN + "\n[+] Pipeline run finished.")

        except SystemExit:
            pass
        except cancel.PipelineCancelled:
            print(Fore.RED + "\n[!] Pipeline stopped by user.")
        except Exception as exc:
            print(f"\n[!] GUI pipeline error: {exc}")

    def _pipeline_failed(self):
        from colorama import Fore
        print(Fore.LIGHTYELLOW_EX + "[*] Ghidra step failed; see errors above.")

def print_banner():
        banner = Fore.RED + r""" 
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


def print_usage():
    message="""Usage:
            AutoBDP [options]

            Options:
                -h, --help      Show this help menu and exit.
                --headless      Start the Command-Line Interface (CLI) version.
                (no options)    Start the Graphical User Interface (GUI)."""
    print(f"{message}\n\n")

def main():

    if(len(sys.argv)>1):
        if(sys.argv[1]=="--headless"):
            subprocess.run(["python3",os.path.join(os.path.dirname(os.path.realpath(__file__)),"auto-bdp.py")])
        elif(sys.argv[1]=="-h" or sys.argv[1]=="--help"):
            print_banner()
            print_usage()
        else:
            print_banner()
            print(f"AutoBDP: error: unrecognized arguments: {sys.argv[1]}\n")
            print_usage()
        sys.exit(0)

    root = tk.Tk(className='AutoBDP')
    filename=os.path.join(os.path.dirname(os.path.realpath(__file__)),"assets", "icon.png")
    try:
        style = ttk.Style()
        icon_img=tk.PhotoImage(file=filename)
        root.iconphoto(True,icon_img)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception as e:
        print(e)
    app = AutoBDPGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
