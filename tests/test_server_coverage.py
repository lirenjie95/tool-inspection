#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server 端覆盖率补充测试

Server-side coverage supplement tests.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 将 server 目录加入路径
# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import agent
from agent import t as agent_t, _safe_collect, get_health_data
from services.disk import collect as collect_disk, t as disk_t
from services.cpu import collect as collect_cpu, t as cpu_t
from services.memory import collect as collect_memory, t as memory_t


class TestAgentTranslation(unittest.TestCase):
    """测试 agent 翻译函数 t

    Tests for the agent translation function t.
    """

    def test_explicit_lang_with_kwargs(self):
        """测试显式指定语言并带格式化参数

        Test explicit language with format arguments.
        """
        result = agent_t("agent_started", lang="en", url="http://0.0.0.0:5000/health")
        self.assertIn("http://0.0.0.0:5000/health", result)

    def test_unknown_lang_falls_back_to_default(self):
        """测试未知语言回退到默认中文

        Test unknown language falls back to the default Chinese.
        """
        result = agent_t("not_found", lang="fr")
        self.assertEqual(result, agent.TRANSLATIONS[agent.DEFAULT_LANG]["not_found"])

    def test_unknown_key_returns_key(self):
        """测试未知 key 原样返回

        Test unknown key is returned as-is.
        """
        self.assertEqual(agent_t("no_such_key", lang="en"), "no_such_key")


class TestSafeCollect(unittest.TestCase):
    """测试 _safe_collect 函数

    Tests for the _safe_collect function.
    """

    def test_explicit_lang_passed_to_collector(self):
        """测试显式传入语言时直接使用该语言

        Test the explicitly passed language is used directly.
        """
        seen = {}

        def collector(lang=None):
            seen["lang"] = lang
            return {"ok": True}

        result = _safe_collect("demo", collector, lang="en")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(seen["lang"], "en")

    def test_default_lang_from_global(self):
        """测试未传语言时使用全局语言

        Test the global language is used when lang is omitted.
        """
        result = _safe_collect("demo", lambda lang=None: {"lang": lang})
        self.assertEqual(result, {"lang": agent._CURRENT_LANG})

    def test_exception_returns_error_dict(self):
        """测试采集异常被隔离并返回错误字典

        Test collection exceptions are isolated and an error dict is returned.
        """
        def collector(lang=None):
            raise RuntimeError("boom")

        result = _safe_collect("demo", collector, lang="zh")
        self.assertEqual(result, {"error": "boom"})


class TestGetHealthDataLang(unittest.TestCase):
    """测试 get_health_data 显式语言参数

    Tests for the get_health_data explicit language argument.
    """

    def test_explicit_lang(self):
        """测试传入 lang 时不再读取全局语言

        Test that passing lang skips reading the global language.
        """
        with patch("agent.collect_disk", return_value=[]) as mock_disk:
            with patch("agent.collect_cpu", return_value={"usage_percent": 10}):
                with patch("agent.collect_memory", return_value={"total_mb": 1, "free_mb": 1, "used_percent": 0}):
                    data = get_health_data(lang="en")
                    self.assertEqual(data["status"], "running")
                    mock_disk.assert_called_once_with(lang="en")


class TestParseArgs(unittest.TestCase):
    """测试 parse_args 命令行解析

    Tests for the parse_args command-line parsing.
    """

    def setUp(self):
        """保存全局语言以便恢复

        Save the global language for restoration.
        """
        self._old_lang = agent._CURRENT_LANG

    def tearDown(self):
        """恢复全局语言

        Restore the global language.
        """
        agent._CURRENT_LANG = self._old_lang

    def test_defaults(self):
        """测试默认参数

        Test default arguments.
        """
        with patch("sys.argv", ["agent.py"]):
            args = agent.parse_args()
            self.assertEqual(args.port, 5000)
            self.assertEqual(args.lang, "zh")
            self.assertEqual(agent._CURRENT_LANG, "zh")

    def test_custom_port_and_lang(self):
        """测试自定义端口与语言

        Test custom port and language.
        """
        with patch("sys.argv", ["agent.py", "--port", "8080", "--lang", "en"]):
            args = agent.parse_args()
            self.assertEqual(args.port, 8080)
            self.assertEqual(args.lang, "en")
            self.assertEqual(agent._CURRENT_LANG, "en")


