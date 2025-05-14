from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, current_app
)
import mysql.connector
from mysql.connector import errors
from werkzeug.utils import secure_filename
import os
from markupsafe import escape

def save_image(file, entity_id):
    from werkzeug.utils import secure_filename
    import os
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1]
    save_name = f"{entity_id}{ext}"
    upload_folder = os.path.join(current_app.root_path, os.pardir, "Fronts", "static", "inquiries_image")
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, save_name)
    file.save(save_path)
    return f"inquiries_image/{save_name}"

def delete_image(image_path):
    import os
    full_path = os.path.join(current_app.root_path, os.pardir, "Fronts", "static", image_path)
    if os.path.exists(full_path):
        os.remove(full_path)

contact_bp = Blueprint("contact_bp", __name__)

# ─────────────────────────────────────────────────────────────────────────────
# 게시글 목록
# ─────────────────────────────────────────────────────────────────────────────
@contact_bp.route("/contact", endpoint="contact")
def contact():
    board_type = request.args.get("type", "QNA")
    page = int(request.args.get("page", 1))  # 현재 페이지
    per_page = 10
    offset = (page - 1) * per_page

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            # 총 글 수 구하기
            cursor.execute("SELECT COUNT(*) AS count FROM inquiries WHERE type = %s", (board_type,))
            total = cursor.fetchone()["count"]
            total_pages = (total + per_page - 1) // per_page  # 전체 페이지 수

            # 현재 페이지 글만 가져오기
            cursor.execute("""
                SELECT i.id, i.title, i.created_at, u.nickname
                FROM inquiries i
                JOIN users u ON i.user_id = u.id
                WHERE i.type = %s
                ORDER BY i.created_at DESC
                LIMIT %s OFFSET %s
            """, (board_type, per_page, offset))
            posts = cursor.fetchall()
    finally:
        conn.close()

    return render_template("contact/contact.html",
                           posts=posts,
                           board_type=board_type,
                           page=page,
                           total_pages=total_pages)


