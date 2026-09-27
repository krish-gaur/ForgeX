"""Network collector: live sockets via psutil, dataset replay, PCAP + Zeek ingestion."""
from __future__ import annotations

import psutil

from app.collectors.base import BaseCollector, CollectContext, apply_filters, apply_limit
from app.collectors.pcap_parser import parse_pcap
from app.db.models import CollectorType


def parse_zeek_conn_log(text: str) -> list[dict]:
    """Zeek conn.log TSV → connection evidence dicts."""
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    if not lines:
        return []
    header = None
    for ln in text.splitlines():
        if ln.startswith("#fields"):
            header = ln.split("\t")[1:]
            break
    if not header:
        return []
    items = []
    for ln in lines:
        cols = ln.split("\t")
        rec = dict(zip(header, cols))
        if rec.get("id.orig_h", "-") == "-":
            continue
        items.append(
            {
                "src_ip": rec.get("id.orig_h"),
                "src_port": int(float(rec["id.orig_p"])) if rec.get("id.orig_p", "-") not in ("-", "") else None,
                "dst_ip": rec.get("id.resp_h"),
                "dst_port": int(float(rec["id.resp_p"])) if rec.get("id.resp_p", "-") not in ("-", "") else None,
                "protocol": (rec.get("proto") or "").upper(),
                "state": rec.get("conn_state", ""),
                "pid": None,
                "process_name": None,
                "bytes_sent": int(float(rec["orig_bytes"])) if rec.get("orig_bytes", "-") not in ("-", "") else None,
                "bytes_recv": int(float(rec["resp_bytes"])) if rec.get("resp_bytes", "-") not in ("-", "") else None,
                "source": "zeek",
            }
        )
    return items


class NetworkCollector(BaseCollector):
    type = CollectorType.NETWORK
    name = "network"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        items: list[dict] = []
        pcap_items: list[dict] = []
        if ctx.is_dataset:
            items = ctx.dataset_file("network.json")
            pcap_path = ctx.dataset_dir() / "capture.pcap"
            if pcap_path.exists():
                packets = parse_pcap(pcap_path.read_bytes())
                for pkt in packets:
                    pcap_items.append(
                        {
                            "src_ip": pkt.src_ip,
                            "src_port": pkt.src_port,
                            "dst_ip": pkt.dst_ip,
                            "dst_port": pkt.dst_port,
                            "protocol": pkt.protocol,
                            "state": "CAPTURED",
                            "pid": None,
                            "process_name": None,
                            "bytes_sent": pkt.length,
                            "bytes_recv": None,
                            "dns_query": pkt.dns_query,
                            "source": "pcap",
                            "captured_at": pkt.ts,
                        }
                    )
            zeek_path = ctx.dataset_dir() / "zeek_conn.log"
            if zeek_path.exists():
                items.extend(parse_zeek_conn_log(zeek_path.read_text()))
        else:
            procs = {}
            for conn in psutil.net_connections(kind="inet"):
                pname = None
                if conn.pid:
                    if conn.pid not in procs:
                        try:
                            procs[conn.pid] = psutil.Process(conn.pid).name()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            procs[conn.pid] = None
                    pname = procs[conn.pid]
                items.append(
                    {
                        "src_ip": conn.laddr.ip if conn.laddr else None,
                        "src_port": conn.laddr.port if conn.laddr else None,
                        "dst_ip": conn.raddr.ip if conn.raddr else None,
                        "dst_port": conn.raddr.port if conn.raddr else None,
                        "protocol": "TCP" if conn.type == 1 else "UDP",
                        "state": conn.status,
                        "pid": conn.pid,
                        "process_name": pname,
                        "bytes_sent": None,
                        "bytes_recv": None,
                        "source": "live",
                    }
                )
        merged = items + list(pcap_items)
        merged = apply_filters(merged, ctx.params.get("filters", []))
        return apply_limit(merged, ctx.params)
