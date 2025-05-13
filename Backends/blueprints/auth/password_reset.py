from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash
from . import auth_bp
from .utils import get_serializer

# ─────────────────────────────────────────────────────────────────────────────
# 비밀번호 재설정 요청
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/reset_password_request", methods=["GET", "POST"], endpoint="reset_password_request")
def reset_password_request():
    if request.method == "POST":
        email = request.form.get("email")
        conn = current_app.get_db_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(f"SELECT id FROM users WHERE email = '{email}'")
                user = cur.fetchone()
        finally:
            conn.close()

        if not user:
            flash("등록된 이메일이 없습니다.")
            return redirect(url_for("auth_bp.reset_password_request"))

        s = get_serializer()
        token = s.dumps(email, salt="password-reset-salt")
        reset_url = url_for("auth_bp.reset_password", token=token, _external=True)
        # TODO: 실제 이메일 발송 로직 필요
        flash(f"비밀번호 재설정 링크: {reset_url}")
        return redirect(url_for("auth_bp.login"))

    return render_template("login/reset_password_request.html")


# ─────────────────────────────────────────────────────────────────────────────
# 비밀번호 재설정 폼 및 처리
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"], endpoint="reset_password")
def reset_password(token):
    s = get_serializer()
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except Exception:
        flash("유효하지 않거나 만료된 링크입니다.")
        return redirect(url_for("auth_bp.login"))

    if request.method == "POST":
        new_pw = request.form.get("password")
        hashed = generate_password_hash(new_pw)
        conn = current_app.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE users SET password = '{hashed}' WHERE email = '{email}'")
            conn.commit()
            flash("비밀번호가 변경되었습니다.")
        finally:
            conn.close()
        return redirect(url_for("auth_bp.login"))

    return render_template("login/reset_password.html", token=token)