# ─────────────────────────────────────────────────────────────────────────────
# 글쓰기
# ─────────────────────────────────────────────────────────────────────────────
@contact_bp.route("/contact/write", methods=["GET", "POST"], endpoint="write_post")
def write_post():
    if "user_id" not in session:
        #flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    board_type = request.args.get("type", "QNA")

    if request.method == "POST":
        title   = request.form["title"]
        content = request.form["content"]
        user_id = session["user_id"]
        file    = request.files.get("image")

        # 관리자는 type을 선택할 수 있음
        if session.get("is_admin"):
            board_type = request.form.get("type", board_type)

        # 서버 사이드 검증
        errors = []
        title = title.strip()
        content = content.strip()
        # 제목 검증: 필수, 최대 200자
        if not title:
            errors.append("제목을 입력하세요.")
        elif len(title) > 200:
            errors.append("제목은 200자 이하로 입력해야 합니다.")
        # 내용 검증: 필수, 최대 2000자
        if not content:
            errors.append("내용을 입력하세요.")
        elif len(content) > 2000:
            errors.append("내용은 2000자 이하로 입력해야 합니다.")
        # 게시판 타입 검증
        allowed_types = ["NOTICE", "FAQ", "QNA"]
        if board_type not in allowed_types:
            errors.append("유효하지 않은 게시판 타입입니다.")

        if errors:
            for e in errors:
                flash(e)
            return render_template(
                "contact/write_post.html",
                board_type=board_type,
                title=escape(title),
                content=escape(content)
            )

        conn = current_app.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO inquiries (user_id, type, title, content)
                    VALUES ({user_id}, '{board_type}', '{title}', '{content}')
                """)
                conn.commit()

                cur.execute("SELECT LAST_INSERT_ID()")
                post_id = cur.fetchone()[0]

                if file and file.filename:
                    image_db_path = save_image(file, post_id)
                    cur.execute(
                        "UPDATE inquiries SET image_path = %s WHERE id = %s",
                        (image_db_path, post_id)
                    )
                    conn.commit()
        finally:
            conn.close()

        
        return redirect(url_for("contact_bp.contact", type=board_type))

    return render_template("contact/write_post.html", board_type=board_type)


# 게시글 수정
@contact_bp.route("/contact/edit/<int:inquiry_id>", methods=["GET", "POST"], endpoint="edit_post")
def edit_post(inquiry_id):
    if "user_id" not in session:
        #flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(f"SELECT * FROM inquiries WHERE id = {inquiry_id}")
            inquiry = cursor.fetchone()

            if not inquiry:
                #flash("글을 찾을 수 없습니다.")
                return redirect(url_for("contact_bp.contact", type="QNA"))

            if session["user_id"] != inquiry["user_id"] and not session.get("is_admin"):
                #flash("수정 권한이 없습니다.")
                return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))

            if request.method == "POST":
                title = request.form["title"]
                content = request.form["content"]
                file = request.files.get("image")

                # 서버 사이드 검증
                errors = []
                title = title.strip()
                content = content.strip()
                if not title:
                    errors.append("제목을 입력하세요.")
                elif len(title) > 200:
                    errors.append("제목은 200자 이하로 입력해야 합니다.")
                if not content:
                    errors.append("내용을 입력하세요.")
                elif len(content) > 2000:
                    errors.append("내용은 2000자 이하로 입력해야 합니다.")
                if errors:
                    for e in errors:
                        flash(e)
                    return render_template(
                        "contact/write_post.html",
                        board_type=inquiry["type"],
                        inquiry=inquiry,
                        title=escape(title),
                        content=escape(content)
                    )

                # 이미지 처리: 기존 이미지 삭제 후 새 이미지 저장
                if file and file.filename:
                    if inquiry.get("image_path"):
                        delete_image(inquiry["image_path"])
                    image_db_path = save_image(file, inquiry_id)
                    cursor.execute(
                        "UPDATE inquiries SET image_path = %s WHERE id = %s",
                        (image_db_path, inquiry_id)
                    )
                    conn.commit()

                # 제목과 내용 업데이트
                cursor.execute(f"UPDATE inquiries SET title = '{title}', content = '{content}' WHERE id = {inquiry_id}")

                conn.commit()

                #flash("게시글이 수정되었습니다.")
                return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))
    finally:
        conn.close()

    return render_template("contact/write_post.html", board_type=inquiry["type"], inquiry=inquiry)



# ─────────────────────────────────────────────────────────────────────────────
# 게시글 삭제
# ─────────────────────────────────────────────────────────────────────────────
@contact_bp.route("/contact/delete/<int:inquiry_id>", methods=["POST"], endpoint="delete_post")
def delete_post(inquiry_id):
    if "user_id" not in session:
        #flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            # 게시글 조회
            cursor.execute(f"SELECT * FROM inquiries WHERE id = {inquiry_id}")
            inquiry = cursor.fetchone()

            if not inquiry:
                #flash("게시글이 존재하지 않습니다.")
                return redirect(url_for("contact_bp.contact", type="QNA"))

            # 삭제 권한 확인
            if session["user_id"] != inquiry["user_id"] and not session.get("is_admin"):
                #flash("삭제 권한이 없습니다.")
                return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))

            # 답변 삭제: 해당 문의글에 달린 답변들을 삭제
            cursor.execute(f"DELETE FROM answers WHERE inquiry_id = {inquiry_id}")
            conn.commit()

            # 게시글에 이미지가 있으면 삭제
            if inquiry.get("image_path"):
                image_path = os.path.join(current_app.root_path, "static", inquiry["image_path"])
                if os.path.exists(image_path):
                    os.remove(image_path)

            # 게시글 삭제
            cursor.execute(f"DELETE FROM inquiries WHERE id = {inquiry_id}")
            conn.commit()

        #flash("게시글과 답변이 삭제되었습니다.")
    except Exception as e:
        conn.rollback()  # 오류 발생 시 롤백
        #flash("게시글 삭제 중 오류가 발생했습니다.")
    finally:
        conn.close()

    return redirect(url_for("contact_bp.contact", type=inquiry["type"]))



# ─────────────────────────────────────────────────────────────────────────────
# 게시글 상세
# ─────────────────────────────────────────────────────────────────────────────
@contact_bp.route("/contact/inquiry/<int:inquiry_id>", methods=["GET", "POST"], endpoint="inquiry_detail")
def inquiry_detail(inquiry_id):
    conn = current_app.get_db_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            # 문의글 조회
            cursor.execute(f"""
                SELECT i.*, u.nickname
                FROM inquiries i
                JOIN users u ON i.user_id = u.id
                WHERE i.id = {inquiry_id}
            """)
            inquiry = cursor.fetchone()

            # 해당 문의글에 대한 답변 조회
            cursor.execute(f"""
                SELECT a.*, u.nickname AS answerer
                FROM answers a
                JOIN users u ON a.user_id = u.id
                WHERE a.inquiry_id = {inquiry_id}
            """)
            answers = cursor.fetchall()

            # 답변이 이미 있다면 답변 수정 폼을 띄우고, 새 답변을 추가하지 않음
            if len(answers) > 0:
                
                answer_to_edit = answers[0]  # 첫 번째 답변만 수정 가능하도록 설정
            else:
                answer_to_edit = None

            # 답변 등록 및 수정 처리 (POST 요청)
            if request.method == "POST":
                if not session.get('is_admin'):
                    #flash("관리자만 답변을 작성하거나 수정할 수 있습니다.")
                    return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))

                answer_content = request.form.get("content")
                answer_id = request.form.get("answer_id")  # 수정할 답변의 ID

                if not answer_content:
                    #flash("답변 내용을 입력하세요.")
                    return render_template("contact/inquiry_detail.html", inquiry=inquiry, answers=answers, answer_to_edit=answer_to_edit)

                # 답변 등록 또는 수정
                if not answer_id:  # 새로운 답변 등록
                    cursor.execute(f"""
                        INSERT INTO answers (inquiry_id, user_id, content)
                        VALUES ({inquiry_id}, {session["user_id"]}, '{answer_content}')
                    """)
                else:  # 기존 답변 수정
                    cursor.execute(f"""
                        UPDATE answers 
                        SET content = '{answer_content}', updated_at = NOW() 
                        WHERE id = {answer_id}
                    """)

                conn.commit()
                
                return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))

    finally:
        conn.close()

    if not inquiry:
        
        return redirect(url_for("contact_bp.contact", type='QNA'))

    return render_template("contact/inquiry_detail.html", inquiry=inquiry, answers=answers, answer_to_edit=answer_to_edit)




# ─────────────────────────────────────────────────────────────────────────────
# 게시글 답변 추가
# ─────────────────────────────────────────────────────────────────────────────
@contact_bp.route("/contact/answer/<int:inquiry_id>", methods=["POST"], endpoint="add_answer")
def add_answer(inquiry_id):
    if "user_id" not in session:
        #flash("로그인이 필요합니다.")
        return redirect(url_for("auth_bp.login"))

    content = request.form["content"]

    # 서버 사이드 검증
    if not content:
        
        return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))

    conn = current_app.get_db_connection()
    try:
        with conn.cursor() as cur:
            # 답변을 answers 테이블에 저장
            cur.execute(f"""
                INSERT INTO answers (inquiry_id, user_id, content)
                VALUES ({inquiry_id}, {session["user_id"]}, '{content}')
            """)
            conn.commit()
            
    finally:
        conn.close()

    return redirect(url_for("contact_bp.inquiry_detail", inquiry_id=inquiry_id))
