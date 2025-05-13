from flask import session, flash, redirect, url_for
import json
from pathlib import Path
from flask import Blueprint, render_template, request, current_app
import os
from collections import defaultdict
import uuid

product_bp = Blueprint("product_bp", __name__)
# 업로드 디렉터리 설정 (app.py에서 UPLOAD_FOLDER 설정 권장)
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
BASE_DIR   = Path(__file__).resolve().parents[2]  # shopping_web/

# ─────────────────────────────────────────────────────────────────────────────
# 상품 상세
# ─────────────────────────────────────────────────────────────────────────────
@product_bp.route("/product/<int:product_id>", endpoint="product_detail")
def product_detail(product_id: int):
    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(f"""
                SELECT
                    p.id, p.name, p.description, p.price, p.stock_quantity,
                    p.created_at, p.updated_at,
                    ct.name AS type_name,
                    c.name AS category_name,
                    pi.url AS image
                FROM products p
                JOIN category_types ct ON p.category_type_id = ct.id
                JOIN categories c ON ct.category_id = c.id
                LEFT JOIN product_images pi
                  ON pi.product_id = p.id AND pi.is_primary = 1
                WHERE p.id = {product_id}
                """)
            product = cursor.fetchone()

            # 이미지 경로 조립
            if product and product.get("image"):
                product["image_url"] = url_for(
                    "static",
                    filename=f"uploads/{product['category_name']}/{product['type_name']}/{product['image']}"
                )
    finally:
        conn.close()

    return render_template(
        "product/product_detail.html",
        product=product
    )


# ─────────────────────────────────────────────────────────────────────────────
# 상품 목록 (카테고리 필터)
# ─────────────────────────────────────────────────────────────────────────────
@product_bp.route("/products", endpoint="products")
def products():
    selected_category = request.args.get("category")
    selected_type = request.args.get("type")
    search_query = request.args.get("q")

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            # ─── 카테고리 + 타입 ───
            cursor.execute("SELECT id, name FROM categories ORDER BY name")
            categories = cursor.fetchall()
            cursor.execute("SELECT id, category_id, name FROM category_types ORDER BY name")
            types = cursor.fetchall()

            # 하위 타입을 상위 카테고리에 묶기
            from collections import defaultdict
            grouped = defaultdict(list)
            for t in types:
                grouped[t["category_id"]].append(t)
            for cat in categories:
                cat["types"] = grouped.get(cat["id"], [])

            # ─── 상품 목록 쿼리 ───
            query = """
                SELECT
                    p.id, p.name, p.description, p.price, p.stock_quantity,
                    p.created_at, p.updated_at,
                    ct.name AS type_name,
                    c.name AS category_name,
                    pi.url AS image
                FROM products p
                JOIN category_types ct ON p.category_type_id = ct.id
                JOIN categories c ON ct.category_id = c.id
                LEFT JOIN product_images pi
                  ON pi.product_id = p.id AND pi.is_primary = 1
            """
            where_clauses = []
            params = []

            if selected_category:
                category_id = next((c["id"] for c in categories if c["name"] == selected_category), None)

                if selected_type:
                    type_ids = [t["id"] for t in types if t["category_id"] == category_id and t["name"] == selected_type]
                    if type_ids:
                        where_clauses.append("p.category_type_id IN (" + ",".join(["%s"] * len(type_ids)) + ")")
                        params.extend(type_ids)
                else:
                    type_ids = [t["id"] for t in types if t["category_id"] == category_id]
                    if type_ids:
                        where_clauses.append("p.category_type_id IN (" + ",".join(["%s"] * len(type_ids)) + ")")
                        params.extend(type_ids)

            if search_query:
                where_clauses.append("(p.name LIKE %s OR ct.name LIKE %s)")
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)
            query += " ORDER BY p.created_at DESC"

            raw_query = query % tuple(params) if params else query
            cursor.execute(raw_query)
            products = cursor.fetchall()

            # 🔥 이미지 경로 재구성
            for product in products:
                if product['image']:
                    product['image_path'] = f"uploads/{product['category_name']}/{product['type_name']}/{product['image']}"
                else:
                    product['image_path'] = "default.jpg"  # 대체 이미지

    finally:
        conn.close()

    return render_template(
        "product/product.html",
        products=products,
        selected_category=selected_category,
        selected_type=selected_type,
        search_query=search_query,
        categories=categories
    )


# 업로드 루트 설정
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'Fronts', 'static', 'uploads')

