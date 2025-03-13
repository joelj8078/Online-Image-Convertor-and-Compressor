from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import os
import json
import zipfile
import io
import cairosvg  # Required for SVG conversion

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "converted"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}
USER_DB = "users.json"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Load users from JSON file
def load_users():
    if os.path.exists(USER_DB):
        with open(USER_DB, "r") as f:
            return json.load(f)
    return {}

# Save users to JSON file
def save_users(users):
    with open(USER_DB, "w") as f:
        json.dump(users, f)

# Helper function to check allowed file types
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Redirect to login if not authenticated
@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("upload"))
    return redirect(url_for("login"))

@app.route("/auth/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        users = load_users()

        if username in users:
            flash("Username already exists!", "danger")
        else:
            users[username] = password
            save_users(users)
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/auth/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        users = load_users()

        if username in users and users[username] == password:
            session["user"] = username
            flash("Login successful!", "success")
            return redirect(url_for("upload"))
        else:
            flash("Invalid credentials, please try again.", "danger")

    return render_template("login.html")

@app.route("/auth/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        flash("You must be logged in to access this page.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        files = request.files.getlist("file")
        format_type = request.form.get("format", "").lower()
        converted_files = []

        if not files or files[0].filename == "":
            flash("No file selected!", "danger")
            return redirect(request.url)

        if format_type not in ALLOWED_EXTENSIONS:
            flash("Invalid conversion format!", "danger")
            return redirect(request.url)

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                converted_filename = convert_image(filepath, format_type)
                if converted_filename:
                    converted_files.append(converted_filename)

        if converted_files:
            if len(converted_files) > 1:
                zip_filename = create_zip(converted_files)
                flash("Files uploaded and converted successfully!", "success")
                return redirect(url_for("download_zip", filename=zip_filename))
            else:
                flash("File uploaded and converted successfully!", "success")
                return redirect(url_for("download", filename=converted_files[0]))

    return render_template("upload.html")

# Convert and compress image
def convert_image(filepath, format_type):
    try:
        img = Image.open(filepath)
        output_filename = os.path.splitext(os.path.basename(filepath))[0] + f".{format_type}"
        output_path = os.path.join(app.config["OUTPUT_FOLDER"], output_filename)

        # Fix for JPG conversion (convert to RGB)
        if format_type in ["jpg", "jpeg"]:
            img = img.convert("RGB")
            img.save(output_path, format="JPEG", quality=85)

        # Fix for SVG conversion
        elif format_type == "svg":
            png_bytes = io.BytesIO()
            img.save(png_bytes, format="PNG")  # Convert image to PNG first
            png_bytes.seek(0)
            svg_data = cairosvg.svg2svg(bytestring=png_bytes.getvalue())  # Convert PNG to SVG
            with open(output_path, "wb") as f:
                f.write(svg_data)

        # Other formats (PNG, GIF, WEBP, BMP)
        else:
            img.save(output_path, format=format_type.upper())

        return output_filename
    except Exception as e:
        flash(f"Error in conversion: {str(e)}", "danger")
        return None

# Create a ZIP file for batch downloads
def create_zip(files):
    zip_filename = "converted_images.zip"
    zip_path = os.path.join(app.config["OUTPUT_FOLDER"], zip_filename)
    
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in files:
            file_path = os.path.join(app.config["OUTPUT_FOLDER"], file)
            zipf.write(file_path, file)
    
    return zip_filename

@app.route("/download/<filename>")
def download(filename):
    filepath = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash("File not found!", "danger")
    return redirect(url_for("upload"))

@app.route("/download_zip/<filename>")
def download_zip(filename):
    zip_path = os.path.join(app.config["OUTPUT_FOLDER"], filename)
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True)
    flash("ZIP file not found!", "danger")
    return redirect(url_for("upload"))

if __name__ == "__main__":
    app.run(debug=True)
