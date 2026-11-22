#!/usr/bin/env python3
"""Check the fixed public endpoints and write latest.json.

Only the two constants in TARGETS are checked. No credentials or API keys are used.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import socket
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any

TARGETS = ("dudu.loc.cc", "panel.dudu.loc.cc")
TIMEOUT = 10
MAX_REDIRECTS = 3
OUTPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "latest.json")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def error_text(exc: BaseException) -> str:
    """Return a bounded, non-secret, JSON-safe diagnostic."""
    text = f"{type(exc).__name__}: {exc}".replace("\x00", "�")
    return text[:500]


def result(status: str = "unknown", **values: Any) -> dict[str, Any]:
    return {"status": status, **values}


def check_dns(host: str) -> dict[str, Any]:
    addresses: dict[str, set[str]] = {"A": set(), "AAAA": set()}
    try:
        infos = socket.getaddrinfo(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _socktype, _proto, _canonname, sockaddr in infos:
            address = sockaddr[0]
            if family == socket.AF_INET:
                addresses["A"].add(address)
            elif family == socket.AF_INET6:
                addresses["AAAA"].add(address)
        flat = {kind: sorted(values) for kind, values in addresses.items()}
        return result("ok" if any(flat.values()) else "fail", resolver="system getaddrinfo", **flat,
                      error=None if any(flat.values()) else "No A or AAAA addresses returned")
    except Exception as exc:
        return result("fail", resolver="system getaddrinfo", A=[], AAAA=[], error=error_text(exc))


def check_tls(host: str) -> dict[str, Any]:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
            with context.wrap_socket(raw, server_hostname=host) as conn:
                cert = conn.getpeercert()
                not_after = cert.get("notAfter")
                if not not_after:
                    return result("fail", verified=True, error="Certificate has no notAfter value")
                expiry = dt.datetime.fromtimestamp(ssl.cert_time_to_seconds(not_after), dt.timezone.utc)
                days = (expiry - dt.datetime.now(dt.timezone.utc)).total_seconds() / 86400
                return result("ok" if days >= 0 else "fail", verified=True,
                              subject=str(cert.get("subject", "")),
                              issuer=str(cert.get("issuer", "")),
                              expires_at=expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                              days_until_expiry=round(days, 2), error=None)
    except Exception as exc:
        return result("fail", verified=False, expires_at=None, days_until_expiry=None, error=error_text(exc))


class LimitedRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        self.count += 1
        if self.count > MAX_REDIRECTS:
            raise urllib.error.HTTPError(req.full_url, code, f"redirect limit exceeded ({MAX_REDIRECTS})", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_http(url: str) -> dict[str, Any]:
    handler = LimitedRedirect()
    opener = urllib.request.build_opener(handler)
    request = urllib.request.Request(url, headers={"User-Agent": "dudu-health-monitor/1.0"}, method="GET")
    try:
        with opener.open(request, timeout=TIMEOUT) as response:
            response.read(1024)
            return result("ok" if 200 <= response.status < 400 else "fail",
                          reachable=True, status_code=response.status, final_url=response.geturl(),
                          redirects=handler.count, error=None)
    except urllib.error.HTTPError as exc:
        return result("fail", reachable=True, status_code=exc.code, final_url=exc.geturl(),
                      redirects=handler.count, error=error_text(exc))
    except Exception as exc:
        return result("fail", reachable=False, status_code=None, final_url=None,
                      redirects=handler.count, error=error_text(exc))


def check_site(host: str) -> dict[str, Any]:
    return {
        "host": host,
        "dns": check_dns(host),
        "tls": check_tls(host),
        "http": check_http(f"http://{host}/"),
        "https": check_http(f"https://{host}/"),
    }


def main() -> int:
    checked_at = utc_now()
    payload = {
        "schema_version": 1,
        "checked_at": checked_at,
        "source": "GitHub Actions / scripts/check_health.py" if os.environ.get("GITHUB_ACTIONS") else "local execution / scripts/check_health.py",
        "timeout_seconds": TIMEOUT,
        "max_redirects": MAX_REDIRECTS,
        "sites": [check_site(host) for host in TARGETS],
    }
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=False)
        handle.write("\n")
    print(json.dumps({"output": OUTPUT, "checked_at": checked_at}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
