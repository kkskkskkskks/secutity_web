# shopping_web/blueprints/checkout.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from datetime import datetime

checkout_bp = Blueprint("checkout_bp", __name__)

@checkout_bp.route("/checkout", methods=["GET", "POST"], endpoint="checkout")
def checkout():
    if "user_id" not in session:
        flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    cart = session.get("cart", [])
    if not cart:
        flash("장바구니가 비어 있습니다.")
        return redirect(url_for("cart_bp.cart"))

    conn = current_app.get_db_connection()
    try:
        # Fetch products and compute total
        products = []
        total_price = 0
        with conn.cursor(dictionary=True) as cursor:
            for item in cart:
                cursor.execute(f"SELECT * FROM products WHERE id = {item['product_id']}")
                product = cursor.fetchone()
                if product:
                    qty = int(item["quantity"])
                    subtotal = product["price"] * qty
                    total_price += subtotal
                    products.append({
                        "id":       product["id"],
                        "name":     product["name"],
                        "price":    product["price"],  # ✅ 올바른 단가
                        "quantity": qty,
                        "subtotal": subtotal
                    })

        if request.method == "POST":
            address = request.form["address"] + " " + request.form["detail_address"]
            payment_method = request.form["payment_method"]
            user_id = session["user_id"]

            with conn.cursor() as cur:
                # 주문 저장
                sql = f"INSERT INTO orders (user_id, address, payment_method, total_amount) VALUES ({user_id}, '{address}', '{payment_method}', {total_price})"
                cur.execute(sql)
                order_id = cur.lastrowid

                # 주문 상세 저장 - ✅ 단가만 저장
                for p in products:
                    sql = f"INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES ({order_id}, {p['id']}, {p['quantity']}, {p['price']})"
                    cur.execute(sql)

            conn.commit()
            session.pop("cart", None)
            return redirect(url_for("checkout_bp.complete", order_id=order_id))
    finally:
        conn.close()

    return render_template("checkout/checkout.html", products=products, total_price=total_price)

@checkout_bp.route("/checkout/complete/<int:order_id>", endpoint="complete")
def checkout_complete(order_id):
    if "user_id" not in session:
        flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            # 주문 정보
            cursor.execute(f"SELECT * FROM orders WHERE id = {order_id}")
            order = cursor.fetchone()

            # 주문 상세 항목
            cursor.execute(f"""
                SELECT oi.*, p.name
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = {order_id}
            """)
            items = cursor.fetchall()

            # ✅ 총합 다시 계산 (단가 * 수량)
            if order:
                order['total_price'] = sum(item['quantity'] * item['unit_price'] for item in items)
    finally:
        conn.close()

    if not order:
        flash("주문 정보를 찾을 수 없습니다.")
        return redirect(url_for("cart_bp.cart"))

    return render_template("checkout/checkout_complete.html", order=order, items=items)
