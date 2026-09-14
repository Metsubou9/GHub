"""Определение IP сервера текущей катки по соединениям процесса игры.
Dota 2 / Deadlock ходят на сервер Valve по UDP (обычно порты 27000-27200).
Берем самый частый публичный remote-IP среди соединений процесса."""
import ipaddress
import socket
from collections import Counter

import psutil

VALVE_PORTS = range(27000, 27250)


def _is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
        return not (a.is_private or a.is_loopback or a.is_link_local
                    or a.is_multicast or a.is_reserved)
    except ValueError:
        return False


def find_match_ip(process_names: list[str]) -> str | None:
    names = {n.lower() for n in process_names}
    pids = set()
    for p in psutil.process_iter(["name", "pid"]):
        if (p.info["name"] or "").lower() in names:
            pids.add(p.info["pid"])
    if not pids:
        return None
    try:
        conns = psutil.net_connections(kind="inet")
    except (psutil.AccessDenied, OSError, RuntimeError):
        return None
    preferred, other = [], []
    for c in conns:
        if c.pid not in pids or not c.raddr:
            continue
        ip = c.raddr.ip
        if not _is_public(ip):
            continue
        port = c.raddr.port
        if c.type == socket.SOCK_DGRAM or port in VALVE_PORTS:
            preferred.append(ip)
        else:
            other.append(ip)
    pool = preferred or other
    if not pool:
        return None
    return Counter(pool).most_common(1)[0][0]
