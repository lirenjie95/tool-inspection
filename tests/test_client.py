#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Client 端单元测试"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 将 client 目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "client"))

from main import check_server_agent, format_disk_line, check_web, main


class TestCheckServerAgent(unittest.TestCase):
    """测试 check_server_agent 函数"""

    @patch("main.requests.get")
    def test_success(self, mock_get):
        """测试正常响应"""
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"status": "running", "disks": []})
        server = {"ip": "192.168.1.10", "port": 5000}
        result = check_server_agent(server)
        self.assertTrue(result["_http_ok"])
        self.assertEqual(result["status"], "running")

    @patch("main.requests.get")
    def test_timeout(self, mock_get):
        """测试连接超时"""
        mock_get.side_effect = Exception("Connection timeout")
        server = {"ip": "192.168.1.10", "port": 5000}
        result = check_server_agent(server)
        self.assertFalse(result["_http_ok"])
        self.assertEqual(result["status"], "unreachable")
        self.assertIn("timeout", result["error"])


class TestFormatDiskLine(unittest.TestCase):
    """测试 format_disk_line 函数"""

    def test_windows_disks(self):
        """测试 Windows 磁盘格式化"""
        disks = [
            {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
            {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200},
        ]
        result = format_disk_line("192.168.1.10", disks)
        self.assertIn("192.168.1.10", result)
        self.assertIn("C盘剩余：45 GB", result)
        self.assertIn("D盘剩余：120 GB", result)

    def test_linux_disks(self):
        """测试 Linux 磁盘格式化"""
        disks = [
            {"DeviceID": "/", "FreeSpaceGB": 10, "SizeGB": 50},
        ]
        result = format_disk_line("192.168.1.20", disks)
        self.assertIn("192.168.1.20", result)
        self.assertIn("/剩余：10 GB", result)

    def test_empty_disks(self):
        """测试空磁盘列表"""
        result = format_disk_line("192.168.1.10", [])
        self.assertEqual(result, "192.168.1.10")


class TestCheckWeb(unittest.TestCase):
    """测试 check_web 函数"""

    @patch("main.requests.get")
    def test_success(self, mock_get):
        """测试网页正常打开"""
        mock_get.return_value = MagicMock(status_code=200)
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertTrue(result["reachable"])
        self.assertEqual(result["code"], 200)
        self.assertEqual(result["status"], "正常打开")

    @patch("main.requests.get")
    def test_not_200(self, mock_get):
        """测试网页返回非 200"""
        mock_get.return_value = MagicMock(status_code=500)
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertFalse(result["reachable"])
        self.assertEqual(result["code"], 500)
        self.assertEqual(result["status"], "HTTP 500")

    @patch("main.requests.get")
    def test_exception(self, mock_get):
        """测试请求异常"""
        mock_get.side_effect = Exception("DNS error")
        result = check_web({"name": "首页", "url": "http://example.com"})
        self.assertFalse(result["reachable"])
        self.assertIsNone(result["code"])
        self.assertIn("DNS error", result["status"])


class TestMain(unittest.TestCase):
    """测试 main() 函数完整流程"""

    @patch("main.SERVERS", [
        {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
        {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
    ])
    @patch("main.WEBS", [
        {"name": "首页", "url": "http://example.com"},
    ])
    @patch("main.DISK_THRESHOLD_GB", 30)
    @patch("main.check_server_agent")
    @patch("main.check_web")
    def test_all_normal(self, mock_check_web, mock_check_server):
        """测试全部正常流程"""
        mock_check_server.side_effect = [
            {"_http_ok": True, "status": "running", "disks": [{"DeviceID": "C:", "FreeSpaceGB": 50, "SizeGB": 100}]},
            {"_http_ok": True, "status": "running", "disks": [{"DeviceID": "D:", "FreeSpaceGB": 100, "SizeGB": 200}]},
        ]
        mock_check_web.return_value = {"reachable": True, "status": "正常打开", "code": 200}

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            main()
        output = captured.getvalue()
        self.assertIn("服务器巡检开始", output)
        self.assertIn("磁盘检查: 通过", output)
        self.assertIn("所有巡检项均正常", output)

    @patch("main.SERVERS", [
        {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
    ])
    @patch("main.WEBS", [])
    @patch("main.DISK_THRESHOLD_GB", 30)
    @patch("main.check_server_agent")
    def test_app_unreachable(self, mock_check_server):
        """测试应用服务器不可达"""
        mock_check_server.return_value = {"_http_ok": False, "status": "unreachable", "error": "timeout"}

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            main()
        output = captured.getvalue()
        self.assertIn("不可达", output)
        self.assertIn("共发现 1 项异常", output)

    @patch("main.SERVERS", [
        {"role": "db", "ip": "192.168.1.20", "port": 5000, "name": "db-01"},
    ])
    @patch("main.WEBS", [])
    @patch("main.DISK_THRESHOLD_GB", 30)
    @patch("main.check_server_agent")
    def test_db_low_disk(self, mock_check_server):
        """测试数据库服务器磁盘低于阈值"""
        mock_check_server.return_value = {"_http_ok": True, "status": "running", "disks": [{"DeviceID": "D:", "FreeSpaceGB": 10, "SizeGB": 100}]}

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            main()
        output = captured.getvalue()
        self.assertIn("[告警] 磁盘低于阈值", output)
        self.assertIn("磁盘空间不足", output)
        self.assertIn("共发现 1 项异常", output)

    @patch("main.SERVERS", [
        {"role": "app", "ip": "192.168.1.10", "port": 5000, "name": "app-01"},
    ])
    @patch("main.WEBS", [])
    @patch("main.DISK_THRESHOLD_GB", 30)
    @patch("main.check_server_agent")
    def test_no_disks(self, mock_check_server):
        """测试无磁盘数据分支"""
        mock_check_server.return_value = {"_http_ok": True, "status": "running", "disks": []}

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            main()
        output = captured.getvalue()
        self.assertIn("运行正常", output)
        self.assertIn("[告警] 磁盘低于阈值", output)

    @patch("main.SERVERS", [])
    @patch("main.WEBS", [
        {"name": "首页", "url": "http://example.com"},
    ])
    @patch("main.check_web")
    def test_web_unreachable(self, mock_check_web):
        """测试网页不可达"""
        mock_check_web.return_value = {"reachable": False, "status": "DNS error", "code": None}

        import io
        captured = io.StringIO()
        with patch("sys.stdout", new=captured):
            main()
        output = captured.getvalue()
        self.assertIn("DNS error", output)
        self.assertIn("网页 首页: DNS error", output)


if __name__ == "__main__":
    unittest.main()
