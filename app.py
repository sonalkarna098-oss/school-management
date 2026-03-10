import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "super_secret_school_key"

# ================= DATABASE (MongoDB Atlas) =================
# Replace <db_password> with your actual password for the user 'Sonal'
atlas_uri = os.getenv("MONGO_URLI")

try:
    client = MongoClient(atlas_uri)
    db = client["management"]
    # Verify connection
    client.admin.command('ping')
    print("Successfully connected to MongoDB Atlas (Database: management)")
except Exception as e:
    print(f"Error connecting to MongoDB Atlas: {e}")

# ================= INSTITUTIONAL PAGES =================
@app.route("/")
def index():
    """Renders the official institutional landing page."""
    return render_template("index.html")

@app.route("/about")
def about():
    """Renders the professional institutional 'About Us' page."""
    return render_template("about.html")

@app.route("/courses")
def courses():
    """Renders the professional institutional 'Courses' page."""
    return render_template("courses.html")

@app.route("/calendar")
def calendar():
    """Renders the official institutional Academic Calendar page."""
    return render_template("calendar.html")

# ================= AUTHENTICATION =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        role = request.form.get("role")

        if db.users.find_one({"username": username}):
            return "User already exists! <a href='/signup'>Try again</a>"

        db.users.insert_one({
            "username": username,
            "password": password, 
            "role": role
        })
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.users.find_one({
            "username": username,
            "password": password,
            "role": role
        })

        if user:
            session["user_role"] = user["role"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            return f"Invalid Credentials for {role.capitalize()}! <a href='/login'>Try again</a>"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= CONSOLIDATED DASHBOARD & NOTIFICATIONS =================
@app.route("/dashboard")
def dashboard():
    """Consolidated dashboard with detailed teacher notifications."""
    if "user_role" not in session:
        return redirect(url_for("login"))
    
    new_applicants = []
    notif_count = 0
    
    # Notification logic: Fetch actual details of unviewed applicants for teachers
    if session.get('user_role') == 'teacher':
        new_applicants = list(db.admissions.find({"viewed": False}))
        notif_count = len(new_applicants)
    
    return render_template("dashboard.html", 
                           user_role=session["user_role"], 
                           notif_count=notif_count,
                           new_applicants=new_applicants)

@app.route("/clear_notifications")
def clear_notifications():
    """Marks all admission notifications as read for the teacher."""
    if session.get('user_role') == 'teacher':
        db.admissions.update_many({"viewed": False}, {"$set": {"viewed": True}})
    return redirect(url_for("dashboard"))

# ================= ADMISSIONS =================
@app.route("/admission", methods=["GET", "POST"])
def admission():
    """Handles new student applications and triggers teacher alerts."""
    if request.method == "POST":
        admission_data = {
            "full_name": request.form.get("full_name"),
            "email": request.form.get("email"),
            "course": request.form.get("course"),
            "status": "Pending",
            "viewed": False  # Triggers notification for teacher
        }
        db.admissions.insert_one(admission_data)
        # Returns the professional blurred 'Thank You' page
        return render_template("thanks.html")
    return render_template("admission.html")

# ================= STUDENT MANAGEMENT =================
@app.route("/students", methods=["GET","POST"])
def students():
    if "user_role" not in session: return redirect(url_for("login"))
    
    if request.method == "POST":
        if session.get("user_role") != "teacher":
            return "Unauthorized Action", 403
            
        db.students.insert_one({
            "name": request.form["name"],
            "roll_no": request.form["roll"],
            "class": request.form["class"],
            "section": request.form["section"]
        })
        return redirect(url_for("students"))

    selected_class = request.args.get("class")
    students_list = list(db.students.find({"class": selected_class})) if selected_class else list(db.students.find())
    return render_template("students.html", students=students_list)

@app.route("/delete_student/<id>")
def delete_student(id):
    if session.get("user_role") != "teacher": return "Unauthorized", 403
    db.students.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("students"))

@app.route("/update_student", methods=["POST"])
def update_student():
    if session.get("user_role") != "teacher": return "Unauthorized", 403
    student_id = request.form.get("id")
    db.students.update_one(
        {"_id": ObjectId(student_id)},
        {"$set": {
            "name": request.form["name"],
            "roll_no": request.form["roll"],
            "class": request.form["class"],
            "section": request.form["section"]
        }}
    )
    return redirect(url_for("students"))

# ================= ATTENDANCE =================
@app.route("/attendance", methods=["GET","POST"])
def attendance():
    if "user_role" not in session: return redirect(url_for("login"))
    
    if request.method == "POST":
        if session.get("user_role") != "teacher": return "Unauthorized", 403
        db.attendance.insert_one({
            "student_id": request.form["student_id"],
            "class": request.form["class"],
            "date": request.form["date"],
            "status": request.form["status"]
        })
        return redirect(url_for("attendance", class_no=request.form["class"]))

    selected_class = request.args.get("class_no")
    attendance_list = list(db.attendance.find({"class": selected_class})) if selected_class else []
    students_map = {str(s["_id"]): s["name"] for s in db.students.find()}
    for a in attendance_list:
        a["student_name"] = students_map.get(a["student_id"], "Unknown")

    return render_template("attendance.html", attendance_list=attendance_list, selected_class=selected_class)