class TestDiskServiceBranches(unittest.TestCase):
    """测试磁盘采集服务的边界分支

    Tests for edge branches of the disk collection service.
    """

    def test_t_without_kwargs(self):
        """测试翻译函数不带格式化参数

        Test translation function without format arguments.
        """
        self.assertIsInstance(disk_t("powershell_failed"), str)

    def test_windows_skips_invalid_lines(self):
        """测试 Windows 输出中空行、字段不足、非数字行被跳过

        Test blank lines, short lines and non-numeric lines are skipped in Windows output.
        """
        mock_output = "C:,45,100\n\nshort\nE:,x,y\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_disk()
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["DeviceID"], "C:")

    def test_linux_skips_short_lines(self):
        """测试 Linux 输出中字段不足的行被跳过，且无结果时返回占位

        Test short lines are skipped in Linux output and a placeholder is returned when empty.
        """
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "short line"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                result = collect_disk()
                self.assertEqual(result, [{"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0}])

    def test_linux_skips_special_mount_points(self):
        """测试 Linux 过滤 /dev、/sys、/proc 挂载点

        Test Linux filters out /dev, /sys, /proc mount points.
        """
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "udev 2G 0G 2G 0% /dev\n"
            "sysfs 0G 0G 0G 0% /sys\n"
            "proc 0G 0G 0G 0% /proc"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=True):
                    result = collect_disk()
                    self.assertEqual(result, [{"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0}])

    def test_linux_skips_non_mount_points(self):
        """测试 Linux 跳过非挂载点路径

        Test Linux skips paths that are not mount points.
        """
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "/dev/disk1 100G 30G 70G 30% /stale"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=False):
                    result = collect_disk()
                    self.assertEqual(result, [{"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0}])

    def test_linux_skips_unparseable_sizes(self):
        """测试 Linux 输出中容量无法解析的行被跳过

        Test lines with unparseable sizes are skipped in Linux output.
        """
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "/dev/disk1 XG 30G YG 30% /"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=True):
                    result = collect_disk()
                    self.assertEqual(result, [{"DeviceID": "/", "FreeSpaceGB": 0, "SizeGB": 0}])

    def test_linux_mount_point_with_spaces(self):
        """测试 Linux 挂载点含空格时正确拼接

        Test mount points containing spaces are joined correctly on Linux.
        """
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "/dev/disk1 100G 30G 70G 30% /my data dir"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=True):
                    result = collect_disk()
                    self.assertEqual(result[0]["DeviceID"], "/my data dir")


class TestCPUServiceBranches(unittest.TestCase):
    """测试 CPU 采集服务的边界分支

    Tests for edge branches of the CPU collection service.
    """

    def test_t_without_kwargs(self):
        """测试翻译函数不带格式化参数

        Test translation function without format arguments.
        """
        self.assertIsInstance(cpu_t("powershell_failed"), str)

    def test_windows_powershell_error(self):
        """测试 Windows PowerShell 失败时抛出异常

        Test that an exception is raised when Windows PowerShell fails.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="denied")
                with self.assertRaises(RuntimeError) as cm:
                    collect_cpu()
                self.assertIn("denied", str(cm.exception))

    def test_windows_skips_invalid_and_negative_lines(self):
        """测试 Windows 输出中空行、非数字行、负值行被跳过

        Test blank, non-numeric and negative lines are skipped in Windows output.
        """
        mock_output = "20\n-5\n\nabc\n30\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_cpu()
                self.assertEqual(result["usage_percent"], 25)

    def test_windows_no_valid_values(self):
        """测试 Windows 输出无有效值时返回 0

        Test 0 is returned when Windows output has no valid values.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="\nabc\n", stderr="")
                result = collect_cpu()
                self.assertEqual(result["usage_percent"], 0)

    def test_linux_bad_header(self):
        """测试 Linux /proc/stat 首行不是 cpu 时返回 0

        Test 0 is returned when the first /proc/stat line is not cpu.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("builtins.open") as mock_open:
                mock_open.return_value.__enter__.return_value.readline.return_value = "intr 123"
                result = collect_cpu()
                self.assertEqual(result["usage_percent"], 0)

    def test_linux_no_progress_between_reads(self):
        """测试 Linux 两次读取无变化时返回 0

        Test 0 is returned when there is no progress between the two Linux reads.
        """
        line = "cpu  100 0 0 100 0 0 0 0 0 0"
        with patch("platform.system", return_value="Linux"):
            with patch("time.sleep"):
                with patch("builtins.open") as mock_open:
                    mock_open.return_value.__enter__.return_value.readline.return_value = line
                    result = collect_cpu()
                    self.assertEqual(result["usage_percent"], 0)

    def test_linux_read_exception(self):
        """测试 Linux 读取 /proc/stat 异常时返回 0

        Test 0 is returned when reading /proc/stat raises.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("builtins.open", side_effect=OSError("no /proc")):
                result = collect_cpu()
                self.assertEqual(result["usage_percent"], 0)


class TestMemoryServiceBranches(unittest.TestCase):
    """测试内存采集服务的边界分支

    Tests for edge branches of the memory collection service.
    """

    def test_t_without_kwargs(self):
        """测试翻译函数不带格式化参数

        Test translation function without format arguments.
        """
        self.assertIsInstance(memory_t("powershell_failed"), str)

    def test_windows_powershell_error(self):
        """测试 Windows PowerShell 失败时抛出异常

        Test that an exception is raised when Windows PowerShell fails.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="denied")
                with self.assertRaises(RuntimeError) as cm:
                    collect_memory()
                self.assertIn("denied", str(cm.exception))

    def test_windows_incomplete_output(self):
        """测试 Windows 输出缺少字段时返回全 0

        Test all-zero result when Windows output lacks fields.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="8388608\n", stderr="")
                result = collect_memory()
                self.assertEqual(result, {"total_mb": 0, "free_mb": 0, "used_percent": 0})

    def test_windows_non_numeric_output(self):
        """测试 Windows 输出非数字时返回全 0

        Test all-zero result when Windows output is non-numeric.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="abc,def\n", stderr="")
                result = collect_memory()
                self.assertEqual(result, {"total_mb": 0, "free_mb": 0, "used_percent": 0})

    def test_linux_too_few_lines(self):
        """测试 Linux free 输出行数不足时返回全 0

        Test all-zero result when Linux free output has too few lines.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="              total        used"):
                result = collect_memory()
                self.assertEqual(result, {"total_mb": 0, "free_mb": 0, "used_percent": 0})

    def test_linux_too_few_fields(self):
        """测试 Linux free 输出字段不足时返回全 0

        Test all-zero result when Linux free output has too few fields.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="header\nMem: 8192"):
                result = collect_memory()
                self.assertEqual(result, {"total_mb": 0, "free_mb": 0, "used_percent": 0})

    def test_linux_command_exception(self):
        """测试 Linux free 命令异常时返回全 0

        Test all-zero result when the Linux free command raises.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", side_effect=OSError("no free")):
                result = collect_memory()
                self.assertEqual(result, {"total_mb": 0, "free_mb": 0, "used_percent": 0})


if __name__ == "__main__":
    unittest.main()
