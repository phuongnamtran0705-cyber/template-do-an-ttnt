from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import date
import database
import subprocess
import json
import sys
import os

app = Flask(__name__)
app.secret_key = "tro_ai_danang_secret_key" # Đặt secret key cho session

database.init_db()

@app.route("/", methods=["GET"])
def index():
    districts = database.distinct_districts()
    amenities = database.distinct_amenities()
    return render_template("index.html", districts=districts, amenities=amenities)

# --- ĐĂNG KÝ / ĐĂNG NHẬP / ĐĂNG XUẤT ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username_or_email = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = database.verify_user(username_or_email, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            return redirect(url_for("admin_dashboard" if user['role'] == 'admin' else "index"))
        else:
            flash("Mật khẩu hoặc tài khoản/email không chính xác!", "danger")

    return render_template("auth.html", mode="login")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# --- LIÊN HỆ HỎI PHÒNG - KHÔNG CẦN ĐĂNG NHẬP ---
 
@app.route("/lien-he/<int:room_id>", methods=["POST"])
def lien_he(room_id):
    from flask import jsonify
 
    customer_name = request.form.get("customer_name", "").strip()
    customer_phone = request.form.get("customer_phone", "").strip()
    note = request.form.get("note", "").strip()
 
    if not customer_name or not customer_phone:
        return jsonify(success=False, message="Vui lòng nhập đầy đủ họ tên và số điện thoại!"), 400
 
    room = database.get_room_by_id(room_id)
    if not room:
        return jsonify(success=False, message="Phòng trọ không tồn tại!"), 404
 
    success = database.add_inquiry(room_id, customer_name, customer_phone, note)
    if success:
        return jsonify(
            success=True,
            message=f"Đã gửi yêu cầu liên hệ! Số điện thoại chủ trọ: {room.get('so_dien_thoai', '0905123456')}",
            phone=room.get('so_dien_thoai', '0905123456'),
        )
    else:
        return jsonify(success=False, message="Có lỗi xảy ra, vui lòng thử lại!"), 500
 
 
@app.route("/admin/inquiries")
def admin_inquiries():
    """Admin xem danh sách khách đã để lại SĐT hỏi phòng nào."""
    if session.get('role') != 'admin':
        flash("Bạn không có quyền truy cập trang này!", "danger")
        return redirect(url_for("login"))
    inquiries = database.get_all_inquiries()
    return render_template("admin_inquiries.html", inquiries=inquiries)

# --- QUẢN TRỊ ADMIN ---

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get('role') != 'admin':
        flash("Bạn không có quyền truy cập trang quản trị!", "danger")
        return redirect(url_for("login"))
    rooms = database.get_all_rooms()
    return render_template("admin_dashboard.html", rooms=rooms)

