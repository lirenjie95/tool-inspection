#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server 端单元测试"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 将 server 目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

from services.disk import collect as collect_disk
from services.iis import collect as collect_iis
from agent import HealthHandler, get_health_data


class TestDiskService(unittest.TestCase):
    """测试磁盘采集服务"""

    def test_collect_linux(self):
        """测试 Linux 磁盘采集返回 list 结构"""
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="Filesystem 1G-blocks Used Available Use% Mounted on\n/dev/disk1 100G 30G 70G 30% /"):
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["DeviceID"], "/")
                self.assertIn("FreeSpaceGB", result[0])
                self.assertIn("SizeGB", result[0])

    def test_collect_linux_fallback(self):
        """测试 Linux 无可用挂载点时返回占位数据"""
        with patch("platform.system", return_value="Linux"):
            with patch("os.path.ismount", return_value=False):
                with patch("subprocess.check_output", side_effect=Exception("fail")):
                    result = collect_disk()
                    self.assertIsInstance(result, list)
                    self.assertEqual(result[0]["DeviceID"], "/")

    def test_collect_windows_structure(self):
        """测试 Windows 磁盘采集结构（mock PowerShell 返回）"""
        mock_json = json.dumps([
            {"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100},
            {"DeviceID": "D:", "FreeSpaceGB": 120, "SizeGB": 200}
        ])
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_json, stderr="")
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]["DeviceID"], "C:")

    def test_collect_windows_single_disk(self):
        """测试 Windows 单条磁盘记录返回 dict 时也能转为 list"""
        mock_json = json.dumps({"DeviceID": "C:", "FreeSpaceGB": 45, "SizeGB": 100})
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_json, stderr="")
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 1)

    def test_collect_windows_powershell_error(self):
        """测试 Windows PowerShell 执行失败时抛出异常"""
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="PowerShell error")
                with self.assertRaises(RuntimeError):
                    collect_disk()


class TestIISService(unittest.TestCase):
    """测试 IIS 采集服务"""

    def test_collect_returns_dict(self):
        """测试 collect 返回字典结构"""
        result = collect_iis()
        self.assertIsInstance(result, dict)
        self.assertIn("service_status", result)
        self.assertIn("sites", result)


class TestHealthHandler(unittest.TestCase):
    """测试 HTTP Handler（通过真实服务器）"""

    def setUp(self):
        """启动真实 HTTP 服务器用于测试"""
        from http.server import HTTPServer
        import threading
        import socket

        # 找一个可用端口
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()

        self.server = HTTPServer(("127.0.0.1", self.port), HealthHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """关闭服务器"""
        self.server.shutdown()
        self.server.server_close()

    def test_get_health_returns_json(self):
        """测试 /health 返回 JSON 数据"""
        import urllib.request
        with patch("agent.collect_disk", return_value=[{"DeviceID": "/", "FreeSpaceGB": 10, "SizeGB": 100}]):
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                body = json.loads(resp.read().decode())
                self.assertEqual(body["status"], "running")
                self.assertIn("os", body)
                self.assertIn("disks", body)

    def test_not_found(self):
        """测试未知路径返回 404"""
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/unknown")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 404)
        body = json.loads(cm.exception.read().decode())
        self.assertEqual(body["status"], "not_found")


class TestGetHealthData(unittest.TestCase):
    """测试 get_health_data 组装函数"""

    def test_returns_expected_keys(self):
        """测试返回数据包含预期字段"""
        with patch("agent.collect_disk", return_value=[]):
            data = get_health_data()
            self.assertIn("status", data)
            self.assertIn("os", data)
            self.assertIn("disks", data)
            self.assertEqual(data["status"], "running")

    def test_collect_disk_exception(self):
        """测试 collect_disk 抛出异常时返回 500"""
        with patch("agent.collect_disk", side_effect=RuntimeError("disk error")):
            from http.server import HTTPServer
            import threading
            import socket
            import urllib.request
            import urllib.error

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()

            server = HTTPServer(("127.0.0.1", port), HealthHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
                with self.assertRaises(urllib.error.HTTPError) as cm:
                    urllib.request.urlopen(req, timeout=5)
                self.assertEqual(cm.exception.code, 500)
                body = json.loads(cm.exception.read().decode())
                self.assertEqual(body["status"], "error")
                self.assertIn("disk error", body["message"])
            finally:
                server.shutdown()
                server.server_close()


class TestRunServer(unittest.TestCase):
    """测试 run_server 函数"""

    def test_run_and_keyboard_interrupt(self):
        """测试服务器启动和 KeyboardInterrupt 关闭"""
        from http.server import HTTPServer
        import threading
        import time
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        server = HTTPServer(("127.0.0.1", port), HealthHandler)
        # 在线程中启动，然后触发 shutdown
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)
        # 确认服务器在运行
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with patch("agent.collect_disk", return_value=[]):
            with urllib.request.urlopen(req, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    unittest.main()
