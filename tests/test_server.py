#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Server 端单元测试

Server-side unit tests.
"""

import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# 将 server 目录加入路径
# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import agent
from services.disk import collect as collect_disk
from services.cpu import collect as collect_cpu
from services.memory import collect as collect_memory
from services.iis import collect as collect_iis
from agent import HealthHandler, get_health_data, run_server


class TestDiskService(unittest.TestCase):
    """测试磁盘采集服务

    Tests for the disk collection service.
    """

    def test_collect_linux(self):
        """测试 Linux 磁盘采集返回 list 结构

        Test Linux disk collection returns a list structure.
        """
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
        """测试 Linux 过滤伪文件系统

        Test Linux filters out pseudo filesystems.
        """
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
        """测试 Linux 无可用挂载点时返回占位数据

        Test Linux returns placeholder data when no usable mount points exist.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", side_effect=Exception("fail")):
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(result[0]["DeviceID"], "/")

    def test_collect_windows_structure(self):
        """测试 Windows 磁盘采集结构（mock PowerShell 返回）

        Test Windows disk collection structure (mock PowerShell output).
        """
        mock_output = "C:,45,100\nD:,120,200\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 2)
                self.assertEqual(result[0]["DeviceID"], "C:")

    def test_collect_windows_single_disk(self):
        """测试 Windows 单条磁盘记录返回也能正确解析

        Test Windows single disk record returning can also be parsed correctly.
        """
        mock_output = "C:,45,100\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_disk()
                self.assertIsInstance(result, list)
                self.assertEqual(len(result), 1)

    def test_collect_windows_powershell_error(self):
        """测试 Windows PowerShell 执行失败时抛出异常

        Test that an exception is raised when Windows PowerShell execution fails.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="PowerShell error")
                with self.assertRaises(RuntimeError):
                    collect_disk()

    def test_collect_windows_has_timeout(self):
        """测试 Windows 磁盘采集为 subprocess.run 设置超时，防止被杀毒软件挂起

        Test Windows disk collection sets a timeout on subprocess.run
        so antivirus hooks cannot hang the request indefinitely.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="C:,45,100\n", stderr="")
                collect_disk()
                self.assertIsNotNone(mock_run.call_args.kwargs.get("timeout"))


class TestCPUService(unittest.TestCase):
    """测试 CPU 采集服务

    Tests for the CPU collection service.
    """

    def test_collect_linux_returns_dict(self):
        """测试 Linux CPU 采集返回字典

        Test Linux CPU collection returns a dict.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("time.sleep"):
                with patch("builtins.open") as mock_open:
                    # 模拟两次 /proc/stat 读取
                    # Simulate two /proc/stat reads
                    mock_open.return_value.__enter__.side_effect = [
                        MagicMock(readline=MagicMock(return_value="cpu  100 0 0 100 0 0 0 0 0 0")),
                        MagicMock(readline=MagicMock(return_value="cpu  200 0 0 150 0 0 0 0 0 0")),
                    ]
                    result = collect_cpu()
                    self.assertIsInstance(result, dict)
                    self.assertIn("usage_percent", result)

    def test_collect_windows_returns_dict(self):
        """测试 Windows CPU 采集返回字典

        Test Windows CPU collection returns a dict.
        """
        mock_output = "20\n30\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_cpu()
                self.assertIsInstance(result, dict)
                self.assertIn("usage_percent", result)
                self.assertEqual(result["usage_percent"], 25)

    def test_collect_windows_has_timeout(self):
        """测试 Windows CPU 采集为 subprocess.run 设置超时

        Test Windows CPU collection sets a timeout on subprocess.run.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="20\n", stderr="")
                collect_cpu()
                self.assertIsNotNone(mock_run.call_args.kwargs.get("timeout"))


class TestMemoryService(unittest.TestCase):
    """测试内存采集服务

    Tests for the memory collection service.
    """

    def test_collect_linux_returns_dict(self):
        """测试 Linux 内存采集返回字典

        Test Linux memory collection returns a dict.
        """
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="              total        used        free      shared  buff/cache   available\nMem:          8192        4096        2048         256        2048        3584"):
                result = collect_memory()
                self.assertIsInstance(result, dict)
                self.assertIn("total_mb", result)
                self.assertIn("free_mb", result)
                self.assertIn("used_percent", result)
                self.assertEqual(result["total_mb"], 8192)

    def test_collect_windows_returns_dict(self):
        """测试 Windows 内存采集返回字典

        Test Windows memory collection returns a dict.
        """
        mock_output = "8388608,4194304\n"
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=mock_output, stderr="")
                result = collect_memory()
                self.assertIsInstance(result, dict)
                self.assertIn("total_mb", result)
                self.assertIn("free_mb", result)
                self.assertIn("used_percent", result)

    def test_collect_windows_has_timeout(self):
        """测试 Windows 内存采集为 subprocess.run 设置超时

        Test Windows memory collection sets a timeout on subprocess.run.
        """
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="8388608,4194304\n", stderr="")
                collect_memory()
                self.assertIsNotNone(mock_run.call_args.kwargs.get("timeout"))


