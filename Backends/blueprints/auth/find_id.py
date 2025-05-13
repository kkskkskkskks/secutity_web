from flask import render_template, request, redirect, url_for, flash, current_app
from . import auth_bp

# ─────────────────────────────────────────────────────────────────────────────
# 아이디 찾기
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/find_id", methods=["GET", "POST"], endpoint="find_id")
def find_id():
    if request.method == "POST":
        email = request.form.get("email")
        conn = current_app.get_db_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(f"SELECT nickname FROM users WHERE email = '{email}'")
                user = cur.fetchone()
        finally:
            conn.close()

        if user:
            flash(f"회원님의 닉네임(아이디)은 “{user['nickname']}” 입니다.")
        else:
            flash("가입된 이메일이 없습니다.")
        return redirect(url_for("auth_bp.find_id"))

    return render_template("login/find_id.html")