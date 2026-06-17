#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Client 端单元测试

Client-side unit tests.
"""

import sys
import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# 将 client 目录加入路径
# Add the client directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

from main import (
    check_server_agent,
    format_disk_line,
    format_metrics,
    check_web,
    inspect_server,
    run_inspection,
    load_config,
    main,
)


class TestCheckServerAgent(unittest.TestCase):
    """测试 check_server_agent 函数

    Tests for the check_server_agent function.
    """

    @patch("main.requests.get")
    def test_success(self, mock_get):
        """测试正常响应

        Test successful response.
        """
        mock_get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "running", "disks": []}
        )
        server = {"ip": "192.168.1.10", "port": 5000}
        result = check_server_agent(server)
        self.assertTrue(result["_http_ok"])
        self.assertEqual(result["status"], "running")

    @patch("main.requests.get")
    def test_timeout(self, mock_get):
        """测试连接超时

        Test connection timeout.
        """
        mock_get.side_effect = Exception("Connection timeout")
        server = {"ip": "192.168.1.10", "port": 5000}
        result = check_server_agent(server)
        self.assertFalse(result["_http_ok"])
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("timeout", result["error"])


class TestFormatDiskLine(unittest.TestCase):
    """测试 format_disk_line 函数

    Tests for the format_disk_line function.
    """

    def test_windows_disks(self):
        """测试 Windows 磁盘格式化

        Test Windows disk formatting.
        """
        disks = [
            {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
            {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200},
        ]
        result = format_disk_line(disks)
        self.assertIn("C盘剩余：45 GB", result)
        self.assertIn("D盘剩余：120 GB", result)

    def test_linux_disks(self):
        """测试 Linux 磁盘格式化

        Test Linux disk formatting.
        """
        disks = [
            {"DeviceID": "/", "FreeSpaceGB": 10, "SizeGB": 50},
        ]
        result = format_disk_line(disks)
        self.assertIn("/剩余：10 GB", result)

    def test_empty_disks(self):
        """测试空磁盘列表

        Test empty disk list.
        """
        result = format_disk_line([])
        self.assertEqual(result, "")

    def test_windows_disks_english(self):
        """测试英文 Windows 磁盘格式化

        Test English Windows disk formatting.
        """
        disks = [
            {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
            {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200},
        ]
        result = format_disk_line(disks, lang="en")
        self.assertIn("C: 45 GB free", result)
        self.assertIn("D: 120 GB free", result)


class TestFormatMetrics(unittest.TestCase):
    """测试 format_metrics 函数

    Tests for the format_metrics function.
    """

    def test_with_cpu_and_memory(self):
        """测试同时有 CPU 和内存数据

        Test with both CPU and memory data present.
        """
        data = {
            "cpu": {"usage_percent": 45.5},
            "memory": {"used_percent": 60.0},
        }
        result = format_metrics(data)
        self.assertIn("CPU: 45.5%", result)
        self.assertIn("内存: 60.0%", result)

    def test_without_metrics(self):
        """测试没有指标数据

        Test with no metric data.
        """
        result = format_metrics({})
        self.assertEqual(result, "")

    def test_with_cpu_and_memory_english(self):
        """测试英文 CPU 和内存格式化

        Test English CPU and memory formatting.
        """
        data = {
            "cpu": {"usage_percent": 45.5},
            "memory": {"used_percent": 60.0},
        }
        result = format_metrics(data, lang="en")
        self.assertIn("CPU: 45.5%", result)
        self.assertIn("Memory: 60.0%", result)


class TestCheckWeb(unittest.TestCase):
    """测试 check_web 函数

    Tests for the check_web function.
    """

    @patch("main.requests.get")
    def test_success(self, mock_get):
        """测试网页正常打开

        Test web page opens successfully.
        """
        mock_get.return_value = MagicMock(status_code=200)
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertTrue(result["reachable"])
        self.assertEqual(result["code"], 200)
        self.assertEqual(result["status"], "正常打开")
        # 确认跟随重定向参数已传入
        # Confirm the follow-redirects parameter was passed
        mock_get.assert_called_once_with(
            "http://example.com", timeout=20, allow_redirects=True
        )

    @patch("main.requests.get")
    def test_not_200(self, mock_get):
        """测试网页返回非 200

        Test web page returns non-200 status.
        """
        mock_get.return_value = MagicMock(status_code=500)
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertFalse(result["reachable"])
        self.assertEqual(result["code"], 500)
        self.assertEqual(result["status"], "HTTP 500")

    @patch("main.requests.get")
    def test_exception(self, mock_get):
        """测试请求异常

        Test request exception.
        """
        mock_get.side_effect = Exception("DNS error")
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertFalse(result["reachable"])
        self.assertIsNone(result["code"])
        self.assertIn("DNS error", result["status"])


class TestLoadConfig(unittest.TestCase):
    """测试 load_config 函数

    Tests for the load_config function.
    """

    def test_load_default_config(self):
        """测试加载默认配置文件

        Test loading the default config file.
        """
        config_path = os.path.join(
            os.path.dirname(__file__), "..", "client", "config.json"
        )
        config = load_config(config_path)
        self.assertTrue(hasattr(config, "SERVERS"))
        self.assertTrue(hasattr(config, "WEBS"))
        self.assertTrue(hasattr(config, "DISK_THRESHOLD_GB"))

    def test_load_missing_config(self):
        """测试加载不存在的配置文件

        Test loading a non-existent config file.
        """
        with self.assertRaises(FileNotFoundError):
            load_config("nonexistent_config.json")

    def test_load_non_json_config(self):
        """测试加载非 JSON 配置文件时抛出错误

        Test that loading a non-JSON config file raises an error.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write("SERVERS = []\n")
            path = f.name
        try:
            with self.assertRaises(ValueError):
                load_config(path)
        finally:
            os.unlink(path)

    def test_load_json_config(self):
        """测试加载 JSON 配置文件

        Test loading a JSON config file.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            import json as _json
            _json.dump(
                {
                    "SERVERS": [
                        {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"}
                    ],
                    "WEBS": [{"name": "首页", "url": "http://example.com"}],
                    "DISK_THRESHOLD_GB": 50,
                    "ROLE_DISK_THRESHOLDS_GB": {"db": 80},
                },
                f,
            )
            path = f.name
        try:
            config = load_config(path)
            self.assertEqual(len(config.SERVERS), 1)
            self.assertEqual(config.SERVERS[0]["ip"], "192.168.1.10")
            self.assertEqual(config.DISK_THRESHOLD_GB, 50)
            self.assertEqual(config.ROLE_DISK_THRESHOLDS_GB["db"], 80)
        finally:
            os.unlink(path)


class TestInspectServer(unittest.TestCase):
    """测试 inspect_server 函数

    Tests for the inspect_server function.
    """

    def test_healthy(self):
        """测试健康服务器

        Test a healthy server.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertIn("app-01 (192.168.1.10)", lines[0])
        self.assertTrue(any("总磁盘空间检查: 通过" in line for line in lines))
        self.assertEqual(len(warnings), 0)

    def test_low_disk(self):
        """测试磁盘低于阈值

        Test disk below threshold.
        """
        srv = {"ip": "192.168.1.20", "port": 5000, "name": "db-01", "role": "db"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 10, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("[告警] 总磁盘空间低于阈值" in line for line in lines))
        self.assertEqual(len(warnings), 1)
        self.assertIn("总磁盘空间不足", warnings[0])

    def test_role_threshold(self):
        """测试角色使用更高的阈值

        Test role using a higher threshold.
        """
        srv = {"ip": "192.168.1.20", "port": 5000, "name": "db-01", "role": "db"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 40, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(
            srv,
            data,
            disk_threshold_gb=30,
            role_disk_thresholds_gb={"db": 50},
        )
        self.assertTrue(any("[告警] 总磁盘空间低于阈值 (50GB)" in line for line in lines))
        self.assertEqual(len(warnings), 1)

    def test_total_disk_above_threshold_single_disk_below(self):
        """测试按总磁盘空间判断：单个盘低于阈值但合计高于阈值时应通过

        Test total-disk-space check: should pass when a single disk is below threshold but the total is above.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [
                {"DeviceID": "C:", "FreeSpaceGB": 20, "SizeGB": 100},
                {"DeviceID": "D:", "FreeSpaceGB": 20, "SizeGB": 100},
            ],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("总磁盘空间检查: 通过" in line for line in lines))
        self.assertEqual(len(warnings), 0)

    def test_total_disk_below_threshold(self):
        """测试按总磁盘空间判断：合计低于阈值时应告警

        Test total-disk-space check: should warn when the total is below threshold.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [
                {"DeviceID": "C:", "FreeSpaceGB": 10, "SizeGB": 100},
                {"DeviceID": "D:", "FreeSpaceGB": 15, "SizeGB": 100},
            ],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("[告警] 总磁盘空间低于阈值 (30GB)" in line for line in lines))
        self.assertEqual(len(warnings), 1)
        self.assertIn("总磁盘空间不足", warnings[0])

    def test_unreachable(self):
        """测试不可达服务器

        Test unreachable server.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {"_http_ok": False, "status": "unreachable", "error": "timeout"}
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertIn("timeout", lines[0])
        self.assertEqual(len(warnings), 1)
        self.assertIn("不可达", warnings[0])

    def test_no_disks(self):
        """测试无磁盘数据

        Test no disk data.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {"_http_ok": True, "status": "running", "disks": []}
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("运行正常" in line for line in lines))
        self.assertTrue(any("[告警] 总磁盘空间低于阈值" in line for line in lines))
        self.assertEqual(len(warnings), 1)

    def test_disk_collection_error(self):
        """测试磁盘采集失败时客户端不崩溃

        Test client does not crash when disk collection fails.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": {"error": "PowerShell execution failed"},
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertTrue(any("磁盘采集失败" in line for line in lines))
        self.assertEqual(len(warnings), 1)
        self.assertIn("总磁盘空间不足", warnings[0])

    def test_without_name(self):
        """测试没有 name 字段的服务器

        Test server without a name field.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30)
        self.assertIn("192.168.1.10 (192.168.1.10)", lines[0])