class TestIISService(unittest.TestCase):
    """测试 IIS 采集服务

    Tests for the IIS collection service.
    """

    def test_collect_returns_dict(self):
        """测试 collect 返回字典结构

        Test collect returns a dict structure.
        """
        result = collect_iis()
        self.assertIsInstance(result, dict)
        self.assertIn("service_status", result)
        self.assertIn("sites", result)


class TestHealthHandler(unittest.TestCase):
    """测试 HTTP Handler（通过真实服务器）

    Tests for the HTTP handler (via a real server).
    """

    def setUp(self):
        """启动真实 HTTP 服务器用于测试

        Start a real HTTP server for testing.
        """
        from http.server import HTTPServer
        import threading
        import socket

        # 找一个可用端口
        # Find an available port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()

        self.server = HTTPServer(("127.0.0.1", self.port), HealthHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """关闭服务器

        Shut down the server.
        """
        self.server.shutdown()
        self.server.server_close()

    def test_get_health_returns_json(self):
        """测试 /health 返回 JSON 数据

        Test /health returns JSON data.
        """
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
        """测试 /ping 返回存活状态

        Test /ping returns alive status.
        """
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/ping")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            body = json.loads(resp.read().decode())
            self.assertEqual(body["status"], "ok")

    def test_not_found(self):
        """测试未知路径返回 404

        Test unknown path returns 404.
        """
        import urllib.request
        import urllib.error
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/unknown")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 404)
        body = json.loads(cm.exception.read().decode())
        self.assertEqual(body["status"], "error")


class TestGetHealthData(unittest.TestCase):
    """测试 get_health_data 组装函数

    Tests for the get_health_data assembly function.
    """

    def test_returns_expected_keys(self):
        """测试返回数据包含预期字段

        Test returned data contains the expected keys.
        """
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
        """测试 collect_disk 抛出异常时被 _safe_collect 隔离，不导致整体失败

        Test that collect_disk exceptions are isolated by _safe_collect and do not cause overall failure.
        """
        with patch("agent.collect_disk", side_effect=RuntimeError("disk error")):
            data = get_health_data()
            self.assertEqual(data["status"], "running")
            self.assertIn("error", data["disks"])
            self.assertIn("disk error", data["disks"]["error"])
            self.assertNotIn("traceback", data["disks"])

    def test_get_health_data_exception_returns_500(self):
        """测试 get_health_data 整体异常时返回 500

        Test that a get_health_data overall exception returns 500.
        """
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
    """测试 run_server 函数

    Tests for the run_server function.
    """

    def test_run_and_shutdown(self):
        """测试服务器启动和正常关闭

        Test server startup and normal shutdown.
        """
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
        # Start in a thread, then trigger shutdown
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)
        # 确认服务器在运行
        # Confirm the server is running
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
        """测试 KeyboardInterrupt 正确触发 shutdown

        Test KeyboardInterrupt correctly triggers shutdown.
        """
        with patch("agent.ThreadingHTTPServer") as mock_httpserver:
            mock_server = MagicMock()
            mock_httpserver.return_value = mock_server
            mock_server.serve_forever.side_effect = KeyboardInterrupt()
            run_server(9999)
            mock_server.shutdown.assert_called_once()

    def test_uses_threading_httpserver(self):
        """测试 agent 使用 ThreadingHTTPServer，单个慢请求不阻塞其他请求

        Test that agent uses ThreadingHTTPServer so one slow request
        does not block all other requests.
        """
        self.assertTrue(hasattr(agent, "ThreadingHTTPServer"))

    def test_run_server_creates_threading_server(self):
        """测试 run_server 通过 ThreadingHTTPServer 创建服务器

        Test run_server creates the server via ThreadingHTTPServer.
        """
        self.assertTrue(hasattr(agent, "ThreadingHTTPServer"))
        with patch("agent.ThreadingHTTPServer") as mock_cls:
            mock_server = MagicMock()
            mock_cls.return_value = mock_server
            run_server(9999)
            mock_server.serve_forever.assert_called_once()


import tempfile
import time

from services.database import collect as collect_database


def _db_config(**overrides):
    """构造数据库巡检配置 / Build a database inspection config."""
    config = {
        "LISTENER_LOG_PATHS": [],
        "LOG_THRESHOLD_GB": 4,
        "SERVICE_NAME_WINDOWS": "OracleServiceORCL",
        "PROCESS_NAME_LINUX": "pmon",
        "BACKUP_DIR": "",
        "BACKUP_MAX_AGE_DAYS": 1,
        "STORAGE_THRESHOLD_GB": 30,
    }
    config.update(overrides)
    return config


