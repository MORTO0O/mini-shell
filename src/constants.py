import pathlib
LOG_FILE = str(pathlib.Path(__file__).resolve().parent.parent / "shell.log")
HIST_FILE = ".history"
COUNTER_FILE = ".history_counter"
TRASH_DIR = ".trash"