class TestRunInspection(unittest.TestCase):
    """测试 run_inspection 完整流程

    Tests for the full run_inspection flow.
    """

    def _make_config(self, servers, webs, threshold=30, role_thresholds=None):
        """构造 run_inspection 参数

        Construct arguments for run_inspection.
        """
        return {
            "servers": servers,
            "webs": webs,
            "disk_threshold_gb": threshold,
            "role_disk_thresholds_gb": role_thresholds or {},
        }

    @patch("main.check_server_agent")
    @patch("main.check_web")
    def test_all_normal(self, mock_check_web, mock_check_server):
        """测试全部正常流程

        Test the all-normal flow.
        """
        cfg = self._make_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
                {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
            ],
            webs=[{"name": "首页", "url": "http://example.com"}],
        )
        mock_check_server.side_effect = [
            {
                "_http_ok": True,
                "status": "running",
                "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
            },
            {
                "_http_ok": True,
                "status": "running",
                "disks": [{"DeviceID": "D:", "FreeSpaceGB": 100, "SizeGB": 200}],
            },
        ]
        mock_check_web.return_value = {
            "reachable": True,
            "status": "正常打开",
            "code": 200,
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("服务器巡检开始", output_text)
        self.assertIn("app-01 (192.168.1.10)", output_text)
        self.assertIn("db-01 (192.168.1.20)", output_text)
        self.assertIn("总磁盘空间检查: 通过", output_text)
        self.assertIn("所有巡检项均正常", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 0)

    @patch("main.check_server_agent")
    def test_app_unreachable(self, mock_check_server):
        """测试应用服务器不可达

        Test application server unreachable.
        """
        cfg = self._make_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": False,
            "status": "unreachable",
            "error": "timeout",
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("不可达", output_text)
        self.assertIn("共发现 1 项异常", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 1)

    @patch("main.check_server_agent")
    def test_db_low_disk(self, mock_check_server):
        """测试数据库服务器磁盘低于阈值

        Test database server disk below threshold.
        """
        cfg = self._make_config(
            servers=[
                {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 10, "SizeGB": 100}],
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("[告警] 总磁盘空间低于阈值", output_text)
        self.assertIn("总磁盘空间不足", output_text)
        self.assertIn("共发现 1 项异常", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 1)

    @patch("main.check_server_agent")
    def test_db_role_threshold(self, mock_check_server):
        """测试数据库角色使用更高的阈值

        Test database role using a higher threshold.
        """
        cfg = self._make_config(
            servers=[
                {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
            ],
            webs=[],
            role_thresholds={"db": 50},
        )
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 40, "SizeGB": 100}],
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("[告警] 总磁盘空间低于阈值 (50GB)", output_text)
        self.assertIn("总磁盘空间不足", output_text)
        self.assertIn("共发现 1 项异常", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 1)

    @patch("main.check_server_agent")
    def test_no_disks(self, mock_check_server):
        """测试无磁盘数据分支

        Test no-disk-data branch.
        """
        cfg = self._make_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [],
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("运行正常", output_text)
        self.assertIn("[告警] 总磁盘空间低于阈值", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 1)

    @patch("main.check_web")
    def test_web_unreachable(self, mock_check_web):
        """测试网页不可达

        Test web page unreachable.
        """
        cfg = self._make_config(
            servers=[],
            webs=[{"name": "首页", "url": "http://example.com"}],
        )
        mock_check_web.return_value = {
            "reachable": False,
            "status": "DNS error",
            "code": None,
        }

        output_text, structured = run_inspection(**cfg)
        self.assertIn("DNS error", output_text)
        self.assertIn("网页 首页: DNS error", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 1)


class TestMain(unittest.TestCase):
    """测试 main() 函数完整流程

    Tests for the full main() flow.
    """

    def setUp(self):
        """每个测试前清空命令行参数，避免 argparse 读取 pytest 参数

        Clear command-line arguments before each test to prevent argparse from reading pytest arguments.
        """
        self.argv_patcher = patch("sys.argv", ["main.py"])
        self.argv_patcher.start()

    def tearDown(self):
        """恢复命令行参数

        Restore command-line arguments.
        """
        self.argv_patcher.stop()

    def _make_mock_config(self, servers, webs, threshold=30, role_thresholds=None):
        """构造模拟配置对象

        Construct a mock config object.
        """
        mock_config = MagicMock()
        mock_config.SERVERS = servers
        mock_config.WEBS = webs
        mock_config.DISK_THRESHOLD_GB = threshold
        mock_config.ROLE_DISK_THRESHOLDS_GB = role_thresholds or {}
        return mock_config

    @patch("main.check_server_agent")
    @patch("main.check_web")
    def test_all_normal(self, mock_check_web, mock_check_server):
        """测试全部正常流程

        Test the all-normal flow.
        """
        mock_config = self._make_mock_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
                {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
            ],
            webs=[{"name": "首页", "url": "http://example.com"}],
        )
        mock_check_server.side_effect = [
            {
                "_http_ok": True,
                "status": "running",
                "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
            },
            {
                "_http_ok": True,
                "status": "running",
                "disks": [{"DeviceID": "D:", "FreeSpaceGB": 100, "SizeGB": 200}],
            },
        ]
        mock_check_web.return_value = {
            "reachable": True,
            "status": "正常打开",
            "code": 200,
        }

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            with patch("main.load_config", return_value=mock_config):
                main()
        output = captured.getvalue()
        self.assertIn("服务器巡检开始", output)
        self.assertIn("总磁盘空间检查: 通过", output)
        self.assertIn("所有巡检项均正常", output)

    @patch("main.check_server_agent")
    def test_app_unreachable(self, mock_check_server):
        """测试应用服务器不可达

        Test application server unreachable.
        """
        mock_config = self._make_mock_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": False,
            "status": "unreachable",
            "error": "timeout",
        }

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            with patch("main.load_config", return_value=mock_config):
                main()
        output = captured.getvalue()
        self.assertIn("不可达", output)
        self.assertIn("共发现 1 项异常", output)

    @patch("main.check_server_agent")
    def test_db_low_disk(self, mock_check_server):
        """测试数据库服务器磁盘低于阈值

        Test database server disk below threshold.
        """
        mock_config = self._make_mock_config(
            servers=[
                {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 10, "SizeGB": 100}],
        }

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            with patch("main.load_config", return_value=mock_config):
                main()
        output = captured.getvalue()
        self.assertIn("[告警] 总磁盘空间低于阈值", output)
        self.assertIn("总磁盘空间不足", output)
        self.assertIn("共发现 1 项异常", output)

    @patch("main.check_server_agent")
    def test_no_disks(self, mock_check_server):
        """测试无磁盘数据分支

        Test no-disk-data branch.
        """
        mock_config = self._make_mock_config(
            servers=[
                {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
            ],
            webs=[],
        )
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [],
        }

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            with patch("main.load_config", return_value=mock_config):
                main()
        output = captured.getvalue()
        self.assertIn("运行正常", output)
        self.assertIn("[告警] 总磁盘空间低于阈值", output)

    @patch("main.check_web")
    def test_web_unreachable(self, mock_check_web):
        """测试网页不可达

        Test web page unreachable.
        """
        mock_config = self._make_mock_config(
            servers=[],
            webs=[{"name": "首页", "url": "http://example.com"}],
        )
        mock_check_web.return_value = {
            "reachable": False,
            "status": "DNS error",
            "code": None,
        }

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            with patch("main.load_config", return_value=mock_config):
                main()
        output = captured.getvalue()
        self.assertIn("DNS error", output)
        self.assertIn("网页 首页: DNS error", output)