class TestDatabaseListenerLog(unittest.TestCase):
    """测试监听日志大小检查 / Tests for the listener log size check."""

    def test_log_size_ok(self):
        """日志未超阈值时判定正常 / Log within threshold is ok."""
        with tempfile.NamedTemporaryFile(suffix=".log") as f:
            f.write(b"x" * 1024)
            f.flush()
            config = _db_config(LISTENER_LOG_PATHS=[f.name])
            result = collect_database(config=config)
        self.assertEqual(result["listener_log"]["status"], "ok")

    def test_log_size_exceeds_threshold(self):
        """日志超阈值时判定异常 / Log exceeding threshold is a warning."""
        with tempfile.NamedTemporaryFile(suffix=".log") as f:
            config = _db_config(LISTENER_LOG_PATHS=[f.name], LOG_THRESHOLD_GB=4)
            five_gb = 5 * 1024 ** 3
            with patch("os.path.getsize", return_value=five_gb):
                result = collect_database(config=config)
        self.assertEqual(result["listener_log"]["status"], "warning")

    def test_log_file_missing(self):
        """日志文件不存在时判定异常 / Missing log file is a warning."""
        config = _db_config(LISTENER_LOG_PATHS=["/nonexistent/listener.log"])
        result = collect_database(config=config)
        self.assertEqual(result["listener_log"]["status"], "warning")

    def test_multiple_logs_checked_individually(self):
        """配置多个日志时逐个判断 / Multiple logs are checked individually."""
        with tempfile.NamedTemporaryFile(suffix=".log") as f:
            config = _db_config(LISTENER_LOG_PATHS=[f.name, "/nonexistent/other.log"])
            result = collect_database(config=config)
        self.assertEqual(result["listener_log"]["status"], "warning")


class TestDatabaseServiceStatus(unittest.TestCase):
    """测试数据库服务状态检查 / Tests for the database service status check."""

    def test_service_running_linux(self):
        """Linux 下进程存在判定正常 / Running process on Linux is ok."""
        config = _db_config()
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="oracle 1234 ora_pmon_ORCL"):
                result = collect_database(config=config)
        self.assertEqual(result["service"]["status"], "ok")

    def test_service_not_running_linux(self):
        """Linux 下进程不存在判定异常 / Missing process on Linux is a warning."""
        config = _db_config()
        with patch("platform.system", return_value="Linux"):
            with patch("subprocess.check_output", return_value="root 1 init"):
                result = collect_database(config=config)
        self.assertEqual(result["service"]["status"], "warning")

    def test_service_running_windows(self):
        """Windows 下服务 Running 判定正常 / Running service on Windows is ok."""
        config = _db_config()
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Running\r\n", stderr="")
                result = collect_database(config=config)
        self.assertEqual(result["service"]["status"], "ok")

    def test_service_stopped_windows(self):
        """Windows 下服务停止判定异常 / Stopped service on Windows is a warning."""
        config = _db_config()
        with patch("platform.system", return_value="Windows"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="Stopped\r\n", stderr="")
                result = collect_database(config=config)
        self.assertEqual(result["service"]["status"], "warning")


class TestDatabaseDeadlock(unittest.TestCase):
    """测试数据库锁死检查 / Tests for the database deadlock check."""

    def test_no_deadlock(self):
        """v$lock 无阻塞时判定正常 / No blocking locks is ok."""
        config = _db_config(SQLPLUS_CONNECT="sys/pwd@ORCL as sysdba")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="\n  0\n", stderr="")
            result = collect_database(config=config)
        self.assertEqual(result["deadlock"]["status"], "ok")

    def test_deadlock_detected(self):
        """v$lock 存在阻塞时判定异常 / Blocking locks are a warning."""
        config = _db_config(SQLPLUS_CONNECT="sys/pwd@ORCL as sysdba")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="\n  2\n", stderr="")
            result = collect_database(config=config)
        self.assertEqual(result["deadlock"]["status"], "warning")

    def test_deadlock_not_configured(self):
        """未配置连接串时降级为 unknown / Missing connect string degrades to unknown."""
        config = _db_config()
        result = collect_database(config=config)
        self.assertEqual(result["deadlock"]["status"], "unknown")

    def test_deadlock_sqlplus_unavailable(self):
        """sqlplus 不可用时降级为 unknown / Missing sqlplus degrades to unknown."""
        config = _db_config(SQLPLUS_CONNECT="sys/pwd@ORCL as sysdba")
        with patch("subprocess.run", side_effect=FileNotFoundError("sqlplus")):
            result = collect_database(config=config)
        self.assertEqual(result["deadlock"]["status"], "unknown")


