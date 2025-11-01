# tests/test.py
import unittest
import unittest.mock as mock
from pathlib import Path
import os
import shutil
from src.shell import Shell, CmdHandlers

class TestShell(unittest.TestCase):
    def setUp(self):
        self.shell = Shell()
        self.temp_dir = Path("test_dir").resolve()
        self.temp_dir.mkdir(exist_ok=True)
        self.original_dir = Path.cwd()
        os.chdir(self.temp_dir)
        self.shell.current_dir = Path.cwd()

    def tearDown(self):
        os.chdir(self.original_dir)
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        if self.shell.hist_file.exists():
            os.remove(self.shell.hist_file)
        if self.shell.counter_file.exists():
            os.remove(self.shell.counter_file)

    def test_ls_command(self):
        (self.temp_dir / "file1.txt").touch()
        CmdHandlers.ls(self.shell, [])

    def test_ls_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.ls(self.shell, ["non_existent"])

    def test_cd_command(self):
        home = Path.home()
        new_dir = CmdHandlers.cd(self.shell, ["~"])
        self.assertEqual(new_dir, home)

    def test_cd_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.cd(self.shell, ["non_existent_dir"])

    def test_cat_command(self):
        file = self.temp_dir / "test.txt"
        file.write_text("Hello", encoding="utf-8")
        CmdHandlers.cat(self.shell, ["test.txt"])

    def test_cat_missing_arg(self):
        with self.assertRaises(ValueError):
            CmdHandlers.cat(self.shell, [])

    def test_cat_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.cat(self.shell, ["non_existent.txt"])

    def test_cp_command(self):
        src = self.temp_dir / "src.txt"
        src.touch()
        dst = self.temp_dir / "dst.txt"
        CmdHandlers.cp(self.shell, ["src.txt", "dst.txt"])
        self.assertTrue(dst.exists())
        CmdHandlers.undo(self.shell, [])
        self.assertFalse(dst.exists())

    def test_cp_recursive(self):
        src_dir = self.temp_dir / "src_dir"
        src_dir.mkdir()
        (src_dir / "file.txt").touch()
        dst_dir = self.temp_dir / "dst_dir"
        CmdHandlers.cp(self.shell, ["-r", "src_dir", "dst_dir"])
        self.assertTrue(dst_dir.exists())
        self.assertTrue((dst_dir / "file.txt").exists())

    def test_cp_missing_args(self):
        with self.assertRaises(ValueError):
            CmdHandlers.cp(self.shell, ["only_one"])

    def test_cp_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.cp(self.shell, ["non_existent", "dst"])

    def test_mv_command(self):
        src = self.temp_dir / "src.txt"
        src.touch()
        dst = self.temp_dir / "dst.txt"
        CmdHandlers.mv(self.shell, ["src.txt", "dst.txt"])
        self.assertFalse(src.exists())
        self.assertTrue(dst.exists())
        CmdHandlers.undo(self.shell, [])
        self.assertTrue(src.exists())
        self.assertFalse(dst.exists())

    def test_mv_missing_args(self):
        with self.assertRaises(ValueError):
            CmdHandlers.mv(self.shell, ["only_one"])

    def test_mv_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.mv(self.shell, ["non_existent", "dst"])

    def test_rm_command(self):
        file = self.temp_dir / "file.txt"
        file.touch()
        CmdHandlers.rm(self.shell, ["file.txt"])
        self.assertFalse(file.exists())
        CmdHandlers.undo(self.shell, [])
        self.assertTrue(file.exists())

    def test_rm_recursive(self):
        dir_to_rm = self.temp_dir / "dir_to_rm"
        dir_to_rm.mkdir()
        (dir_to_rm / "file.txt").touch()
        with mock.patch('builtins.input', return_value='y'):
            CmdHandlers.rm(self.shell, ["-r", "dir_to_rm"])
        self.assertFalse(dir_to_rm.exists())

    def test_rm_missing_args(self):
        with self.assertRaises(ValueError):
            CmdHandlers.rm(self.shell, [])

    def test_rm_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.rm(self.shell, ["non_existent"])

    def test_grep_command(self):
        file = self.temp_dir / "grep_test.txt"
        file.write_text("Line one\nLine two\nLine one again", encoding="utf-8")
        CmdHandlers.grep(self.shell, ["one", "grep_test.txt"])

    def test_grep_recursive(self):
        sub_dir = self.temp_dir / "sub_dir"
        sub_dir.mkdir()
        file = sub_dir / "file.txt"
        file.write_text("Search me", encoding="utf-8")
        CmdHandlers.grep(self.shell, ["-r", "Search", "."])

    def test_grep_missing_args(self):
        with self.assertRaises(ValueError):
            CmdHandlers.grep(self.shell, ["only_one"])

    def test_grep_non_existent(self):
        with self.assertRaises(FileNotFoundError):
            CmdHandlers.grep(self.shell, ["pattern", "non_existent"])

    def test_history_command(self):
        self.shell.global_counter = 1
        with open(self.shell.hist_file, "w", encoding="utf-8") as f:
            f.write("1. ls\n2. cd ~\n")
        CmdHandlers.history(self.shell, [])
        CmdHandlers.history(self.shell, ["1"])

    def test_undo_no_action(self):
        CmdHandlers.undo(self.shell, [])

    def test_exit_command(self):
        with self.assertRaises(SystemExit):
            CmdHandlers.exit_cmd(self.shell, [])