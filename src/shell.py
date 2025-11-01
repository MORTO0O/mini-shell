import os
import pathlib
import shutil
import logging
import sys
import shlex
import re
import stat
from datetime import datetime
from functools import partial
from .constants import LOG_FILE, HIST_FILE, COUNTER_FILE, TRASH_DIR

class Shell:
    def __init__(self):
        self.current_dir = pathlib.Path.cwd()
        self.trash_dir = pathlib.Path.home() / TRASH_DIR
        self.hist_file = pathlib.Path.home() / HIST_FILE
        self.counter_file = pathlib.Path.home() / COUNTER_FILE
        self.log_file = pathlib.Path.home() / LOG_FILE
        self.global_counter = 0
        self.last_undo = None
        self._setup_logging()
        self.trash_dir.mkdir(exist_ok=True)
        if self.hist_file.exists():
            with open(self.hist_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if lines:
                nums = []
                for line in lines:
                    if line.strip():
                        try:
                            num = int(line.split('.')[0].strip())
                            nums.append(num)
                        except ValueError:
                            pass
                if nums:
                    self.global_counter = max(nums)
        if self.counter_file.exists():
            try:
                cnt = int(self.counter_file.read_text(encoding="utf-8").strip())
                self.global_counter = max(self.global_counter, cnt)
            except ValueError:
                pass
        self._commands = {
            "ls": CmdHandlers.ls,
            "cd": CmdHandlers.cd,
            "cat": CmdHandlers.cat,
            "cp": CmdHandlers.cp,
            "mv": CmdHandlers.mv,
            "rm": CmdHandlers.rm,
            "grep": CmdHandlers.grep,
            "history": CmdHandlers.history,
            "undo": CmdHandlers.undo,
            "exit": CmdHandlers.exit_cmd,
        }

    def _setup_logging(self):
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def run(self):
        print("Mini-shell started. Type 'exit' to quit.")
        while True:
            try:
                cmd = input(f"{self.current_dir}$ ")
            except EOFError:
                print("\nExiting mini-shell.")
                break
            if not cmd.strip():
                continue
            logging.info(f"{cmd}")
            try:
                parts = shlex.split(cmd)
                command = parts[0]
                args = parts[1:]
                cmd_func = self._commands.get(command)
                if not cmd_func:
                    raise ValueError(f"Unknown command: {command}")
                new_dir = cmd_func(self, args)
                if new_dir is not None:
                    os.chdir(new_dir)
                    self.current_dir = pathlib.Path.cwd()
                logging.info(f"OK: {cmd}")
                self.global_counter += 1
                with open(self.hist_file, "a", encoding="utf-8") as f:
                    f.write(f"{self.global_counter}. {cmd}\n")
                with open(self.counter_file, "w", encoding="utf-8") as f:
                    f.write(str(self.global_counter))
            except SystemExit:
                logging.info("Exiting mini-shell.")
                break
            except Exception as e:
                print(f"Error: {str(e)}", file=sys.stderr)
                logging.error(f"ERROR: {str(e)}")

class CmdHandlers:
    @staticmethod
    def ls(shell, args):
        long_format = False
        target_args = []
        for a in args:
            if a in ("-l", "-1"):
                long_format = True
            else:
                target_args.append(a)
        target = shell.current_dir / target_args[0] if target_args else shell.current_dir
        if not target.exists():
            raise FileNotFoundError(f"No such file or directory: {target}")
        if target.is_dir():
            entries = sorted(target.iterdir())
            for p in entries:
                if long_format:
                    st = p.stat()
                    size = st.st_size
                    mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    mode = stat.filemode(st.st_mode)
                    print(f"{mode} {size:>8} {mtime} {p.name}")
                else:
                    print(p.name)
        else:
            if long_format:
                st = target.stat()
                size = st.st_size
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                mode = stat.filemode(st.st_mode)
                print(f"{mode} {size:>8} {mtime} {target.name}")
            else:
                print(target.name)
        return None

    @staticmethod
    def cd(shell, args):
        if not args:
            new_dir = pathlib.Path.home()
        else:
            arg = args[0]
            if arg == "/":
                new_dir = pathlib.Path(shell.current_dir.anchor)
            elif arg == "~":
                new_dir = pathlib.Path.home()
            elif arg == "..":
                new_dir = shell.current_dir.parent
            else:
                new_dir = (shell.current_dir / arg).resolve()
        if new_dir.exists() and new_dir.is_dir():
            return new_dir
        else:
            raise FileNotFoundError(f"No such directory: {args[0] if args else '~'}")

    @staticmethod
    def cat(shell, args):
        if not args:
            raise ValueError("cat: missing file operand")
        file_path = shell.current_dir / args[0]
        if file_path.exists() and file_path.is_file():
            print(file_path.read_text(encoding="utf-8"))
        else:
            raise FileNotFoundError(f"cat: {args[0]}: No such file or directory")
        return None

    @staticmethod
    def cp(shell, args):
        recursive = False
        if args and args[0] == "-r":
            recursive = True
            args = args[1:]
        if len(args) != 2:
            raise ValueError("cp: missing source or destination")
        src = shell.current_dir / args[0]
        dst = shell.current_dir / args[1]
        if not src.exists():
            raise FileNotFoundError(f"cp: cannot stat '{args[0]}': No such file or directory")
        if dst.exists():
            raise FileExistsError(f"cp: destination '{args[1]}' exists")
        if src.is_dir() and not recursive:
            raise IsADirectoryError("cp: -r not specified; omitting directory")
        if recursive:
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        shell.last_undo = partial(shutil.rmtree if dst.is_dir() else os.remove, dst)
        return None

    @staticmethod
    def mv(shell, args):
        if len(args) != 2:
            raise ValueError("mv: missing source or destination")
        src = shell.current_dir / args[0]
        dst = shell.current_dir / args[1]
        if not src.exists():
            raise FileNotFoundError(f"mv: cannot stat '{args[0]}': No such file or directory")
        if dst.exists() and dst.is_dir():
            final_dst = dst / src.name
        else:
            final_dst = dst
        if final_dst.exists():
            raise FileExistsError(f"mv: destination '{final_dst}' exists")
        shutil.move(src, final_dst)
        shell.last_undo = partial(shutil.move, final_dst, src)
        return None

    @staticmethod
    def rm(shell, args):
        recursive = False
        if args and args[0] == "-r":
            recursive = True
            args = args[1:]
        if not args:
            raise ValueError("rm: missing operand")
        for arg in args:
            if arg == "..":
                raise PermissionError("rm: cannot remove parent directory")
            path = shell.current_dir / arg
            if not path.exists():
                raise FileNotFoundError(f"rm: cannot remove '{arg}': No such file or directory")
            if path.resolve() == pathlib.Path(path.anchor):
                raise PermissionError("rm: cannot remove root directory")
            if path.is_dir() and not recursive:
                raise IsADirectoryError(f"rm: cannot remove '{arg}': Is a directory")
            if path.is_dir() and recursive:
                confirm = input(f"rm: remove directory '{arg}'? (y/n) ")
                if confirm.lower() != "y":
                    continue
            trash_path = shell.trash_dir / path.name
            i = 1
            base_name = path.name
            while trash_path.exists():
                trash_path = shell.trash_dir / f"{base_name}_{i}"
                i += 1
            shutil.move(path, trash_path)
            shell.last_undo = partial(shutil.move, trash_path, path)
        return None

    @staticmethod
    def grep(shell, args):
        recursive = False
        ignore_case = False
        while args and args[0].startswith("-"):
            opt = args.pop(0)
            if "r" in opt:
                recursive = True
            if "i" in opt:
                ignore_case = True
        if len(args) != 2:
            raise ValueError("grep: usage: grep [-r] [-i] <pattern> <path>")
        pattern = args[0]
        path = shell.current_dir / args[1]
        if not path.exists():
            raise FileNotFoundError(f"grep: {args[1]} no such file or directory")
        flags = re.IGNORECASE if ignore_case else 0
        regex = re.compile(pattern, flags)
        def search_file(f):
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                return
            for lnum, line in enumerate(content.splitlines(), start=1):
                if regex.search(line):
                    rel_f = f.relative_to(shell.current_dir)
                    print(f"{rel_f}:{lnum}:{line}")
        if path.is_file():
            search_file(path)
        elif path.is_dir():
            if not recursive:
                raise IsADirectoryError("grep: is directory, use -r")
            for root, _, files in os.walk(path):
                for file in files:
                    f = pathlib.Path(root) / file
                    search_file(f)
        else:
            raise FileNotFoundError(f"grep: {args[1]} no such file or directory")
        return None

    @staticmethod
    def history(shell, args):
        n = int(args[0]) if args else None
        if shell.hist_file.exists():
            with open(shell.hist_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if n:
                lines = lines[-n:]
            for line in lines:
                print(line.strip())
        return None

    @staticmethod
    def undo(shell, args):
        if shell.last_undo:
            shell.last_undo()
            if shell.hist_file.exists():
                with open(shell.hist_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if lines:
                    lines = lines[:-1]
                    with open(shell.hist_file, "w", encoding="utf-8") as f:
                        f.writelines(lines)
            shell.last_undo = None
        else:
            print("No action to undo")
        return None

    @staticmethod
    def exit_cmd(shell, args):
        raise SystemExit
