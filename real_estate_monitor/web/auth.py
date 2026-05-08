from __future__ import annotations

import os

from functools import wraps

from flask import flash, redirect, render_template, request, session, url_for


def get_credentials() -> tuple[str, str]:
    user = os.environ.get("WEB_USER")
    password = os.environ.get("WEB_PASSWORD")
    if not user or not password:
        raise RuntimeError("WEB_USER and WEB_PASSWORD environment variables must be set")
    return user, password


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated


def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        valid_user, valid_pass = get_credentials()
        if username == valid_user and password == valid_pass:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Credenciais invalidas.", "error")
    return render_template("login.html")


def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))
