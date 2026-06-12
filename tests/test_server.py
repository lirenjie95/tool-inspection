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
from services.cpu import collect as collect_cpu
from services.memory import collect as collect_memory
from services.iis import collect as collect_iis
from agent import HealthHandler, get_health_data, run_server


class TestDiskService(unittest.TestCase):
    """测试磁盘采集服务"""

    def test_collect_linux(self):
        """测试 Linux 磁盘采集返回 list 结构"""
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "/dev/disk1 100G 30G 70G 30% /\n"
            "/dev/disk2 200G 50G 150G 25% /data"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=True):
                    result = collect_disk()
                    self.assertIsInstance(result, list)
                    self.assertEqual(len(result), 2)
                    device_ids = {r["DeviceID"] for r in result}
                    self.assertIn("/", device_ids)
                    self.assertIn("/data", device_ids)

    def test_collect_linux_skip_pseudo_fs(self):
        """测试 Linux 过滤伪文件系统"""
        df_output = (
            "Filesystem 1G-blocks Used Available Use% Mounted on\n"
            "/dev/disk1 100G 30G 70G 30% /\n"
            "tmpfs 2G 0G 2G 0% /run\n"
            "devtmpfs 1G 0G 1G 0% /dev"
        )
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value=df_output):
                with patch("os.path.ismount", return_value=True):
                    result = collect_disk()
                    self.assertIsInstance(result, list)
                    self.assertEqual(len(result), 1)
                    self.assertEqual(result[0]["DeviceID"], "/")

    def test_collect_linux_fallback(self):
        """测试 Linux 无可用挂载点时返回占位数据"""
        with patch("platform.system", return_value="Linux"):
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


class TestCPUService(unittest.TestCase):
    """测试 CPU 采集服务"""

    def test_collect_linux_returns_dict(self):
        """测试 Linux CPU 采集返回字典"""
        with patch("platform.system", return_value="Linux"):
            with patch("time.sleep"):
                with patch("builtins.open") as mock_open:
                    # 模拟两次 /proc/stat 读取
                    mock_open.return_value.__enter__.side_effect = [
                        MagicMock(readline=MagicMock(return_value="cpu  100 0 0 100 0 0 0 0 0 0")),
                        MagicMock(readline=MagicMock(return_value="cpu  200 0 0 150 0 0 0 0 0 0")),
                    ]
                    result = collect_cpu()
                    self.assertIsInstance(result, dict)
                    self.assertIn("usage_percent", result)

    def test_collect_windows_returns_dict(self):
        """测试 Windows CPU 采集返回字典"""
        mock_json = json.dumps([20, 30])
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_json, stderr="")
                result = collect_cpu()
                self.assertIsInstance(result, dict)
                self.assertIn("usage_percent", result)
                self.assertEqual(result["usage_percent"], 25)


class TestMemoryService(unittest.TestCase):
    """测试内存采集服务"""

    def test_collect_linux_returns_dict(self):
        """测试 Linux 内存采集返回字典"""
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="              total        used        free      shared  buff/cache   available\nMem:          8192        4096        2048         256        2048        3584"):
                result = collect_memory()
                self.assertIsInstance(result, dict)
                self.assertIn("total_mb", result)
                self.assertIn("free_mb", result)
                self.assertIn("used_percent", result)
                self.assertEqual(result["total_mb"], 8192)

    def test_collect_windows_returns_dict(self):
        """测试 Windows 内存采集返回字典"""
        mock_json = json.dumps({"TotalVisibleMemorySize": 8388608, "FreePhysicalMemory": 4194304})
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_json, stderr="")
                result = collect_memory()
                self.assertIsInstance(result, dict)
                self.assertIn("total_mb", result)
                self.assertIn("free_mb", result)
                self.assertIn("used_percent", result)


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
            with patch("agent.collect_cpu", return_value={"usage_percent": 10}):
                with patch("agent.collect_memory", return_value={"total_mb": 8192, "free_mb": 4096, "used_percent": 50}):
                    req = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        self.assertEqual(resp.status, 200)
                        body = json.loads(resp.read().decode())
                        self.assertEqual(body["status"], "running")
                        self.assertIn("os", body)
                        self.assertIn("disks", body)
                        self.assertIn("cpu", body)
                        self.assertIn("memory", body)

    def test_ping_returns_ok(self):
        """测试 /ping 返回存活状态"""
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/ping")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode())
            self.assertEqual(body["status"], "ok")

    def test_not_found(self):
        """测试未知路径返回 404"""
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/unknown")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 404)
        body = json.loads(cm.exception.read().decode())
        self.assertEqual(body["status"], "error")


class TestGetHealthData(unittest.TestCase):
    """测试 get_health_data 组装函数"""

    def test_returns_expected_keys(self):
        """测试返回数据包含预期字段"""
        with patch("agent.collect_disk", return_value=[]):
            with patch("agent.collect_cpu", return_value={"usage_percent": 10}):
                with patch("agent.collect_memory", return_value={"total_mb": 8192, "free_mb": 4096, "used_percent": 50}):
                    data = get_health_data()
                    self.assertIn("status", data)
                    self.assertIn("os", data)
                    self.assertIn("disks", data)
                    self.assertIn("cpu", data)
                    self.assertIn("memory", data)
                    self.assertEqual(data["status"], "running")

    def test_collect_disk_exception_isolated(self):
        """测试 collect_disk 抛出异常时被 _safe_collect 隔离，不导致整体失败"""
        with patch("agent.collect_disk", side_effect=RuntimeError("disk error")):
            data = get_health_data()
            self.assertEqual(data["status"], "running")
            self.assertIn("error", data["disks"])
            self.assertIn("disk error", data["disks"]["error"])

    def test_get_health_data_exception_returns_500(self):
        """测试 get_health_data 整体异常时返回 500"""
        with patch("agent.get_health_data", side_effect=RuntimeError("unexpected")):
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
                self.assertIn("unexpected", body["message"])
            finally:
                server.shutdown()
                server.server_close()


class TestRunServer(unittest.TestCase):
    """测试 run_server 函数"""

    def test_run_and_shutdown(self):
        """测试服务器启动和正常关闭"""
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
            with patch("agent.collect_cpu", return_value={"usage_percent": 0}):
                with patch("agent.collect_memory", return_value={"total_mb": 0, "free_mb": 0, "used_percent": 0}):
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        self.assertEqual(resp.status, 200)
        server.shutdown()
        server.server_close()

    def test_keyboard_interrupt(self):
        """测试 KeyboardInterrupt 正确触发 shutdown"""
        with patch("agent.HTTPServer") as mock_httpserver:
            mock_server = MagicMock()
            mock_httpserver.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            run_server(9999)
            mock_server.shutdown.assert_called_once()


if __name__ == "__main__":
    unittest.main()
