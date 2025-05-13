from flask import render_template, redirect, url_for, flash, session, request, current_app
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import auth_bp

@auth_bp.route("/profile", methods=["GET", "POST"], endpoint="profile")
def mypage():
    if "user_id" not in session:
        flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    if request.method == "POST":
        # 비밀번호 변경
        if request.form.get("current_password"):
            current_pw = request.form.get("current_password")
            new_pw     = request.form.get("new_password")
            confirm_pw = request.form.get("confirm_password")
            # 새 비밀번호 길이 검증: 최소 6자
            if len(new_pw) < 6:
                flash("새 비밀번호는 최소 6자 이상이어야 합니다.")
                return redirect(url_for("auth_bp.profile", tab="info"))

            conn = current_app.get_db_connection()
            try:
                with conn.cursor(dictionary=True) as cur:
                    cur.execute(f"SELECT password FROM users WHERE id = {session['user_id']}")
                    user_pw = cur.fetchone()["password"]
                if not check_password_hash(user_pw, current_pw):
                    flash("현재 비밀번호가 일치하지 않습니다.")
                    return redirect(url_for("auth_bp.profile", tab="info"))
                if new_pw != confirm_pw:
                    flash("새 비밀번호와 확인이 일치하지 않습니다.")
                    return redirect(url_for("auth_bp.profile", tab="info"))
                hashed = generate_password_hash(new_pw)
                with conn.cursor() as cur:
                    cur.execute(f"UPDATE users SET password = '{hashed}', updated_at = NOW() WHERE id = {session['user_id']}")
                conn.commit()
                flash("비밀번호가 변경되었습니다.")
            finally:
                conn.close()
            return redirect(url_for("auth_bp.profile", tab="info"))

        # 개인정보 업데이트
        nickname = request.form.get("nickname")
        phone    = request.form.get("phone")
        conn = current_app.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE users SET nickname = '{nickname}', phone = '{phone}', updated_at = NOW() WHERE id = {session['user_id']}")
            conn.commit()
            flash("개인정보가 업데이트되었습니다.")
        finally:
            conn.close()
        return redirect(url_for("auth_bp.profile", tab="info"))

    tab = request.args.get("tab", "info")
    conn = current_app.get_db_connection()

    with conn.cursor(dictionary=True) as cur:
        # 사용자 정보
        cur.execute(f"""
            SELECT u.*, r.name AS role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = {session['user_id']}
        """)
        user = cur.fetchone()

        orders = []
        if tab == "orders":
            cur.execute(f"""
                SELECT
                    o.id AS order_id, o.created_at, o.total_amount, o.status,
                    o.address, p.name AS product_name, oi.quantity, oi.unit_price,
                    pi.url AS image,
                    cat.name AS category, ct.name AS category_type
                FROM orders o
                JOIN order_items oi ON o.id = oi.order_id
                JOIN products p ON oi.product_id = p.id
                LEFT JOIN product_images pi ON p.id = pi.product_id AND pi.is_primary = 1
                JOIN category_types ct ON p.category_type_id = ct.id
                JOIN categories cat ON ct.category_id = cat.id
                WHERE o.user_id = {session['user_id']}
                ORDER BY o.created_at DESC
            """)
            raw_orders = cur.fetchall()

            # 주문 내역에 날짜별로 그룹화하기
            current_date = None
            for order in raw_orders:
                if isinstance(order["created_at"], str):
                    order["created_at"] = datetime.strptime(order["created_at"], "%Y-%m-%d %H:%M:%S")
                order["image_url"] = f"uploads/{order['category']}/{order['category_type']}/{order['image']}"
                orders.append(order)

    conn.close()
    return render_template("login/profile.html", tab=tab, user=user, orders=orders)





# Existing view functions...
# ─────────────────────────────────────────────────────────────────────────────
# 주문취소
# ─────────────────────────────────────────────────────────────────────────────
@auth_bp.route("/cancel_order/<int:order_id>", methods=["POST"], endpoint="cancel_order")
def cancel_order(order_id):
    if "user_id" not in session:
        flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cur:
            # 주문이 본인의 것인지 + 상태 확인
            cur.execute(f"SELECT status, user_id FROM orders WHERE id = {order_id}")
            order = cur.fetchone()

            if not order or order["user_id"] != session["user_id"]:
                flash("잘못된 접근입니다.")
                return redirect(url_for("auth_bp.profile", tab="orders"))

            if order["status"] not in ("PENDING", "PAID"):
                flash("이 주문은 취소할 수 없습니다.")
                return redirect(url_for("auth_bp.profile", tab="orders"))

            # 주문 상태 업데이트
            cur.execute(f"UPDATE orders SET status = 'CANCELLED' WHERE id = {order_id}")
            conn.commit()

            flash("주문이 취소되었습니다.")
    finally:
        conn.close()

    return redirect(url_for("auth_bp.profile", tab="orders"))

@auth_bp.route("/update_address/<int:order_id>", methods=["GET", "POST"])
def update_address(order_id):
    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(f"SELECT * FROM orders WHERE id = {order_id}")
            order = cur.fetchone()

        # 주문이 존재하지 않거나 상태가 PENDING 또는 PAID가 아닌 경우, 접근을 막음
        if not order or order['status'] not in ['PENDING', 'PAID']:
            flash("배송지를 수정할 수 없습니다.", 'danger')
            return redirect(url_for('auth_bp.profile', tab='orders'))

        if request.method == 'POST':
            new_address = request.form.get('address')

            # 배송지 업데이트
            with conn.cursor() as cur:
                cur.execute(f"UPDATE orders SET address = '{new_address}', updated_at = NOW() WHERE id = {order_id}")
            conn.commit()
            flash("배송지가 수정되었습니다.", 'success')
            return redirect(url_for('auth_bp.profile', tab='orders'))

        return render_template("update_address.html", order=order)

    finally:
        conn.close()
