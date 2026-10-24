"""Per-user Kite connection and read-only portfolio endpoints."""

import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from cryptography.fernet import InvalidToken
from flask import Blueprint, jsonify, redirect, request, session, url_for

from database import delete_kite_connection, get_kite_connection, save_kite_connection
from kite_integration import (
    KiteAPIError, KiteConfigurationError, decrypt_token, encrypt_token,
    exchange_request_token, fetch_portfolio, invalidate_token, login_url, session_is_current,
)


kite_bp = Blueprint("kite", __name__)


@kite_bp.route("/kite/connect")
def connect():
    if "user" not in session:
        return redirect(url_for("login_page"))
    try:
        state = secrets.token_urlsafe(32)
        session["kite_connect_state"] = state
        session["kite_connect_user"] = session["user"]
        session["kite_connect_started"] = datetime.now(timezone.utc).isoformat()
        return redirect(login_url(state))
    except KiteConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503


@kite_bp.route("/kite/callback")
def callback():
    if "user" not in session:
        return redirect(url_for("login_page"))
    expected_state = session.pop("kite_connect_state", None)
    expected_user = session.pop("kite_connect_user", None)
    started = session.pop("kite_connect_started", None)
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(started)
        recent = timedelta(0) <= elapsed < timedelta(minutes=10)
    except (TypeError, ValueError):
        recent = False
    if (not expected_state or expected_user != session["user"] or not recent
            or not secrets.compare_digest(request.args.get("state", ""), expected_state)):
        return jsonify({"error": "Kite connection state is invalid. Please retry."}), 400
    if request.args.get("status") != "success" or not request.args.get("request_token"):
        return redirect(url_for("portfolio", kite_error="login"))
    try:
        result = exchange_request_token(request.args["request_token"])
        broker_user_id = result.get("user_id")
        token = result.get("access_token")
        if not broker_user_id or not token:
            raise KiteAPIError("Kite did not return account credentials.")
        save_kite_connection(
            session["user"], broker_user_id, encrypt_token(token),
            datetime.now(timezone.utc).isoformat(),
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "This Kite account is already linked to another user."}), 409
    except (KiteAPIError, KiteConfigurationError) as exc:
        return jsonify({"error": str(exc)}), getattr(exc, "status_code", 503)
    return redirect(url_for("portfolio", connected="1"))


@kite_bp.route("/api/kite/portfolio")
def portfolio_data():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    connection = get_kite_connection(session["user"])
    if connection is None:
        return jsonify({"connected": False, "reconnect_required": False}), 200
    if not session_is_current(connection["connected_at"]):
        return jsonify({"connected": False, "reconnect_required": True}), 200
    try:
        token = decrypt_token(connection["access_token_encrypted"])
        data = fetch_portfolio(token)
    except InvalidToken:
        return jsonify({"error": "Stored Kite session cannot be read. Reconnect your account."}), 503
    except KiteConfigurationError as exc:
        return jsonify({"error": str(exc)}), 503
    except KiteAPIError as exc:
        if exc.status_code == 401:
            return jsonify({"connected": False, "reconnect_required": True}), 200
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify({"connected": True, "broker_user_id": connection["broker_user_id"], **data})


@kite_bp.route("/api/kite/disconnect", methods=["POST"])
def disconnect():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    connection = get_kite_connection(session["user"])
    if connection is None:
        return jsonify({"disconnected": True, "broker_session_revoked": True})
    revoked = not session_is_current(connection["connected_at"])
    if not revoked:
        try:
            invalidate_token(decrypt_token(connection["access_token_encrypted"]))
            revoked = True
        except KiteAPIError as exc:
            revoked = exc.status_code == 401
        except (InvalidToken, KiteConfigurationError):
            pass
    delete_kite_connection(session["user"])
    response = {"disconnected": True, "broker_session_revoked": revoked}
    if not revoked:
        response["warning"] = "Local connection removed, but Kite session revocation could not be confirmed. The broker session expires separately."
    return jsonify(response)
