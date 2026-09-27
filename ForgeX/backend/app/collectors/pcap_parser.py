"""Pure-Python PCAP parser (no tshark dependency): Ethernet/IPv4/IPv6 + TCP/UDP/DNS."""
from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

MAGIC_LE = 0xA1B2C3D4
MAGIC_BE = 0xD4C3B2A1


@dataclass
class PcapPacket:
    ts: float
    src_ip: str
    dst_ip: str
    src_port: int | None
    dst_port: int | None
    protocol: str
    length: int
    dns_query: str | None = None


def parse_pcap(data: bytes) -> list[PcapPacket]:
    if len(data) < 24:
        raise ValueError("File too small to be a PCAP capture")
    magic = struct.unpack("<I", data[0:4])[0]
    if magic == MAGIC_LE:
        endian = "<"
    elif magic == MAGIC_BE:
        endian = ">"
    else:
        raise ValueError(f"Not a PCAP file (bad magic 0x{magic:08x})")
    link_type = struct.unpack(endian + "I", data[20:24])[0]
    packets: list[PcapPacket] = []
    off = 24
    while off + 16 <= len(data):
        ts_sec, ts_usec, caplen, _origlen = struct.unpack(endian + "IIII", data[off : off + 16])
        off += 16
        raw = data[off : off + caplen]
        off += caplen
        pkt = _parse_packet(raw, link_type, ts_sec + ts_usec / 1e6)
        if pkt:
            packets.append(pkt)
    return packets


def _parse_packet(raw: bytes, link_type: int, ts: float) -> PcapPacket | None:
    if link_type == 1:  # Ethernet
        if len(raw) < 14:
            return None
        ether_type = struct.unpack("!H", raw[12:14])[0]
        payload = raw[14:]
    elif link_type in (101, 102):  # raw IP
        ether_type = 0x0800 if (raw[0] >> 4) == 4 else 0x86DD
        payload = raw
    else:
        return None
    if ether_type == 0x0800:
        return _parse_ip(payload, ts, 4)
    if ether_type == 0x86DD:
        return _parse_ip(payload, ts, 6)
    return None


def _parse_ip(payload: bytes, ts: float, version: int) -> PcapPacket | None:
    if version == 4:
        if len(payload) < 20:
            return None
        ihl = (payload[0] & 0x0F) * 4
        proto = payload[9]
        src = socket.inet_ntoa(payload[12:16])
        dst = socket.inet_ntoa(payload[16:20])
        l4 = payload[ihl:]
    else:
        if len(payload) < 40:
            return None
        proto = payload[6]
        src = socket.inet_ntop(socket.AF_INET6, payload[8:24])
        dst = socket.inet_ntop(socket.AF_INET6, payload[24:40])
        l4 = payload[40:]
    src_port = dst_port = None
    dns_query = None
    if proto in (6, 17) and len(l4) >= 4:
        src_port, dst_port = struct.unpack("!HH", l4[0:4])
        if proto == 17 and (src_port == 53 or dst_port == 53):
            dns_query = _parse_dns_query(l4)
    protocol = {6: "TCP", 17: "UDP", 1: "ICMP"}.get(proto, f"IP-{proto}")
    return PcapPacket(ts=ts, src_ip=src, dst_ip=dst, src_port=src_port, dst_port=dst_port, protocol=protocol, length=len(payload), dns_query=dns_query)


def _parse_dns_query(l4: bytes) -> str | None:
    # UDP payload begins after 8-byte UDP header
    udp = l4[8:]
    if len(udp) < 13:
        return None
    qdcount = struct.unpack("!H", udp[4:6])[0]
    if qdcount < 1:
        return None
    idx = 12
    labels = []
    while idx < len(udp):
        ln = udp[idx]
        if ln == 0:
            break
        if ln & 0xC0:  # compression pointer
            return ".".join(labels) or None
        idx += 1
        labels.append(udp[idx : idx + ln].decode("utf-8", "replace"))
        idx += ln
    return ".".join(labels) or None


def write_pcap(packets: list[dict], path) -> None:
    """Write a valid pcap (used by the synthetic dataset generator)."""
    out = bytearray(struct.pack("<IHHiIII", MAGIC_LE, 2, 4, 0, 0, 65535, 1))
    for p in packets:
        eth = _build_eth_ipv4_tcp_udp(p)
        ts = int(p["ts"])
        usec = int((p["ts"] - ts) * 1e6)
        out += struct.pack("<IIII", ts, usec, len(eth), len(eth))
        out += eth
    with open(path, "wb") as f:
        f.write(bytes(out))


def _build_eth_ipv4_tcp_udp(p: dict) -> bytes:
    proto = 6 if p.get("protocol", "TCP") == "TCP" else 17
    src = socket.inet_aton(p["src_ip"])
    dst = socket.inet_aton(p["dst_ip"])
    sport = int(p.get("src_port") or 0)
    dport = int(p.get("dst_port") or 0)
    payload = b""
    if dport == 53 or sport == 53:
        payload = _build_dns_query(p.get("dns_query", "example.com"))
    l4 = struct.pack("!HH", sport, dport) + b"\x00" * (12 if proto == 6 else 4) + payload
    total = 20 + len(l4)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, total, 1, 0x4000, 64, proto, 0, src, dst)
    return b"\x00" * 12 + struct.pack("!H", 0x0800) + ip + l4


def _build_dns_query(name: str) -> bytes:
    header = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(part)]) + part.encode() for part in name.split(".")) + b"\x00"
    return header + qname + struct.pack("!HH", 1, 1)