@app.route("/admin/edit/<int:room_id>", methods=["GET", "POST"])
def admin_edit_room(room_id):
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
    
    room = database.get_room_by_id(room_id)
    if not room:
        flash("Phòng trọ không tồn tại!", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        room_data = {
            'title': request.form.get('title'),
            'gia_thue': int(request.form.get('gia_thue', 0)),
            'quan': request.form.get('quan'),
            'dien_tich': float(request.form.get('dien_tich', 0)),
            'tien_ich': request.form.get('tien_ich'),
            'mo_ta': request.form.get('mo_ta'),
            'so_dien_thoai': request.form.get('so_dien_thoai')
        }
        if database.update_room(room_id, room_data):
            flash("Cập nhật thông tin phòng trọ thành công!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Có lỗi xảy ra khi cập nhật!", "danger")

    return render_template("admin_edit.html", room=room)

@app.route("/admin/delete/<int:room_id>")
def admin_delete_room(room_id):
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
    database.delete_room(room_id)
    flash("Xóa phòng trọ thành công!", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/add", methods=["GET", "POST"])
def add_room():
    if session.get('role') != 'admin':
        flash("Vui lòng đăng nhập với quyền quản trị để thực hiện chức năng này!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        room_data = {
            'title': request.form.get('title'),
            'gia_thue': int(request.form.get('gia_thue', 0)),
            'quan': request.form.get('quan'),
            'dien_tich': float(request.form.get('dien_tich', 0)),
            'tien_ich': request.form.get('tien_ich'),
            'mo_ta': request.form.get('mo_ta'),
            'so_dien_thoai': request.form.get('so_dien_thoai') or '0905123456',
            'nguon': 'Đăng tay qua Admin',
            'url': '#',
            'nguoi_dang': session.get('full_name', 'Chủ trọ'),
            'user_id': session.get('user_id'),
        }
        if database.add_room(room_data):
            flash("Đăng tin phòng trọ thành công!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Có lỗi xảy ra khi lưu tin đăng!", "danger")

    return render_template("add_room.html")

# --- ROUTE SEARCH GIỮ NGUYÊN ---
@app.route("/search", methods=["POST"])
def search():
    raw_budget = request.form.get("budget", "").strip()
    raw_area = request.form.get("area_min", "").strip()
    district = request.form.get("district", "").strip()
    keyword = request.form.get("keyword", "").strip()
    selected_amenities = request.form.getlist("amenities")

    budget = int(raw_budget) if raw_budget.isdigit() else 0
    if 0 < budget < 10000:
        budget = budget * 1000

    area_min = float(raw_area) if raw_area.replace('.', '', 1).isdigit() else 0
    all_rooms = database.get_all_rooms()
    scored_rooms = []

    for room in all_rooms:
        score = 0
        price = room.get('gia_thue', 0)
        real_price = price * 1000 if price < 100000 else price

        if budget > 0 and real_price <= budget: score += 30
        if district and district.lower() in room.get('quan', '').lower(): score += 25
        if keyword and keyword.lower() in f"{room.get('title','')} {room.get('mo_ta','')}".lower(): score += 20
        
        room['match_score'] = score
        scored_rooms.append(room)

    scored_rooms.sort(key=lambda x: x['match_score'], reverse=True)
    return render_template("results.html", results=scored_rooms)

# tránh lỗi UnicodeEncodeError khi các script print() tiếng Việt có dấu.
_SUBPROCESS_ENV = os.environ.copy()
_SUBPROCESS_ENV["PYTHONIOENCODING"] = "utf-8"
_SUBPROCESS_ENV["PYTHONUTF8"] = "1"
 
@app.route("/admin/scrape", methods=["GET"])
def admin_scrape():
    if session.get('role') != 'admin':
        flash("Bạn không có quyền truy cập trang này!", "danger")
        return redirect(url_for("login"))
    return render_template("admin_scrape.html", results=None, log_output=None)
 
 
@app.route("/admin/scrape/run", methods=["POST"])
def admin_scrape_run():
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
 
    district = request.form.get("district", "quan-hai-chau")
    max_pages = request.form.get("max_pages", "1")
 
    log_lines = []
 
    log_lines.append(f"$ {sys.executable} 1_scraper_nhatot_v2.py --districts {district} --max-pages {max_pages}")
    result1 = subprocess.run(
        [sys.executable, "1_scraper_nhatot_v2.py", "--districts", district, "--max-pages", max_pages],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, env=_SUBPROCESS_ENV,
    )
    log_lines.append(result1.stdout)
    log_lines.append(result1.stderr)
 
    if result1.returncode != 0:
        flash("Cào dữ liệu thất bại - xem log bên dưới để biết chi tiết.", "danger")
        return render_template("admin_scrape.html", results=None, log_output="\n".join(log_lines))
 
    log_lines.append(f"$ {sys.executable} 2_normalize.py")
    result2 = subprocess.run(
        [sys.executable, "2_normalize.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, env=_SUBPROCESS_ENV,
    )
    log_lines.append(result2.stdout)
    log_lines.append(result2.stderr)
 
    results = []
    try:
        with open("normalized_listings.jsonl", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
    except FileNotFoundError:
        flash("Không tìm thấy file kết quả sau khi chuẩn hóa.", "danger")
 
    flash(f"Đã cào và chuẩn hóa {len(results)} tin. Xem bảng bên dưới, bấm 'Nhập vào Database' nếu muốn lưu.", "success")
    return render_template("admin_scrape.html", results=results, log_output="\n".join(log_lines))
 
 
@app.route("/admin/scrape/import", methods=["POST"])
def admin_scrape_import():
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
 
    result = subprocess.run(
        [sys.executable, "3_import_to_db.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60, env=_SUBPROCESS_ENV,
    )
 
    if result.returncode == 0:
        flash("Đã nhập dữ liệu vào Database thành công! Xem trong Quản lý phòng trọ.", "success")
    else:
        flash(f"Có lỗi khi nhập vào Database: {result.stderr}", "danger")
 
    return redirect(url_for("admin_dashboard"))
 

 # --- ĐÁNH GIÁ PHÒNG TRỌ - KHÔNG CẦN ĐĂNG NHẬP ---

@app.route("/danh-gia/<int:room_id>", methods=["POST"])
def danh_gia(room_id):
    from flask import jsonify

    customer_name = request.form.get("customer_name", "").strip()
    customer_phone = request.form.get("customer_phone", "").strip()
    rating = request.form.get("rating", "").strip()
    comment = request.form.get("comment", "").strip()

    if not customer_name or not customer_phone or not rating:
        return jsonify(success=False, message="Vui lòng nhập đầy đủ họ tên, SĐT và chọn số sao!"), 400

    if not rating.isdigit() or not (1 <= int(rating) <= 5):
        return jsonify(success=False, message="Số sao không hợp lệ!"), 400

    room = database.get_room_by_id(room_id)
    if not room:
        return jsonify(success=False, message="Phòng trọ không tồn tại!"), 404

    success, msg = database.add_review(room_id, customer_name, customer_phone, rating, comment)
    if success:
        return jsonify(success=True, message=msg)
    else:
        return jsonify(success=False, message=msg), 500


@app.route("/phong/<int:room_id>/danh-gia", methods=["GET"])
def xem_danh_gia(room_id):
    """Trả về JSON danh sách đánh giá công khai của 1 phòng - dùng cho modal xem đánh giá."""
    from flask import jsonify
    reviews = database.get_reviews_for_room(room_id)
    # Chuyển datetime thành string để jsonify được
    for r in reviews:
        r["created_at"] = str(r["created_at"])
    return jsonify(reviews=reviews)


@app.route("/admin/reviews")
def admin_reviews():
    """Admin xem và duyệt (xóa) đánh giá - phòng khi có review spam/không đúng sự thật."""
    if session.get('role') != 'admin':
        flash("Bạn không có quyền truy cập trang này!", "danger")
        return redirect(url_for("login"))
    reviews = database.get_all_reviews_admin()
    return render_template("admin_reviews.html", reviews=reviews)


@app.route("/admin/reviews/delete/<int:review_id>", methods=["POST"])
def admin_delete_review(review_id):
    if session.get('role') != 'admin':
        return redirect(url_for("login"))
    database.delete_review(review_id)
    flash("Đã xóa đánh giá.", "success")
    return redirect(url_for("admin_reviews"))
UNIVERSITIES = [
    {"name": "ĐH Bách Khoa - ĐH Đà Nẵng", "lat": 16.0725, "lng": 108.1500},
    {"name": "ĐH Sư Phạm - ĐH Đà Nẵng", "lat": 16.0682, "lng": 108.1522},
    {"name": "ĐH Kinh Tế - ĐH Đà Nẵng", "lat": 16.0336, "lng": 108.2406},
    {"name": "ĐH Ngoại Ngữ - ĐH Đà Nẵng", "lat": 16.0279, "lng": 108.2086},
    {"name": "ĐH Duy Tân (cơ sở Nguyễn Văn Linh)", "lat": 16.0619, "lng": 108.2171},
    {"name": "ĐH Đông Á", "lat": 16.0553, "lng": 108.2205},
]
 
 
@app.route("/ban-do-nhiet", methods=["GET"])
def ban_do_nhiet():
    """Bản đồ nhiệt mật độ phòng trọ + tính khoảng cách tới trường - không cần đăng nhập."""
    rooms = database.get_rooms_with_coords()
    return render_template("ban_do_nhiet.html", rooms=rooms, universities=UNIVERSITIES)

if __name__ == "__main__":
    app.run(debug=True, port=5000)