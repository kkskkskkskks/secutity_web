from flask import render_template, request, redirect, url_for, flash, current_app
from werkzeug.security import generate_password_hash
from mysql.connector import errors
from email_validator import validate_email, EmailNotValidError
from markupsafe import escape
from . import auth_bp

@auth_bp.route("/register", methods=["GET", "POST"], endpoint="register")
def register():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]
        nickname = request.form.get("nickname") or ""
        phone    = request.form.get("phone") or ""

        # 이메일 형식 검증
        try:
            valid = validate_email(email)
            email = valid.email
        except EmailNotValidError:
            flash("유효한 이메일 주소를 입력하세요.")
            return render_template(
                "login/register.html",
                email=escape(email),
                nickname=escape(nickname),
                phone=escape(phone)
            )

        # 비밀번호 길이 검증: 최소 6자
        if len(password) < 6:
            flash("비밀번호는 최소 6자 이상이어야 합니다.")
            return render_template(
                "login/register.html",
                email=escape(email),
                nickname=escape(nickname),
                phone=escape(phone)
            )

        # 닉네임 길이 검증
        if nickname and len(nickname) > 50:
            flash("닉네임은 최대 50자까지 입력 가능합니다.")
            return render_template(
                "login/register.html",
                email=escape(email),
                nickname=escape(nickname),
                phone=escape(phone)
            )

        # 전화번호 길이 검증
        if phone and len(phone) > 20:
            flash("전화번호는 최대 20자까지 입력 가능합니다.")
            return render_template(
                "login/register.html",
                email=escape(email),
                nickname=escape(nickname),
                phone=escape(phone)
            )

        if not email or not password:
            flash("이메일과 비밀번호는 필수입니다.")
            return redirect(url_for("auth_bp.register"))

        hashed_pw = generate_password_hash(password)

        conn = current_app.get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO users (email, password, nickname, phone, role_id)
                    VALUES ('{email}', '{hashed_pw}', '{nickname}', '{phone}', 2)
                """)
            conn.commit()
            return redirect(url_for("main_bp.index"))

        except errors.IntegrityError:
            flash("이미 등록된 이메일입니다.")
            return redirect(url_for("auth_bp.register"))

        finally:
            conn.close()

    return render_template("login/register.html")