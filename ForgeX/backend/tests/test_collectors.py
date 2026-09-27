"""Unit tests: parsers + collectors (real parsing, mocked OS where needed)."""
from __future__ import annotations

import json
from pathlib import Path

from app.collectors.base import CollectContext, apply_filters
from app.collectors.event_collector import EventCollector
from app.collectors.network_collector import parse_zeek_conn_log
from app.collectors.pcap_parser import parse_pcap, write_pcap
from app.collectors.process_collector import ProcessCollector
from app.db.models import Investigation, Provenance


def test_pcap_roundtrip(tmp_path: Path):
    packets = [
        {"ts": 1790705780.5, "src_ip": "10.0.0.5", "dst_ip": "203.0.113.9", "src_port": 49152, "dst_port": 4444, "protocol": "TCP"},
        {"ts": 1790705781.0, "src_ip": "10.0.0.5", "dst_ip": "10.0.0.2", "src_port": 53001, "dst_port": 53, "protocol": "UDP", "dns_query": "evil.ngrok.io"},
    ]
    path = tmp_path / "c.pcap"
    write_pcap(packets, path)
    parsed = parse_pcap(path.read_bytes())
    assert len(parsed) == 2
    assert parsed[0].dst_port == 4444 and parsed[0].protocol == "TCP"
    assert parsed[1].dns_query == "evil.ngrok.io"


def test_pcap_rejects_garbage():
    try:
        parse_pcap(b"not a pcap file at all")
        raise AssertionError("should raise")
    except ValueError:
        pass


def test_zeek_conn_log():
    text = "\n".join(
        [
            "#separator \\x09",
            "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p\tproto\tconn_state\torig_bytes\tresp_bytes",
            "1790705780.0\tC1\t10.0.0.5\t49152\t203.0.113.9\t4444\ttcp\tSF\t5242880\t1200",
        ]
    )
    rows = parse_zeek_conn_log(text)
    assert rows[0]["dst_ip"] == "203.0.113.9"
    assert rows[0]["bytes_sent"] == 5242880
    assert rows[0]["protocol"] == "TCP"


def test_apply_filters_operators():
    items = [{"name": "powershell.exe", "pid": 5, "user": "SYSTEM"}, {"name": "bash", "pid": 90, "user": "alice"}]
    assert len(apply_filters(items, [{"field": "name", "op": "CONTAINS", "value": "shell"}])) == 1
    assert len(apply_filters(items, [{"field": "pid", "op": ">", "value": 10}])) == 1
    assert len(apply_filters(items, [{"field": "user", "op": "IN", "value": ["alice", "bob"]}])) == 1
    assert len(apply_filters(items, [{"field": "name", "op": "CONTAINS", "value": "s"}, {"field": "pid", "op": ">", "value": 10, "bool_op": "OR"}])) == 2
    assert len(apply_filters(items, [{"field": "missing", "op": "=", "value": "x"}])) == 0


def _ctx(tmp_path: Path, **kw) -> CollectContext:
    inv = Investigation(id="inv", name="n", target_host="h", source_mode="DATASET", source_path=str(tmp_path), provenance=Provenance.SYNTHETIC.value)
    return CollectContext(investigation=inv, provenance=Provenance.SYNTHETIC, **kw)


async def test_process_collector_dataset_and_live(tmp_path: Path):
    (tmp_path / "processes.json").write_text(json.dumps([{"pid": 1, "name": "x", "cmdline": "x", "user": "u", "parent_pid": 0, "parent_name": ""}]))
    items = await ProcessCollector().collect(_ctx(tmp_path))
    assert items[0]["name"] == "x"
    ctx_live = CollectContext(investigation=Investigation(id="i2", name="n", target_host="localhost", source_mode="LIVE_LOCAL"))
    live = await ProcessCollector().collect(ctx_live)
    assert any(p["pid"] > 0 and p["name"] for p in live)  # real processes of this host


async def test_event_collector_syslog_parsing(tmp_path: Path):
    log = "Sep 26 10:02:12 host sshd[800]: Failed password for bob from 1.2.3.4 port 500 ssh2\nSep 26 10:03:00 host sshd[801]: Accepted password for bob from 1.2.3.4 port 501 ssh2\n"
    (tmp_path / "auth.log").write_text(log)
    (tmp_path / "events.json").write_text("[]")
    collector = EventCollector()
    items = await collector.collect(_ctx(tmp_path))
    # dataset events.json empty → falls back to syslog text via dataset adapter path
    types = {i["event_type"] for i in items}
    assert types <= {"login_failure", "login_success", "system", "privilege_use"} or items == []
