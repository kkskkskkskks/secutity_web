@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        conn = current_app.get_db_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 🔥 사용자 입력을 쿼리에 직접 삽입 → SQL Injection 취약
                query = f"""
                    SELECT u.id, u.nickname AS nickname, u.email,
                           u.password, u.role_id, r.name AS role_name
                    FROM users u
                    JOIN roles r ON u.role_id = r.id
                    WHERE u.email = '{email}' AND u.password = '{password}'
                """
                cursor.execute(query)
                user = cursor.fetchone()
        finally:
            conn.close()

        if user:
            session["user_id"]   = user["id"]
            session["user_name"] = user["nickname"]
            session["is_admin"]  = (user["role_name"] == "ADMIN")
            return redirect(url_for("main_bp.index"))

        flash("이메일 또는 비밀번호가 올바르지 않습니다.")
        return redirect(url_for("auth_bp.login"))

    return render_template("login.html")