class TestDatabaseBackup(unittest.TestCase):
    """测试备份有效性检查 / Tests for the backup effectiveness check."""

    def _make_dmp(self, dirpath, name="backup.dmp", content=b"data"):
        path = os.path.join(dirpath, name)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def test_backup_ok(self):
        """存在最近非空 .dmp 判定正常 / Recent non-empty .dmp is ok."""
        with tempfile.TemporaryDirectory() as d:
            self._make_dmp(d)
            config = _db_config(BACKUP_DIR=d)
            result = collect_database(config=config)
        self.assertEqual(result["backup"]["status"], "ok")

    def test_backup_no_file(self):
        """无 .dmp 文件判定异常 / No .dmp file is a warning."""
        with tempfile.TemporaryDirectory() as d:
            config = _db_config(BACKUP_DIR=d)
            result = collect_database(config=config)
        self.assertEqual(result["backup"]["status"], "warning")

    def test_backup_old_file(self):
        """备份文件过旧判定异常 / Stale backup file is a warning."""
        with tempfile.TemporaryDirectory() as d:
            path = self._make_dmp(d)
            old = time.time() - 3 * 86400
            os.utime(path, (old, old))
            config = _db_config(BACKUP_DIR=d, BACKUP_MAX_AGE_DAYS=1)
            result = collect_database(config=config)
        self.assertEqual(result["backup"]["status"], "warning")

    def test_backup_empty_file(self):
        """空备份文件判定异常 / Empty backup file is a warning."""
        with tempfile.TemporaryDirectory() as d:
            self._make_dmp(d, content=b"")
            config = _db_config(BACKUP_DIR=d)
            result = collect_database(config=config)
        self.assertEqual(result["backup"]["status"], "warning")


class TestDatabaseStorage(unittest.TestCase):
    """测试存储空间检查 / Tests for the storage sufficiency check."""

    def _config_with_paths(self, d):
        return _db_config(LISTENER_LOG_PATHS=[os.path.join(d, "listener.log")], BACKUP_DIR=d)

    def test_storage_ok(self):
        """磁盘余量充足判定正常 / Sufficient free space is ok."""
        with tempfile.TemporaryDirectory() as d:
            config = self._config_with_paths(d)
            disks = [{"DeviceID": "C:", "FreeSpaceGB": 100, "SizeGB": 200}]
            with patch("services.database.collect_disk", return_value=disks):
                result = collect_database(config=config)
        self.assertEqual(result["storage"]["status"], "ok")

    def test_storage_low(self):
        """磁盘余量不足判定异常 / Insufficient free space is a warning."""
        with tempfile.TemporaryDirectory() as d:
            config = self._config_with_paths(d)
            disks = [{"DeviceID": "C:", "FreeSpaceGB": 10, "SizeGB": 200}]
            with patch("services.database.collect_disk", return_value=disks):
                result = collect_database(config=config)
        self.assertEqual(result["storage"]["status"], "warning")


class TestDatabaseCollectStructure(unittest.TestCase):
    """测试 collect 返回结构 / Tests for the collect() return structure."""

    def test_collect_returns_all_checks(self):
        """返回五项检查且各含 status/detail / Returns five checks with status/detail."""
        with tempfile.TemporaryDirectory() as d:
            config = _db_config(
                LISTENER_LOG_PATHS=[os.path.join(d, "listener.log")],
                BACKUP_DIR=d,
            )
            result = collect_database(config=config)
        for key in ("listener_log", "service", "deadlock", "storage", "backup"):
            self.assertIn(key, result)
            self.assertIn("status", result[key])
            self.assertIn("detail", result[key])
            self.assertIn(result[key]["status"], ("ok", "warning", "unknown"))

    def test_collect_english_detail(self):
        """英文输出 / English output is supported."""
        config = _db_config()
        result = collect_database(lang="en", config=config)
        self.assertIn("status", result["service"])


class TestAgentDatabaseWiring(unittest.TestCase):
    """测试 agent 按配置启用数据库巡检 / Tests for config-driven database wiring."""

    def test_health_without_config_has_no_database_key(self):
        """无 config.json 时不返回 database 字段 / No database key without config."""
        with patch("agent.load_database_config", return_value=None):
            data = get_health_data()
        self.assertNotIn("database", data)

    def test_health_with_config_includes_database(self):
        """有 config.json 时返回 database 字段 / Config present includes database key."""
        fake_result = {"service": {"status": "ok", "detail": "x"}}
        with patch("agent.load_database_config", return_value=_db_config()):
            with patch("agent.collect_database", return_value=fake_result):
                data = get_health_data()
        self.assertEqual(data["database"], fake_result)


if __name__ == "__main__":
    unittest.main()
