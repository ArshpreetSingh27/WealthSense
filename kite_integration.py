"""Read-only Kite Connect client and per-user token protection."""

import hashlib
import os
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from cryptography.fernet import Fernet


class KiteConfigurationError(Exception):
    pass


class KiteAPIError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def _config():
    key = os.environ.get("KITE_API_KEY")
    secret = os.environ.get("KITE_API_SECRET")
    encryption_key = os.environ.get("KITE_TOKEN_ENCRYPTION_KEY")
    if not all((key, secret, encryption_key, os.environ.get("FLASK_SECRET_KEY"))):
        raise KiteConfigurationError("Kite connection is not configured on this server.")
    try:
        cipher = Fernet(encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise KiteConfigurationError("Kite token encryption key is invalid.") from exc
    environment = os.environ.get("KITE_ENV", "production")
    if environment not in ("production", "sandbox"):
        raise KiteConfigurationError("Kite environment is invalid.")
    root = "https://sandbox.kite.trade" if environment == "sandbox" else "https://api.kite.trade"
    login_root = "https://sandbox.kite.trade" if environment == "sandbox" else "https://kite.zerodha.com"
    prefix = "/oms" if environment == "sandbox" else ""
    return key, secret, cipher, root, login_root, prefix


def login_url(state):
    key, _, _, _, login_root, _ = _config()
    params = {"api_key": key, "redirect_params": urlencode({"state": state})}
    if login_root == "https://kite.zerodha.com":
        params["v"] = "3"
    return f"{login_root}/connect/login?{urlencode(params)}"


def encrypt_token(token):
    return _config()[2].encrypt(token.encode())


def decrypt_token(encrypted_token):
    return _config()[2].decrypt(encrypted_token).decode()


def session_is_current(connected_at):
    try:
        connected = datetime.fromisoformat(connected_at)
    except (TypeError, ValueError):
        return False
    if connected.tzinfo is None:
        return False
    connected = connected.astimezone(ZoneInfo("Asia/Kolkata"))
    expiry = datetime.combine(connected.date() + timedelta(days=1), time(6), ZoneInfo("Asia/Kolkata"))
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    return connected <= now < expiry


def _request(method, path, token=None, data=None):
    key, _, _, root, _, prefix = _config()
    headers = {"X-Kite-Version": "3"}
    if token:
        headers["Authorization"] = f"token {key}:{token}"
    try:
        response = requests.request(method, f"{root}{prefix}{path}", headers=headers, data=data, timeout=12)
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise KiteAPIError("Kite is temporarily unavailable.") from exc
    if not isinstance(payload, dict):
        raise KiteAPIError("Kite returned an invalid response.")
    if response.status_code in (401, 403) or payload.get("error_type") == "TokenException":
        raise KiteAPIError("Kite session expired. Reconnect your account.", 401)
    if not response.ok or payload.get("status") != "success":
        raise KiteAPIError("Kite could not complete the request.")
    if "data" not in payload:
        raise KiteAPIError("Kite returned an incomplete response.")
    return payload["data"]


def exchange_request_token(request_token):
    key, secret, _, _, _, _ = _config()
    checksum = hashlib.sha256(f"{key}{request_token}{secret}".encode()).hexdigest()
    return _request("POST", "/session/token", data={"api_key": key, "request_token": request_token, "checksum": checksum})


def invalidate_token(token):
    key = _config()[0]
    return _request("DELETE", f"/session/token?{urlencode({'api_key': key, 'access_token': token})}", token)


def fetch_portfolio(token):
    holdings = _request("GET", "/portfolio/holdings", token)
    positions_data = _request("GET", "/portfolio/positions", token)
    funds = _request("GET", "/user/margins", token)
    orders = _request("GET", "/orders", token)
    if (not isinstance(holdings, list) or not isinstance(positions_data, dict)
            or not isinstance(positions_data.get("net"), list)
            or not isinstance(funds, dict) or not isinstance(orders, list)):
        raise KiteAPIError("Kite returned incomplete portfolio data.")
    return {
        "holdings": holdings,
        "positions": positions_data["net"],
        "funds": funds,
        "orders": orders[-30:],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
