#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Oracle 数据库巡检服务

Oracle database inspection service.

检查项 / Checks:
    1. listener_log: 监听日志文件大小（可配置路径与阈值，默认 4GB）
       listener log file size (configurable paths and threshold, default 4GB)
    2. service: 数据库服务运行状态（Windows 查服务 / Linux 查进程）
       database service status (Windows service / Linux process)
    3. deadlock: 锁死检测（通过 sqlplus 查询 v$lock；不可用或未配置时降级为 unknown）
       deadlock detection (queries v$lock via sqlplus; degrades to unknown when unavailable)
    4. storage: 监听日志与备份目录所在磁盘的剩余空间
       free space on the disks holding the listener log and backup directory
    5. backup: 备份目录下是否存在最近成功的 .dmp 备份文件
       whether a recent successful .dmp backup file exists in the backup directory

本服务为可选服务：仅在 agent.py 旁存在 config.json 且配置了 DATABASE 段时启用。
This service is optional: it is enabled only when a config.json with a DATABASE
section exists next to agent.py.
"""

import glob
import os
import platform
import subprocess
import time

from services.disk import collect as collect_disk


# 默认输出语言 / Default output language
DEFAULT_LANG = "zh"

# 状态值 / Status values
STATUS_OK = "ok"
STATUS_WARNING = "warning"
STATUS_UNKNOWN = "unknown"

# 翻译表 / Translation table
TRANSLATIONS = {
    "zh": {
        "log_ok": "监听日志大小正常: {details}",
        "log_exceeded": "监听日志超过阈值 ({threshold}GB): {details}",
        "log_not_configured": "未配置监听日志路径",
        "log_missing": "文件不存在",
        "service_ok": "数据库服务运行正常 ({name})",
        "service_not_running": "数据库服务未运行 ({name}): {detail}",
        "service_check_failed": "服务状态查询失败: {error}",
        "deadlock_ok": "未检测到阻塞锁",
        "deadlock_found": "检测到 {count} 个阻塞锁，数据库可能锁死",
        "deadlock_not_configured": "未配置 SQLPLUS_CONNECT，跳过锁死检测（降级为服务级检查）",
        "deadlock_unavailable": "sqlplus 不可用或查询失败，无法检测锁死: {error}",
        "storage_ok": "存储空间充足: {details}",
        "storage_low": "存储空间不足 ({threshold}GB): {details}",
        "storage_not_configured": "未配置监听日志或备份目录，无法定位磁盘",
        "storage_disk_not_found": "未找到路径所在磁盘: {path}",
        "backup_ok": "备份有效: {file}",
        "backup_no_file": "备份目录下没有 .dmp 备份文件: {dir}",
        "backup_no_recent": "最近 {days} 天内没有非空备份文件: {dir}",
        "backup_not_configured": "未配置备份目录",
        "backup_dir_missing": "备份目录不存在: {dir}",
        "gb_free": "剩余 {free}GB",
    },
    "en": {
        "log_ok": "Listener log size OK: {details}",
        "log_exceeded": "Listener log exceeds threshold ({threshold}GB): {details}",
        "log_not_configured": "Listener log paths not configured",
        "log_missing": "file not found",
        "service_ok": "Database service running normally ({name})",
        "service_not_running": "Database service not running ({name}): {detail}",
        "service_check_failed": "Service status query failed: {error}",
        "deadlock_ok": "No blocking locks detected",
        "deadlock_found": "{count} blocking lock(s) detected, database may be deadlocked",
        "deadlock_not_configured": "SQLPLUS_CONNECT not configured, deadlock check skipped (degraded to service-level check)",
        "deadlock_unavailable": "sqlplus unavailable or query failed, cannot detect deadlocks: {error}",
        "storage_ok": "Storage sufficient: {details}",
        "storage_low": "Storage below threshold ({threshold}GB): {details}",
        "storage_not_configured": "No listener log or backup directory configured, cannot locate disks",
        "storage_disk_not_found": "Disk not found for path: {path}",
        "backup_ok": "Backup effective: {file}",
        "backup_no_file": "No .dmp backup files in directory: {dir}",
        "backup_no_recent": "No non-empty backup files within the last {days} day(s): {dir}",
        "backup_not_configured": "Backup directory not configured",
        "backup_dir_missing": "Backup directory does not exist: {dir}",
        "gb_free": "{free}GB free",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """获取指定语言的翻译文本 / Get translated text for the specified language."""
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def collect(lang: str = DEFAULT_LANG, config: dict = None):
    """
    采集 Oracle 数据库巡检结果。

    Collect Oracle database inspection results.

    Args:
        lang: 输出语言 (默认 zh) / Output language (default zh).
        config: 数据库巡检配置（config.json 的 DATABASE 段）
                Database inspection config (the DATABASE section of config.json).

    Returns:
        dict: 五项检查结果，每项含 status (ok/warning/unknown) 与 detail
        dict: Five check results, each with status (ok/warning/unknown) and detail.
    """
    config = config or {}
    return {
        "listener_log": _check_listener_log(config, lang),
        "service": _check_service(config, lang),
        "deadlock": _check_deadlock(config, lang),
        "storage": _check_storage(config, lang),
        "backup": _check_backup(config, lang),
    }


def _check_listener_log(config: dict, lang: str):
    """检查监听日志文件大小，可配置多个文件逐个判断。

    Check listener log file sizes; multiple configured files are checked individually.
    """
    paths = config.get("LISTENER_LOG_PATHS") or []
    threshold = config.get("LOG_THRESHOLD_GB", 4)
    if not paths:
        return {"status": STATUS_UNKNOWN, "detail": t("log_not_configured", lang)}

    problems = []
    details = []
    for path in paths:
        if not os.path.isfile(path):
            problems.append(f"{path} ({t('log_missing', lang)})")
            continue
        size_gb = round(os.path.getsize(path) / (1024 ** 3), 2)
        details.append(f"{path} {size_gb}GB")
        if size_gb > threshold:
            problems.append(f"{path} {size_gb}GB")

    if problems:
        return {"status": STATUS_WARNING, "detail": t("log_exceeded", lang, threshold=threshold, details="; ".join(problems))}
    return {"status": STATUS_OK, "detail": t("log_ok", lang, details="; ".join(details))}


def _check_service(config: dict, lang: str):
    """检查数据库服务运行状态：Windows 查服务，Linux 查进程。

    Check database service status: Windows service, Linux process.
    """
    if platform.system() == "Windows":
        name = config.get("SERVICE_NAME_WINDOWS", "OracleServiceORCL")
        try:
            result = subprocess.run(
                ["powershell", "-Command", f"(Get-Service -Name '{name}').Status"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except Exception as e:
            return {"status": STATUS_WARNING, "detail": t("service_check_failed", lang, error=e)}
        if result.returncode != 0:
            return {"status": STATUS_WARNING, "detail": t("service_not_running", lang, name=name, detail=result.stderr.strip())}
        status = result.stdout.strip()
        if status == "Running":
            return {"status": STATUS_OK, "detail": t("service_ok", lang, name=name)}
        return {"status": STATUS_WARNING, "detail": t("service_not_running", lang, name=name, detail=status)}
    else:
        name = config.get("PROCESS_NAME_LINUX", "pmon")
        try:
            output = subprocess.check_output(["ps", "-ef"], text=True, timeout=15)
        except Exception as e:
            return {"status": STATUS_WARNING, "detail": t("service_check_failed", lang, error=e)}
        if name in output:
            return {"status": STATUS_OK, "detail": t("service_ok", lang, name=name)}
        return {"status": STATUS_WARNING, "detail": t("service_not_running", lang, name=name, detail=name)}


def _check_deadlock(config: dict, lang: str):
    """通过 sqlplus 查询 v$lock 检测阻塞锁；不可用或未配置时降级为 unknown。

    Detect blocking locks by querying v$lock via sqlplus;
    degrades to unknown when sqlplus is unavailable or not configured.
    """
    connect = config.get("SQLPLUS_CONNECT")
    if not connect:
        return {"status": STATUS_UNKNOWN, "detail": t("deadlock_not_configured", lang)}

    sql = (
        "SET HEADING OFF FEEDBACK OFF PAGESIZE 0;\n"
        "SELECT COUNT(*) FROM v$lock WHERE block > 0;\n"
        "EXIT;\n"
    )
    try:
        result = subprocess.run(
            ["sqlplus", "-S", connect],
            input=sql,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as e:
        return {"status": STATUS_UNKNOWN, "detail": t("deadlock_unavailable", lang, error=e)}

    # 从输出中找到纯数字行作为查询结果；找不到说明连接或查询失败
    # Find a pure-number line as the query result; absence means connect/query failed
    count = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            count = int(line)
            break
    if count is None:
        error = (result.stderr or result.stdout).strip().splitlines()
        return {"status": STATUS_UNKNOWN, "detail": t("deadlock_unavailable", lang, error=error[0] if error else "")}
    if count > 0:
        return {"status": STATUS_WARNING, "detail": t("deadlock_found", lang, count=count)}
    return {"status": STATUS_OK, "detail": t("deadlock_ok", lang)}


def _check_storage(config: dict, lang: str):
    """检查监听日志与备份目录所在磁盘的剩余空间。

    Check free space on the disks holding the listener log and backup directory.
    """
    threshold = config.get("STORAGE_THRESHOLD_GB", 30)
    paths = list(config.get("LISTENER_LOG_PATHS") or [])
    backup_dir = config.get("BACKUP_DIR")
    if backup_dir:
        paths.append(backup_dir)
    if not paths:
        return {"status": STATUS_UNKNOWN, "detail": t("storage_not_configured", lang)}

    try:
        disks = collect_disk(lang=lang)
    except Exception as e:
        return {"status": STATUS_UNKNOWN, "detail": t("service_check_failed", lang, error=e)}
    if not isinstance(disks, list):
        return {"status": STATUS_UNKNOWN, "detail": t("service_check_failed", lang, error=disks)}

    matched = {}
    missing = []
    for path in paths:
        disk = _find_disk_for_path(path, disks)
        if disk is None:
            missing.append(t("storage_disk_not_found", lang, path=path))
        else:
            matched[disk["DeviceID"]] = disk

    low = [d for d in matched.values() if d.get("FreeSpaceGB", 0) < threshold]
    if low or missing:
        details = [f"{d['DeviceID']} {t('gb_free', lang, free=d.get('FreeSpaceGB', 0))}" for d in low] + missing
        return {"status": STATUS_WARNING, "detail": t("storage_low", lang, threshold=threshold, details="; ".join(details))}
    details = "; ".join(f"{d['DeviceID']} {t('gb_free', lang, free=d.get('FreeSpaceGB', 0))}" for d in matched.values())
    return {"status": STATUS_OK, "detail": t("storage_ok", lang, details=details)}


def _find_disk_for_path(path: str, disks: list):
    """按最长前缀匹配路径所在磁盘（兼容 Windows 盘符与 Linux 挂载点）。

    Match the disk for a path by longest prefix
    (works for both Windows drive letters and Linux mount points).
    """
    abs_path = os.path.abspath(path).replace("/", "\\" if platform.system() == "Windows" else "/")
    best = None
    for disk in disks:
        device = disk.get("DeviceID", "")
        if not device:
            continue
        if abs_path.upper().startswith(device.upper()):
            if best is None or len(device) > len(best["DeviceID"]):
                best = disk
    return best


def _check_backup(config: dict, lang: str):
    """检查备份目录下是否存在最近成功的 .dmp 备份（存在、非空、在时间窗口内）。

    Check for a recent successful .dmp backup in the backup directory
    (exists, non-empty, modified within the time window).
    """
    backup_dir = config.get("BACKUP_DIR")
    max_age_days = config.get("BACKUP_MAX_AGE_DAYS", 1)
    if not backup_dir:
        return {"status": STATUS_UNKNOWN, "detail": t("backup_not_configured", lang)}
    if not os.path.isdir(backup_dir):
        return {"status": STATUS_WARNING, "detail": t("backup_dir_missing", lang, dir=backup_dir)}

    dump_files = glob.glob(os.path.join(backup_dir, "*.dmp"))
    if not dump_files:
        return {"status": STATUS_WARNING, "detail": t("backup_no_file", lang, dir=backup_dir)}

    earliest = time.time() - max_age_days * 86400
    for path in dump_files:
        if os.path.getsize(path) > 0 and os.path.getmtime(path) >= earliest:
            return {"status": STATUS_OK, "detail": t("backup_ok", lang, file=os.path.basename(path))}
    return {"status": STATUS_WARNING, "detail": t("backup_no_recent", lang, days=max_age_days, dir=backup_dir)}
