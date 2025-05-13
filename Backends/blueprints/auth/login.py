from flask import render_template, redirect, url_for, flash, session, current_app, request
from werkzeug.security import check_password_hash
from .forms import LoginForm
from . import auth_bp
from flask import current_app

@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        conn = current_app.get_db_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(f"""
                    SELECT u.id, u.nickname, u.email, u.password,
                           u.role_id, r.name AS role_name
                    FROM users u
                    LEFT JOIN roles r ON u.role_id = r.id
                    WHERE u.email = '{email}'
                    """)
                user = cursor.fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"]   = user["id"]
            session["user_name"] = user["nickname"]
            session["is_admin"]  = (user["role_name"] == "ADMIN")
            flash("로그인 성공!", "success")
            return redirect(url_for("main_bp.index"))

        flash("이메일 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("login/login.html", form=form)