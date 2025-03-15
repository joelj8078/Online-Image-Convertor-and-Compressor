import os
import zipfile
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = "uploads"
CONVERTED_FOLDER = "converted"
ZIP_FOLDER = "zips"

# Ensure required folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["CONVERTED_FOLDER"] = CONVERTED_FOLDER
app.config["ZIP_FOLDER"] = ZIP_FOLDER

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

users = {"admin": "password123"}  # Simple user storage (Replace with a database in production)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def create_zip(files, zip_name="converted_images.zip"):
    zip_path = os.path.join(app.config["ZIP_FOLDER"], zip_name)
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))
    return zip_path

@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("upload"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username] == password:
            session["user"] = username
            flash("Login successful!", "success")
            return redirect(url_for("upload"))
        else:
            flash("Invalid username or password!", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users:
            flash("Username already exists!", "danger")
        else:
            users[username] = password
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if "files" not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)

        files = request.files.getlist("files")
        target_format = request.form.get("format")

        if not files or not target_format:
            flash("Please upload files and select a format!", "danger")
            return redirect(request.url)

        target_format = target_format.lower()
        if target_format == "jpg":
            target_format = "jpeg"

        converted_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(input_path)

                converted_filename = f"{os.path.splitext(filename)[0]}.{target_format}"
                output_path = os.path.join(app.config["CONVERTED_FOLDER"], converted_filename)

                with Image.open(input_path) as img:
                    if target_format in ["jpg", "jpeg"] and img.mode == "RGBA":
                        img = img.convert("RGB")

                    img.save(output_path, format=target_format.upper())

                converted_files.append(output_path)

        if converted_files:
            zip_filename = create_zip(converted_files)
            flash("Images converted successfully!", "success")
            return send_file(zip_filename, as_attachment=True)

    return render_template("upload.html")

if __name__ == "__main__":
    app.run(debug=True)
