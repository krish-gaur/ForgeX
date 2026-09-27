"""User account collector: pwd/grp on Linux, dataset replay, clear error elsewhere."""
from __future__ import annotations

import platform
import struct
from datetime import UTC, datetime

from app.collectors.base import BaseCollector, CollectContext, apply_filters, apply_limit
from app.core.errors import UnsupportedArtifact
from app.db.models import CollectorType

_WTMP_CANDIDATES = ("/var/log/wtmp", "/var/run/utmp")


def _last_logins() -> dict[str, str]:
    """Best-effort last login per user from wtmp (Linux utmp record format)."""
    out: dict[str, str] = {}
    for path in _WTMP_CANDIDATES:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            continue
        rec_size = 384
        for off in range(0, len(data) - rec_size + 1, rec_size):
            rec = data[off : off + rec_size]
            ut_type = struct.unpack_from("<i", rec, 0)[0]
            if ut_type != 7:  # USER_PROCESS
                continue
            user = rec[8 : 8 + 32].split(b"\x00")[0].decode("utf-8", "replace")
            tv_sec = struct.unpack_from("<i", rec, 20)[0]
            if user and tv_sec:
                out[user] = datetime.fromtimestamp(tv_sec, tz=UTC).isoformat()
    return out


class UserCollector(BaseCollector):
    type = CollectorType.USER
    name = "user"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.is_dataset:
            items = ctx.dataset_file("users.json")
            items = apply_filters(items, ctx.params.get("filters", []))
            return apply_limit(items, ctx.params)
        if platform.system() == "Windows":
            raise UnsupportedArtifact(
                "Live Windows SAM collection requires the ForgeX Windows agent (roadmap). Use a dataset source or a Linux target.",
                details={"collector": "users", "platform": platform.system()},
            )
        import grp
        import pwd

        last = _last_logins()
        items = []
        for pw in pwd.getpwall():
            if pw.pw_name.startswith("_") or pw.pw_name in ("nobody", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp", "proxy", "www-data", "backup", "list", "irc", "gnats"):
                continue
            groups = [g.gr_name for g in grp.getgrall() if pw.pw_name in g.gr_mem] or []
            items.append(
                {
                    "username": pw.pw_name,
                    "uid": pw.pw_uid,
                    "gid": pw.pw_gid,
                    "home": pw.pw_dir,
                    "shell": pw.pw_shell,
                    "last_login": last.get(pw.pw_name),
                    "groups": groups,
                }
            )
        items = apply_filters(items, ctx.params.get("filters", []))
        return apply_limit(items, ctx.params)
