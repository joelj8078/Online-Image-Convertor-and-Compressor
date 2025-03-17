import os
import json
import zipfile
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this in production

UPLOAD_FOLDER = "uploads"
CONVERTED_FOLDER = "converted"
ZIP_FOLDER = "zips"
USERS_FILE = "users.json"  # File to store user accounts

# Ensure required folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["CONVERTED_FOLDER"] = CONVERTED_FOLDER
app.config["ZIP_FOLDER"] = ZIP_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "tiff", "ico"}

# Function to load users from file
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

# Function to save users to file
def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

# Load users from file
users = load_users()

# Function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Function to create ZIP archive
def create_zip(files, zip_name="converted_images.zip"):
    zip_path = os.path.join(app.config["ZIP_FOLDER"], zip_name)
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))
    return zip_path

# Strong password validation with detailed messages
def is_strong_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character."
    return None

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
            password_error = is_strong_password(password)
            if password_error:
                flash(password_error, "danger")
            else:
                users[username] = password
                save_users(users)  # Save users to file
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

                try:
                    file.save(input_path)
                except Exception as e:
                    flash(f"Error saving file: {str(e)}", "danger")
                    return redirect(request.url)

                converted_filename = f"{os.path.splitext(filename)[0]}.{target_format}"
                output_path = os.path.join(app.config["CONVERTED_FOLDER"], converted_filename)

                try:
                    with Image.open(input_path) as img:
                        if target_format in ["jpg", "jpeg"] and img.mode == "RGBA":
                            img = img.convert("RGB")

                        img.save(output_path, format=target_format.upper())

                    converted_files.append(output_path)
                except Exception as e:
                    flash(f"Error converting image: {str(e)}", "danger")
                    return redirect(request.url)

        if converted_files:
            zip_filename = create_zip(converted_files)
            flash("Images converted successfully!", "success")
            return send_file(zip_filename, as_attachment=True)

    return render_template("upload.html", formats=ALLOWED_EXTENSIONS)

if __name__ == "__main__":
    app.run(debug=True)
