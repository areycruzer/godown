#!/usr/bin/env python3
"""Interactive IndiaMART OTP login → writes godown/sessions/*.txt

Usage:
  python3 scripts/indiamart_login.py --mobile 8588077790
  python3 scripts/indiamart_login.py --mobile 8588077790 --otp 1234
  python3 scripts/indiamart_login.py --otp 1234   # resume pending OTP
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx first: pip install httpx", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = ROOT / "sessions"
PENDING = ROOT / ".otp_pending.json"
TOKEN = "imobile@15061981"
UA = "Godown-IndiaMART-Agent/1.0"
EVAL_URL = "https://utils.imimg.com/header/js/evaluate.php"
LOGIN_URL = "https://utils.imimg.com/header/js/login.php"


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"},
        timeout=45.0,
        follow_redirects=True,
    )


def evaluate(client: httpx.Client, mobile: str) -> dict:
    r = client.post(
        EVAL_URL,
        data={
            "username": mobile,
            "iso": "IN",
            "modid": "DIR",
            "format": "JSON",
            "create_user": 1,
            "originalreferer": "https://www.indiamart.com/",
            "GEOIP_COUNTRY_ISO": "IN",
            "ip": "127.0.0.1",
            "screen_name": "Godown-Login",
            "country": "India",
            "service_code": 5,
        },
    )
    r.raise_for_status()
    data = r.json()
    if str(data.get("code")) != "200":
        raise RuntimeError(f"evaluate failed: {data}")
    return data


def send_otp(client: httpx.Client, *, glid: str, session_key: str, mobile: str) -> dict:
    r = client.post(
        LOGIN_URL,
        data={
            "token": TOKEN,
            "glusrid": glid,
            "modid": "DIR",
            "user_mobile_country_code": "91",
            "flag": "OTPGen",
            "user_ip": "127.0.0.1",
            "user_country": "IN",
            "process": "OTP_JoinFreeForm_Desktop",
            "user_updatedusing": "Godown-Login",
            "attribute_id": "121",
            "service_code": "3",
            "sessionKey": session_key,
            "mobile_num": mobile,
        },
    )
    r.raise_for_status()
    data = r.json()
    resp = data.get("Response") or {}
    if resp.get("Status") != "Success":
        raise RuntimeError(f"OTPGen failed: {data}")
    return data


def verify_otp(
    client: httpx.Client,
    *,
    glid: str,
    otp: str,
    mobile: str,
) -> dict:
    r = client.post(
        LOGIN_URL,
        data={
            "token": TOKEN,
            "modid": "DIR",
            "user_mobile_country_code": "91",
            "flag": "OTPVer",
            "user_ip": "127.0.0.1",
            "user_country": "IN",
            "country_name": "India",
            "auth_key": otp.strip(),
            "glusrid": glid,
            "verify_process": "OTP",
            "attribute_id": "121",
            "verify_screen": "Godown-Login",
            "process": "OTP_JoinFreeForm_Desktop",
            "service_code": "3",
            "mobile_num": mobile,
        },
    )
    r.raise_for_status()
    data = r.json()
    resp = data.get("Response") or {}
    if resp.get("Status") != "Success":
        raise RuntimeError(f"OTPVer failed: {data}")
    return data


def build_cookie_header(data_cookie: dict, ak: str) -> str:
    order = (
        "admln",
        "admsales",
        "cd",
        "ctid",
        "fn",
        "glid",
        "iso",
        "mb1",
        "phcc",
        "pkrp",
        "utyp",
        "uv",
    )
    parts = []
    for k in order:
        v = data_cookie.get(k)
        if v is None or v == "":
            continue
        parts.append(f"{k}={v}")
    # Keep any extra keys from the server
    for k, v in data_cookie.items():
        if k in order or k == "sessionKey" or v is None or v == "":
            continue
        parts.append(f"{k}={v}")
    imesh = "|".join(parts)
    im_iss = "t%3D" + ak
    return f"ImeshVisitor={imesh}; im_iss={im_iss}"


def write_session(mobile: str, verify_body: dict) -> Path:
    SESSIONS.mkdir(parents=True, exist_ok=True)
    login = (verify_body.get("Response") or {}).get("LOGIN_DATA") or {}
    dc = login.get("DataCookie") or {}
    ak = ((login.get("im_iss") or {}).get("t") or "").strip()
    if not ak:
        raise RuntimeError("No im_iss.t in verify response")
    cookie = build_cookie_header(dc, ak)
    (SESSIONS / "ak.txt").write_text(ak + "\n", encoding="utf-8")
    (SESSIONS / "im_iss_t.txt").write_text(ak + "\n", encoding="utf-8")
    (SESSIONS / "cookie_header.txt").write_text(cookie + "\n", encoding="utf-8")
    (SESSIONS / "otp_mobile.txt").write_text(mobile + "\n", encoding="utf-8")
    meta = {
        "status": "authenticated",
        "glid": login.get("glid") or dc.get("glid"),
        "mobile": mobile,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "access": login.get("access"),
    }
    (SESSIONS / "session_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    for name in ("ak.txt", "cookie_header.txt", "im_iss_t.txt", "otp_mobile.txt"):
        try:
            (SESSIONS / name).chmod(0o600)
        except OSError:
            pass
    if PENDING.exists():
        PENDING.unlink()
    return SESSIONS


def save_pending(mobile: str, glid: str, session_key: str, otpgen: dict) -> None:
    PENDING.write_text(
        json.dumps(
            {
                "mobile": mobile,
                "glid": glid,
                "sessionKey": session_key,
                "otpgen": otpgen,
                "ts": time.time(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_pending() -> dict | None:
    if not PENDING.is_file():
        return None
    return json.loads(PENDING.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="IndiaMART OTP → godown/sessions")
    ap.add_argument("--mobile", default=None, help="10-digit Indian mobile")
    ap.add_argument("--otp", default=None, help="OTP from SMS (prompted if omitted after send)")
    ap.add_argument("--send-only", action="store_true", help="Only send OTP")
    ap.add_argument("--resend", action="store_true", help="Force a new OTP even if pending exists")
    args = ap.parse_args()

    pending = None if args.resend else load_pending()

    with _client() as client:
        # Resume path: only OTP needed
        if args.otp and pending and not args.resend and (
            not args.mobile or args.mobile.strip() == str(pending.get("mobile"))
        ):
            mobile = str(pending["mobile"])
            glid = str(pending["glid"])
            print(f"Resuming pending OTP for {mobile} (glid={glid})…")
            ver = verify_otp(client, glid=glid, otp=args.otp, mobile=mobile)
            print("   ", (ver.get("Response") or {}).get("Message"))
            path = write_session(mobile, ver)
            print(f"Wrote session files under {path}")
            print("Set USE_AK=true in .env and restart the backend.")
            return 0

        mobile = (args.mobile or (pending or {}).get("mobile") or "").strip()
        if not (mobile.isdigit() and len(mobile) == 10):
            print("Pass --mobile 10DIGIT (or have a pending OTP + --otp)", file=sys.stderr)
            return 2

        print("1) identify (evaluate.php)…")
        ev = evaluate(client, mobile)
        dc = ev.get("DataCookie") or {}
        glid = str(dc.get("glid") or "")
        session_key = str(dc.get("sessionKey") or "")
        if not glid:
            print("No glid from evaluate", file=sys.stderr)
            return 1
        print(f"   glid={glid}")

        print("2) send OTP (login.php OTPGen)…")
        gen = send_otp(client, glid=glid, session_key=session_key, mobile=mobile)
        msg = (gen.get("Response") or {}).get("Message")
        print(f"   {msg}")
        save_pending(mobile, glid, session_key, gen)

        if args.send_only:
            print(f"OTP sent. Re-run: python3 scripts/indiamart_login.py --otp YOUR_CODE")
            return 0

        otp = args.otp or input("Enter SMS OTP: ").strip()
        print("3) verify OTP (login.php OTPVer)…")
        ver = verify_otp(client, glid=glid, otp=otp, mobile=mobile)
        print("   ", (ver.get("Response") or {}).get("Message"))

        path = write_session(mobile, ver)
        print(f"Wrote session files under {path}")
        print("Set USE_AK=true in .env and restart the backend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
