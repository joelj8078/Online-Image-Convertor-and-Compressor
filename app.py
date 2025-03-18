import os
import json
import zipfile
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from PIL import Image

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this in production

UPLOAD_FOLDER = "uploads"
CONVERTED_FOLDER = "converted"
COMPRESSED_FOLDER = "compressed"
ZIP_FOLDER = "zips"
USERS_FILE = "users.json"  # File to store user accounts

# Ensure required folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONVERTED_FOLDER, exist_ok=True)
os.makedirs(COMPRESSED_FOLDER, exist_ok=True)
os.makedirs(ZIP_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["CONVERTED_FOLDER"] = CONVERTED_FOLDER
app.config["COMPRESSED_FOLDER"] = COMPRESSED_FOLDER
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
def create_zip(files, zip_name="output.zip"):
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
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username in users and users[username] == password:
            session["user"] = username
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
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
                save_users(users)
                flash("Registration successful! You can now log in.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")

@app.route("/convert", methods=["GET", "POST"])
def convert():
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
            target_format = "jpeg"  # Pillow only recognizes "JPEG"

        if target_format not in ALLOWED_EXTENSIONS:
            flash("Invalid format selected!", "danger")
            return redirect(request.url)

        converted_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(input_path)

                if target_format == "jpeg":
                    converted_filename = f"{os.path.splitext(filename)[0]}.jpeg"  # Keep .jpeg extension
                    save_format = "JPEG"
                
                else:
                    converted_filename = f"{os.path.splitext(filename)[0]}.{target_format}"
                    save_format = target_format.upper()

                output_path = os.path.join(app.config["CONVERTED_FOLDER"], converted_filename)

                try:
                    with Image.open(input_path) as img:
                        # Fix for "cannot write mode RGBA as JPEG" error
                        if save_format == "JPEG" and img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")

                        img.save(output_path, format=target_format.upper())
                    converted_files.append(output_path)
                except Exception as e:
                    flash(f"Error converting image: {str(e)}", "danger")
                    return redirect(request.url)

        if converted_files:
            zip_filename = create_zip(converted_files, "converted_images.zip")
            flash("Images converted successfully!", "success")
            return send_file(zip_filename, as_attachment=True)

    return render_template("convert.html", formats=ALLOWED_EXTENSIONS)

@app.route("/compress", methods=["GET", "POST"])
def compress():
    if "user" not in session:
        return redirect(url_for("login"))
    
    compressed_images = []  # ✅ Define this at the start

    if request.method == "POST":
        files = request.files.getlist("files")
        compression_level = request.form.get("compression", "medium").lower()

        if not files:
            flash("Please upload files to compress!", "danger")
            return redirect(request.url)
        
        # Quality mapping for JPEG/JPG (Higher value → Higher quality, larger file)
        jpeg_quality_mapping = {"low": 30, "medium": 60, "high": 90}
        jpeg_quality = jpeg_quality_mapping.get(compression_level, 60)

        # Compression level mapping for PNG (Lower value → Higher quality, larger file)
        png_color_mapping = {"low": 32, "medium": 64, "high": 128}  # Reduce colors
        png_colors = png_color_mapping.get(compression_level, 64)

        compressed_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(input_path)

                compressed_filename = f"compressed_{filename}"
                output_path = os.path.join(app.config["COMPRESSED_FOLDER"], compressed_filename)

                try:
                    with Image.open(input_path) as img:
                        original_size = os.path.getsize(input_path) / 1024  # Convert to KB

                        if img.format.lower() in ["jpeg", "jpg", "webp"]:
                            img.save(output_path, quality=jpeg_quality, optimize=True)
                        elif img.format.lower() == "png":
                            img = img.convert("P", palette=Image.ADAPTIVE, colors=png_colors)  
                            img.save(output_path, format="PNG", optimize=True)
                    
                        compressed_size = os.path.getsize(output_path) / 1024  # Convert to KB
                        compressed_images.append({
                            "filename": compressed_filename,
                            "original_size": round(original_size, 2),
                            "compressed_size": round(compressed_size, 2),
                            "path": f"compressed/{compressed_filename}"  # ✅ Correct relative path
                        })
                except Exception as e:
                    flash(f"Error compressing image: {str(e)}", "danger")
                    

        return render_template("compress.html", compressed_images=compressed_images)
    
    return render_template("compress.html", compressed_images=[])

@app.route("/crop", methods=["GET", "POST"])
def crop():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        if "cropped_image" not in request.files:
            flash("No image uploaded!", "danger")
            return redirect(url_for("crop"))

        file = request.files["cropped_image"]
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(input_path)

        # Save the cropped image
        cropped_path = os.path.join(app.config["CONVERTED_FOLDER"], filename)
        with Image.open(input_path) as img:
            img.save(cropped_path)

        return send_file(cropped_path, as_attachment=True)

    return render_template("crop.html")


if __name__ == "__main__":
    app.run(debug=True)