@app.route("/delete_attendance/<id>")
def delete_attendance(id):
    if session.get("user_role") != "teacher": return "Unauthorized Action", 403
    db.attendance.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("attendance"))

# ================= MARKS =================
@app.route("/marks", methods=["GET","POST"])
def marks():
    if "user_role" not in session: return redirect(url_for("login"))
    
    if request.method == "POST":
        if session.get("user_role") != "teacher": return "Unauthorized", 403
        db.marks.insert_one({
            "student_id": request.form["student_id"],
            "class": request.form["class"],
            "subject": request.form["subject"].strip(),
            "marks": request.form["marks"],
            "exam": request.form["exam"]
        })
        return redirect(url_for("marks", class_no=request.form["class"], subject=request.form["subject"]))

    selected_class = request.args.get("class_no")
    selected_subject = request.args.get("subject")
    query = {}
    if selected_class: query["class"] = selected_class
    if selected_subject: query["subject"] = selected_subject

    marks_list = list(db.marks.find(query)) if query else []
    students_map = {str(s["_id"]): s["name"] for s in db.students.find()}
    for m in marks_list:
        m["student_name"] = students_map.get(m["student_id"], "Unknown")

    return render_template("marks.html", marks_list=marks_list, selected_class=selected_class, selected_subject=selected_subject)

@app.route("/delete_mark/<id>")
def delete_mark(id):
    if session.get("user_role") != "teacher": return "Unauthorized Action", 403
    db.marks.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("marks"))

@app.route("/update_marks", methods=["POST"])
def update_marks():
    if session.get("user_role") != "teacher": return "Unauthorized", 403
    mark_id = request.form.get("id")
    db.marks.update_one(
        {"_id": ObjectId(mark_id)},
        {"$set": {
            "subject": request.form["subject"],
            "marks": request.form["marks"],
            "exam": request.form["exam"]
        }}
    )
    return redirect(url_for("marks", class_no=request.form["class"]))

# ================= TIMETABLE =================
@app.route("/timetable", methods=["GET","POST"])
def timetable():
    if "user_role" not in session: return redirect(url_for("login"))
    
    if request.method == "POST":
        if session.get("user_role") != "teacher": return "Unauthorized", 403
        db.timetable.insert_one({
            "class": request.form["class"],
            "time": request.form["time"],
            "monday": request.form["monday"],
            "tuesday": request.form["tuesday"],
            "wednesday": request.form["wednesday"],
            "thursday": request.form["thursday"],
            "friday": request.form["friday"]
        })
        return redirect(url_for("timetable", class_name=request.form["class"]))

    selected_class = request.args.get("class_name")
    classes = [str(i) for i in range(1,11)]
    timetable_data = list(db.timetable.find({"class": selected_class})) if selected_class else []
    return render_template("timetable.html", 
                           classes=classes, 
                           selected_class=selected_class, 
                           timetable=timetable_data)

@app.route("/delete_timetable/<id>")
def delete_timetable(id):
    if session.get("user_role") != "teacher": return "Unauthorized", 403
    record = db.timetable.find_one({"_id": ObjectId(id)})
    class_to_return = record.get('class') if record else None
    db.timetable.delete_one({"_id": ObjectId(id)})
    return redirect(url_for("timetable", class_name=class_to_return) if class_to_return else url_for("timetable"))

@app.route("/update_timetable", methods=["POST"])
def update_timetable():
    if session.get("user_role") != "teacher": return "Unauthorized", 403
    timetable_id = request.form.get("id")
    class_val = request.form.get("class")
    db.timetable.update_one(
        {"_id": ObjectId(timetable_id)},
        {"$set": {
            "class": class_val,
            "time": request.form.get("time"),
            "monday": request.form.get("monday"),
            "tuesday": request.form.get("tuesday"),
            "wednesday": request.form.get("wednesday"),
            "thursday": request.form.get("thursday"),
            "friday": request.form.get("friday")
        }}
    )
    return redirect(url_for("timetable", class_name=class_val))

# ================= CONTACT & HELPERS =================
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        return "<h3>Thank you! We will contact you shortly.</h3><a href='/'>Return Home</a>"
    return render_template("contact.html")

@app.route("/get_students/<class_no>")
def get_students(class_no):
    students_cursor = db.students.find({"class": class_no})
    return jsonify([{"id": str(s["_id"]), "name": s["name"]} for s in students_cursor])

if __name__ == "__main__":
    app.run(debug=True)