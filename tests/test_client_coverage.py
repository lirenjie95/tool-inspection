#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Client 端覆盖率补充测试

Client-side coverage supplement tests.
"""

import io
import json
import sys
import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# 将 client 目录加入路径
# Add the client directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

from main import (
    load_config,
    _load_default_config,
    check_all_servers,
    format_disk_line,
    inspect_server,
    run_inspection,
    main,
)


class TestJsonConfigFallbacks(unittest.TestCase):
    """测试 _JsonConfig 兼容分支

    Tests for _JsonConfig compatibility branches.
    """

    def _write_config(self, data):
        """写入临时 JSON 配置文件

        Write a temporary JSON config file.
        """
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(data, f)
        f.close()
        return f.name

    def test_role_thresholds_default_empty(self):
        """测试未配置角色阈值时返回空字典

        Test an empty dict is returned when role thresholds are not configured.
        """
        path = self._write_config(
            {"SERVERS": [], "WEBS": [], "DISK_THRESHOLD_GB": 30}
        )
        try:
            config = load_config(path)
            self.assertEqual(config.ROLE_DISK_THRESHOLDS_GB, {})
        finally:
            os.unlink(path)

    def test_missing_key_raises_attribute_error(self):
        """测试访问缺失配置项时抛出 AttributeError

        Test accessing a missing config key raises AttributeError.
        """
        path = self._write_config(
            {"SERVERS": [], "WEBS": [], "DISK_THRESHOLD_GB": 30}
        )
        try:
            config = load_config(path)
            with self.assertRaises(AttributeError):
                config.NO_SUCH_KEY
        finally:
            os.unlink(path)


class TestLoadDefaultConfigFrozen(unittest.TestCase):
    """测试 _load_default_config 打包（frozen）运行分支

    Tests for the _load_default_config frozen-run branches.
    """

    def test_frozen_prefers_config_next_to_exe(self):
        """测试打包运行时优先使用 exe 旁的 config.json

        Test frozen run prefers the config.json next to the exe.
        """
        sentinel = object()
        with patch.multiple(sys, frozen=True, executable="/fake/dir/app.exe", create=True):
            with patch("main.os.path.isfile", side_effect=lambda p: p == os.path.join("/fake/dir", "config.json")):
                with patch("main.load_config", return_value=sentinel) as mock_load:
                    result = _load_default_config()
                    self.assertIs(result, sentinel)
                    mock_load.assert_called_once_with(os.path.join("/fake/dir", "config.json"))

    def test_frozen_falls_back_to_meipass(self):
        """测试打包运行时 exe 旁无配置则回退到 _MEIPASS 内置配置

        Test frozen run falls back to the bundled _MEIPASS config
        when no config sits next to the exe.
        """
        sentinel = object()
        meipass_path = os.path.join("/fake/meipass", "config.json")
        with patch.multiple(sys, frozen=True, executable="/fake/dir/app.exe", _MEIPASS="/fake/meipass", create=True):
            with patch("main.os.path.isfile", side_effect=lambda p: p == meipass_path):
                with patch("main.load_config", return_value=sentinel) as mock_load:
                    result = _load_default_config()
                    self.assertIs(result, sentinel)
                    mock_load.assert_called_once_with(meipass_path)

    def test_frozen_no_config_falls_back_to_source_dir(self):
        """测试打包运行时无任何候选配置则回退到源码目录默认配置

        Test frozen run falls back to the source-directory default config
        when no candidate config exists.
        """
        sentinel = object()
        with patch.multiple(sys, frozen=True, executable="/fake/dir/app.exe", _MEIPASS="/fake/meipass", create=True):
            with patch("main.os.path.isfile", return_value=False):
                with patch("main.load_config", return_value=sentinel) as mock_load:
                    result = _load_default_config()
                    self.assertIs(result, sentinel)
                    import main as client_main
                    mock_load.assert_called_once_with(
                        os.path.join(os.path.dirname(client_main.__file__), "config.json")
                    )


class TestCheckAllServers(unittest.TestCase):
    """测试 check_all_servers 异常分支

    Tests for the check_all_servers exception branch.
    """

    def test_future_exception_marked_unreachable(self):
        """测试单个服务器采集抛异常时标记为不可达且不影响其他服务器

        Test a server whose collection raises is marked unreachable
        without affecting the other servers.
        """
        servers = [
            {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"},
            {"ip": "192.168.1.20", "port": 5000, "name": "db-01", "role": "db"},
        ]

        def side_effect(srv):
            if srv["name"] == "app-01":
                raise RuntimeError("unexpected")
            return {"status": "running", "_http_ok": True}

        with patch("main.check_server_agent", side_effect=side_effect):
            results = check_all_servers(servers)
            # 按原始顺序返回 / Preserve original order
            self.assertEqual([s["name"] for s, _ in results], ["app-01", "db-01"])
            app_data = results[0][1]
            self.assertFalse(app_data["_http_ok"])
            self.assertEqual(app_data["status"], "unreachable")
            self.assertIn("unexpected", app_data["error"])
            self.assertTrue(results[1][1]["_http_ok"])


class TestFormatDiskLineBranches(unittest.TestCase):
    """测试 format_disk_line 边界分支

    Tests for format_disk_line edge branches.
    """

    def test_skips_non_dict_items(self):
        """测试非字典元素被跳过

        Test non-dict items are skipped.
        """
        disks = ["garbage", None, {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100}]
        result = format_disk_line(disks)
        self.assertEqual(result, "C盘剩余：45 GB")


class TestInspectServerBranches(unittest.TestCase):
    """测试 inspect_server 边界分支

    Tests for inspect_server edge branches.
    """

    def test_default_threshold_from_config(self):
        """测试未传磁盘阈值时从默认配置加载

        Test the disk threshold is loaded from the default config when omitted.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        mock_config = MagicMock()
        mock_config.DISK_THRESHOLD_GB = 30
        with patch("main._load_default_config", return_value=mock_config) as mock_load:
            lines, warnings = inspect_server(srv, data)
            mock_load.assert_called_once()
            self.assertTrue(any("总磁盘空间检查: 通过" in line for line in lines))
            self.assertEqual(len(warnings), 0)

    def test_metrics_line_output(self):
        """测试有 CPU/内存指标时输出指标行

        Test the metrics line is output when CPU/memory metrics are present.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
            "cpu": {"usage_percent": 12.5},
            "memory": {"used_percent": 34.0},
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("CPU: 12.5%" in line and "内存: 34.0%" in line for line in lines))
        self.assertEqual(len(warnings), 0)

    def test_no_metrics_line_when_metrics_missing(self):
        """测试无 CPU/内存指标时不输出指标行

        Test no metrics line is output when CPU/memory metrics are missing.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertFalse(any("CPU" in line for line in lines))
        self.assertEqual(len(warnings), 0)