class TestEnglishOutput(unittest.TestCase):
    """测试英文输出

    Tests for English output.
    """

    def test_inspect_server_healthy_english(self):
        """测试英文健康服务器输出

        Test English output for a healthy server.
        """
        srv = {"ip": "192.168.1.10", "port": 5000, "name": "app-01", "role": "app"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30, lang="en")
        self.assertIn("app-01 (192.168.1.10)", lines[0])
        self.assertTrue(any("Total disk space check: PASSED" in line for line in lines))
        self.assertEqual(len(warnings), 0)

    def test_inspect_server_low_disk_english(self):
        """测试英文磁盘低于阈值输出

        Test English output for low disk space.
        """
        srv = {"ip": "192.168.1.20", "port": 5000, "name": "db-01", "role": "db"}
        data = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "D:", "FreeSpaceGB": 10, "SizeGB": 100}],
        }
        lines, warnings = inspect_server(srv, data, disk_threshold_gb=30, lang="en")
        self.assertTrue(any("[WARNING] Total disk space below threshold" in line for line in lines))
        self.assertEqual(len(warnings), 1)
        self.assertIn("insufficient total disk space", warnings[0])

    @patch("main.check_server_agent")
    @patch("main.check_web")
    def test_run_inspection_all_normal_english(self, mock_check_web, mock_check_server):
        """测试英文完整巡检正常流程

        Test English full inspection normal flow.
        """
        servers = [
            {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
        ]
        webs = [{"name": "Home", "url": "http://example.com"}]
        mock_check_server.return_value = {
            "_http_ok": True,
            "status": "running",
            "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}],
        }
        mock_check_web.return_value = {
            "reachable": True,
            "status": "OK",
            "code": 200,
        }

        output_text, structured = run_inspection(
            servers=servers, webs=webs, disk_threshold_gb=30, lang="en"
        )
        self.assertIn("Server Inspection Started", output_text)
        self.assertIn("App Server Inspection", output_text)
        self.assertIn("Total disk space check: PASSED", output_text)
        self.assertIn("All inspection items are normal", output_text)
        self.assertEqual(structured["summary"]["total_warnings"], 0)


if __name__ == "__main__":
    unittest.main()
