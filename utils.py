# utils.py
import subprocess
import uuid
import platform
import requests
import os
import sys

API_URL = os.environ.get("API_URL", "https://GameBey.squareweb.app")
TIMEOUT = 20

CODES = {
    101: "❌ Key Not Found.",
    102: "🚫 User Banned.",
    103: "🔒 Key Blocked.",
    104: "⌛ Key Expired.",
    105: "⚠️ Invalid Key Format.",
    106: "🚫 Access Blocked Due to Excessive Attempts.",
    107: "📄 Incomplete Fingerprint.",
    108: "🔍 Device Does Not Match Registered One.",
    109: "🚫 Invalid Token.",
    110: "❌ Incorrect Email.",
    111: "❌ Incorrect Password.",
    500: "💥 Internal Server Error."
}


def _run_cmd(cmd: str):
    try:
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except Exception:
        return None


def get_android_prop(prop):
    return _run_cmd(f"getprop {prop}")


def detect_platform():
    android_model = get_android_prop("ro.product.model")
    if android_model:
        return "android"

    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        if sys.platform == "ios":
            return "ios"
        return "macos"
    return "unknown"


def get_machine_id():
    plat = detect_platform()
    if plat in ["android", "linux", "macos"]:
        try:
            with open("/etc/machine-id", "r") as f:
                return f.read().strip()
        except Exception:
            return str(uuid.getnode())
    elif plat == "windows":
        out = _run_cmd("wmic csproduct get uuid")
        if out:
            lines = out.splitlines()
            if len(lines) > 1:
                return lines[1].strip()
        return str(uuid.getnode())
    return str(uuid.getnode())


def get_os_version():
    try:
        return platform.platform()
    except Exception:
        return None


def get_public_ip():
    try:
        resp = requests.get("https://api.ipify.org?format=json", timeout=3)
        return resp.json().get("ip")
    except Exception:
        return None


def get_fingerprint():
    plat = detect_platform()

    if plat == "ios":
        return {"error": "❌ iOS System Detected, Usage Impossible."}

    device_id = get_machine_id()
    os_version = get_os_version()
    model = platform.node()
    manufacturer = "Unknown"

    if plat == "android":
        model = get_android_prop("ro.product.model")
        manufacturer = get_android_prop("ro.product.manufacturer") or "Unknown"
    elif plat == "windows":
        manu_out = _run_cmd("wmic computersystem get manufacturer")
        if manu_out:
            lines = manu_out.splitlines()
            if len(lines) > 1:
                manufacturer = lines[1].strip()
    elif plat == "linux":
        sys_vendor_path = "/sys/devices/virtual/dmi/id/sys_vendor"
        if os.path.exists(sys_vendor_path):
            try:
                with open(sys_vendor_path, "r") as f:
                    manufacturer = f.read().strip()
            except Exception:
                pass
    elif plat == "macos":
        manufacturer = "Apple"

    return {
        "device_id": device_id,
        "os_version": os_version,
        "model": model,
        "manufacturer": manufacturer,
    }


def _parse_api_error(data):
    if not data:
        return "❓ Empty API response."
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
        if isinstance(detail, dict):
            code = detail.get("code")
            if code and code in CODES:
                return CODES[code]
            if detail.get("message"):
                return f"❌ {detail.get('message')}"
        elif isinstance(detail, str):
            return f"❌ {detail}"
    if isinstance(data, dict):
        code = data.get("code")
        if code and code in CODES:
            return CODES[code]
        if data.get("message"):
            return f"❌ {data.get('message')}"
    return f"❓ Unmapped error: {data}"


def verificar_key_com_fingerprint(chave: str, api_url: str = None):
    api = api_url or API_URL
    fingerprint = get_fingerprint()
    if "error" in fingerprint:
        return {"status": "error", "message": fingerprint["error"]}

    public_ip = get_public_ip()
    headers = {
        "Authorization": chave,
        "Content-Type": "application/json"
    }
    if public_ip:
        headers["X-Forwarded-For"] = public_ip

    try:
        resp = requests.post(f"{api}/key", json=fingerprint, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"status": "error", "message": f"🌐 Connection Error: {e}"}

    try:
        data = resp.json()
    except ValueError:
        return {"status": "error", "message": f"❌ Invalid API response (status {resp.status_code})."}

    if 200 <= resp.status_code < 300:
        if data.get("success"):
            return {
                "status": "ok",
                "message": "✅ Access Granted.",
                "id": data.get("id"),
                "key": chave,
                "valid_until": data.get("valid_until"),
                "token": data.get("token"),
                "raw": data
            }
        return {"status": "error", "message": _parse_api_error(data), "raw": data}

    return {"status": "error", "message": _parse_api_error(data), "http_status": resp.status_code, "raw": data}


def login(chave: str, email: str, password: str, token: str, api_url: str = None):
    api = api_url or API_URL
    fingerprint = get_fingerprint()
    if "error" in fingerprint:
        return {"status": "error", "message": fingerprint["error"]}

    public_ip = get_public_ip()
    payload = {
        "email": email,
        "password": password,
        "token": token,
        **fingerprint
    }

    headers = {
        "Authorization": chave,
        "Content-Type": "application/json"
    }
    if public_ip:
        headers["X-Forwarded-For"] = public_ip

    try:
        resp = requests.post(f"{api}/login", json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"status": "error", "message": f"🌐 Connection Error: {e}"}

    try:
        data = resp.json()
    except ValueError:
        return {"status": "error", "message": f"❌ Invalid API response (status {resp.status_code})."}

    if 200 <= resp.status_code < 300:
        return data

    return {"status": "error", "message": _parse_api_error(data), "http_status": resp.status_code, "raw": data}


def inject_account(chave: str, token: str, api_url: str = None):
    api = api_url or API_URL
    fingerprint = get_fingerprint()
    if "error" in fingerprint:
        return {"status": "error", "message": fingerprint["error"]}

    public_ip = get_public_ip()
    payload = {
        "token": token,
        **fingerprint
    }

    headers = {
        "Authorization": chave,
        "Content-Type": "application/json"
    }
    if public_ip:
        headers["X-Forwarded-For"] = public_ip

    try:
        resp = requests.post(f"{api}/inject_account", json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"status": "error", "message": f"🌐 Connection Error: {e}"}

    try:
        data = resp.json()
    except ValueError:
        return {"status": "error", "message": f"❌ Invalid API response (status {resp.status_code})."}

    if 200 <= resp.status_code < 300:
        return {"status_code": resp.status_code, **data}

    return {"status": "error", "message": _parse_api_error(data), "http_status": resp.status_code, "raw": data}