class TestRunInspectionDefaults(unittest.TestCase):
    """测试 run_inspection 默认参数分支

    Tests for the run_inspection default-argument branches.
    """

    def _make_default_config(self):
        """构造模拟默认配置

        Construct a mock default config.
        """
        mock_config = MagicMock()
        mock_config.SERVERS = []
        mock_config.WEBS = []
        mock_config.DISK_THRESHOLD_GB = 30
        mock_config.ROLE_DISK_THRESHOLDS_GB = {}
        return mock_config

    def test_all_defaults_loaded_from_config(self):
        """测试全部参数缺省时从默认配置加载

        Test all defaults are loaded from the default config when omitted.
        """
        mock_config = self._make_default_config()
        with patch("main._load_default_config", return_value=mock_config) as mock_load:
            with patch("main.check_all_servers", return_value=[]):
                output_text, structured = run_inspection()
                # 加载一次后复用同一个 default_cfg
                # The same default_cfg is reused after the first load
                self.assertEqual(mock_load.call_count, 1)
                self.assertIn("服务器巡检开始", output_text)
                self.assertEqual(structured["summary"]["total_warnings"], 0)

    def test_partial_defaults(self):
        """测试部分参数缺省时复用已加载的默认配置

        Test the loaded default config is reused when only some arguments are omitted.
        """
        mock_config = self._make_default_config()
        with patch("main._load_default_config", return_value=mock_config) as mock_load:
            with patch("main.check_all_servers", return_value=[]):
                output_text, structured = run_inspection(servers=[], webs=[])
                # servers/webs 已提供，仅加载阈值两项
                # servers/webs provided; only the two thresholds are loaded
                self.assertEqual(mock_load.call_count, 1)
                self.assertEqual(structured["summary"]["total_warnings"], 0)

    def test_unknown_role_uses_suffix_display(self):
        """测试未知角色使用通用显示名

        Test an unknown role uses the generic display name.
        """
        servers = [
            {"role": "cache", "ip": "192.168.1.30", "port": 5000, "name": "cache-01"},
        ]
        with patch("main.check_server_agent", return_value={"_http_ok": True, "status": "running", "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}]}):
            output_text, structured = run_inspection(
                servers=servers, webs=[], disk_threshold_gb=30
            )
            self.assertIn("cache 服务器巡检", output_text)


class TestMainOutput(unittest.TestCase):
    """测试 main() 输出报告分支

    Tests for the main() report-output branches.
    """

    def _make_mock_config(self):
        """构造模拟配置对象

        Construct a mock config object.
        """
        mock_config = MagicMock()
        mock_config.SERVERS = []
        mock_config.WEBS = []
        mock_config.DISK_THRESHOLD_GB = 30
        mock_config.ROLE_DISK_THRESHOLDS_GB = {}
        return mock_config

    def _run_main(self, argv):
        """运行 main 并捕获输出

        Run main and capture its output.
        """
        captured = io.StringIO()
        captured_err = io.StringIO()
        with patch("main.load_config", return_value=self._make_mock_config()):
            with patch("main.check_all_servers", return_value=[]):
                with patch("sys.stdout", new=captured):
                    with patch("sys.stderr", new=captured_err):
                        main(argv)
        return captured.getvalue(), captured_err.getvalue()

    def test_output_text_report(self):
        """测试 --output 保存文本报告

        Test --output saves a text report.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "report.txt")
            stdout, stderr = self._run_main(["--output", out_path])
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, "r", encoding="utf-8") as f:
                self.assertIn("服务器巡检开始", f.read())
            self.assertIn("巡检报告已保存到", stdout)
            self.assertEqual(stderr, "")

    def test_output_json_report(self):
        """测试 --output 保存 JSON 报告

        Test --output saves a JSON report.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "report.json")
            stdout, stderr = self._run_main(["--output", out_path])
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("summary", data)
            self.assertEqual(data["summary"]["total_warnings"], 0)
            self.assertIn("巡检报告已保存到", stdout)

    def test_output_save_failure(self):
        """测试保存报告失败时输出错误信息

        Test a save failure prints an error message.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # 以目录作为输出路径，触发写入异常
            # Use a directory as the output path to trigger a write error
            stdout, stderr = self._run_main(["--output", tmpdir])
            self.assertIn("保存报告失败", stderr)


if __name__ == "__main__":
    unittest.main()