def get_upload_path(category_name, type_name):
    rel_path = os.path.join("..", "Fronts", "static", "uploads", category_name, type_name)
    # 절대 경로 변환 후 반환
    return os.path.abspath(os.path.join(current_app.root_path, rel_path))

@product_bp.route("/new", methods=["GET", "POST"], endpoint="create_product")
def create_product():
    if not session.get("is_admin") == 1:
        flash("관리자 권한이 필요합니다.")
        return redirect(url_for("product_bp.products"))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, name FROM categories ORDER BY name")
            categories = cursor.fetchall()

            cursor.execute("SELECT id, category_id, name FROM category_types ORDER BY name")
            types = cursor.fetchall()
    finally:
        conn.close()

    grouped = defaultdict(list)
    for t in types:
        grouped[t["category_id"]].append(t)
    for cat in categories:
        cat["types"] = grouped.get(cat["id"], [])

    if request.method == "POST":
        name = request.form["name"]
        category_type_id = request.form["category_type_id"]
        price = request.form["price"]
        description = request.form["description"]
        stock_quantity = request.form["stock_quantity"]

        file = request.files.get("image")
        if not file or file.filename == "":
            flash("이미지를 업로드해주세요.")
            return redirect(url_for("product_bp.create_product"))

        ext = os.path.splitext(file.filename)[1]  # 예: '.jpg'
        filename = f"{uuid.uuid4().hex}{ext}"

        conn = current_app.get_db_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(f"""
                    SELECT c.name AS category_name, ct.name AS type_name
                    FROM category_types ct
                    JOIN categories c ON ct.category_id = c.id
                    WHERE ct.id = {category_type_id}
                """)
                cat_info = cursor.fetchone()

                category_name = cat_info["category_name"]
                type_name = cat_info["type_name"]
                upload_folder = get_upload_path(category_name, type_name)
                os.makedirs(upload_folder, exist_ok=True)

                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)

                relative_path = f"{filename}"

                cursor.execute(f"""
                    INSERT INTO products (name, category_type_id, description, price, stock_quantity, created_at, updated_at)
                    VALUES ('{name}', {category_type_id}, '{description}', {price}, {stock_quantity}, NOW(), NOW())
                """)

                product_id = cursor.lastrowid

                cursor.execute(f"""
                    INSERT INTO product_images (product_id, url, is_primary)
                    VALUES ({product_id}, '{relative_path}', 1)
                """)

                conn.commit()
        finally:
            conn.close()

        flash("상품이 등록되었습니다.")
        return redirect(url_for("product_bp.products"))

    return render_template("admin/create_product.html", categories=categories)



import os
from flask import current_app

@product_bp.route("/product/delete/<int:product_id>", methods=["POST"], endpoint="delete_product")
def delete_product(product_id):
    if not session.get("is_admin"):
        flash("관리자 권한이 필요합니다.")
        return redirect(url_for("product_bp.product_detail", product_id=product_id))

    conn = current_app.get_db_connection()
    image_path = None

    try:
        with conn.cursor(dictionary=True) as cursor:
            # 🔍 1. 이미지 경로를 먼저 조회
            cursor.execute("""
                SELECT pi.url, ct.name AS type_name, c.name AS category_name
                FROM product_images pi
                JOIN products p ON pi.product_id = p.id
                JOIN category_types ct ON p.category_type_id = ct.id
                JOIN categories c ON ct.category_id = c.id
                WHERE pi.product_id = %s AND pi.is_primary = 1
            """, (product_id,))
            row = cursor.fetchone()
            if row:
                filename = row["url"]
                category = row["category_name"]
                type_name = row["type_name"]
                image_path = os.path.join(
                    current_app.root_path, "..", "Fronts", "static", "uploads",
                    category, type_name, filename
                )

        # 🔄 실제 삭제 실행 (커서 재사용)
        with conn.cursor() as cursor:
            cursor.execute(f"DELETE FROM order_items WHERE product_id = {product_id}")
            cursor.execute(f"DELETE FROM carts WHERE product_id = {product_id}")
            cursor.execute(f"DELETE FROM product_images WHERE product_id = {product_id}")
            cursor.execute(f"DELETE FROM products WHERE id = {product_id}")
        conn.commit()

    finally:
        conn.close()

    # 🔥 파일 삭제
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except Exception as e:
            current_app.logger.warning(f"이미지 삭제 실패: {e}")

    flash("상품이 완전히 삭제되었습니다.")
    return redirect(url_for("admin_bp.manage_products"))
