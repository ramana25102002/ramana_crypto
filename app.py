from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import os
import qrcode
from Crypto.PublicKey import RSA
from PIL import Image
import hashlib
import base64
import random
import datetime
from decimal import Decimal
import socket

# Flask app initialization
app = Flask(__name__)
app.secret_key = "a6d4c5f91b7a3c81d2e3f4c5b6a7d8f9d0e1c2b3a4f5c6d7e8f9a0b1c2d3e4f5"

# MySQL configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""  # Replace with your MySQL root password
app.config["MYSQL_DB"] = "crypto_wallets"

# Initialize MySQL
mysql = MySQL(app)

# Function to create necessary tables in the database
def create_tables():
    cursor = mysql.connection.cursor()
    # Create table for users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            age INT NOT NULL,
            phone VARCHAR(15) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            gender VARCHAR(10) NOT NULL,
            monthly_income DECIMAL(10, 2) NOT NULL,
            profile_photo LONGBLOB NOT NULL,
            password VARCHAR(255) NOT NULL,
            public_key TEXT NOT NULL,
            private_key TEXT NOT NULL,
            qr_code LONGBLOB NOT NULL
        );
    """)

    # Create table for crypto balances
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crypto_balances (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            email VARCHAR(255) NOT NULL,
            btc_balance DECIMAL(10, 4) NOT NULL,
            eth_balance DECIMAL(10, 4) NOT NULL,
            usdt_balance DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    mysql.connection.commit()
    cursor.close()

@app.route('/')
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("main1.html")

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        try:
            # Collect user details from the form
            name = request.form["name"]
            age = int(request.form["age"])
            phone = request.form["phone"]
            email = request.form["email"]
            gender = request.form["gender"]
            monthly_income = float(request.form["monthly_income"])
            password = request.form["password"]
            profile_photo = request.files["profile_photo"]

            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered. Use another email.", "danger")
            else:
                # Create a folder for the user
                user_folder = os.path.join("static/uploads", email)
                os.makedirs(user_folder, exist_ok=True)

                # Save profile photo
                profile_photo_filename = os.path.splitext(profile_photo.filename)[0] + ".jpg"
                profile_photo_path = os.path.join(user_folder, profile_photo_filename)
                img = Image.open(profile_photo)
                img = img.convert("RGB")
                img.save(profile_photo_path, "JPEG")
                profile_photo_data = open(profile_photo_path, "rb").read()

                # Hash the password
                hashed_password = hashlib.sha256(password.encode()).hexdigest()

                # Generate RSA keys
                key = RSA.generate(2048)
                private_key = key.export_key().decode()
                public_key = key.publickey().export_key().decode()

                # Generate QR code for the public key
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(public_key)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_code_filename = os.path.join(user_folder, f"{email}_qr_code.jpg")
                qr_img.save(qr_code_filename, "JPEG")
                qr_code_data = open(qr_code_filename, "rb").read()

                # Insert user details into the database
                cursor.execute("""
                    INSERT INTO users (name, age, phone, email, gender, monthly_income, profile_photo, password, public_key, private_key, qr_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (name, age, phone, email, gender, monthly_income, profile_photo_data, hashed_password, public_key, private_key, qr_code_data))
                mysql.connection.commit()

                # Get the newly created user's ID
                user_id = cursor.lastrowid

                # Generate random balances
                btc_balance = round(random.uniform(0.001, 10.0), 4)
                eth_balance = round(random.uniform(0.001, 50.0), 4)
                usdt_balance = round(random.uniform(1.0, 10000.0), 2)

                # Insert balances into the crypto_balances table
                cursor.execute("""
                    INSERT INTO crypto_balances (user_id, email, btc_balance, eth_balance, usdt_balance)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, email, btc_balance, eth_balance, usdt_balance))
                mysql.connection.commit()

                # Create a table for the user's transactions
                # transaction_table = f"transactions_{name.replace(' ', '_').lower()}"
                # cursor.execute(f"""
                #     CREATE TABLE IF NOT EXISTS {transaction_table} (
                #         id INT AUTO_INCREMENT PRIMARY KEY,
                #         recipient_email VARCHAR(255) NOT NULL,
                #         sender_email VARCHAR(255) NOT NULL,
                #         crypto_type VARCHAR(10) NOT NULL,
                #         amount DECIMAL(10, 4) NOT NULL,
                #         transaction_time DATETIME NOT NULL,
                #         status VARCHAR(20) NOT NULL
                #     );
                # """)
                # mysql.connection.commit()
                return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error during signup: {e}", "danger")
    return render_template("signup.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, name, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user and user[2] == hashlib.sha256(password.encode()).hexdigest():
            session["user_id"] = user[0]
            session["name"] = user[1]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    if "user_id" in session:
        user_id = session["user_id"]

        cursor = mysql.connection.cursor()

        # Fetch user data
        cursor.execute("""
            SELECT id, name, age, phone, email, gender, monthly_income, profile_photo, qr_code
            FROM users WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()

        # Fetch crypto balances
        cursor.execute("""
            SELECT email, btc_balance, eth_balance, usdt_balance FROM crypto_balances WHERE user_id = %s
        """, (user_id,))
        balances = cursor.fetchone()
        cursor.close()

        if user and balances:
            profile_photo_base64 = base64.b64encode(user[7]).decode('utf-8')
            qr_code_base64 = base64.b64encode(user[8]).decode('utf-8')
            return render_template("dashboard.html",
                                   id=user[0],
                                   name=user[1],
                                   age=user[2],
                                   phone=user[3],
                                   email=user[4],
                                   gender=user[5],
                                   monthly_income=user[6],
                                   profile_photo_base64=profile_photo_base64,
                                   qr_code_base64=qr_code_base64,
                                   btc_balance=balances[1],
                                   eth_balance=balances[2],
                                   usdt_balance=balances[3])

        flash("User data not found.", "danger")
        return redirect(url_for("login"))

    flash("Please login first.", "danger")
    return redirect(url_for("login"))


@app.route('/logout')
def logout():
    # Clear session data
    session.clear()
    flash("Logged out successfully.", "success")

    # Remove the session cookie explicitly
    response = redirect(url_for("login"))
    response.set_cookie('session', '', expires=0)  # Force the session cookie to expire
    return response


@app.route('/exchange', methods=["GET", "POST"])
def exchange():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor()

    if request.method == "POST":
        # Get form data
        recipient_email = request.form.get("recipient_email")
        crypto_type = request.form.get("crypto_type")
        amount = request.form.get("amount")

        # Validate required fields
        if not recipient_email or not crypto_type or not amount:
            flash("All fields are required.", "danger")
            return redirect(url_for("exchange"))

        try:
            amount = Decimal(amount)  # Convert amount to Decimal
        except ValueError:
            flash("Invalid amount entered.", "danger")
            return redirect(url_for("exchange"))

        # Check internet connection
        try:
            socket.create_connection(("www.google.com", 80))
        except OSError:
            flash("No internet connection. Please check your connection and try again.", "danger")
            return redirect(url_for("exchange"))

        # Fetch sender's balance and details
        cursor.execute("""
            SELECT email, btc_balance, eth_balance, usdt_balance FROM crypto_balances WHERE user_id = %s
        """, (user_id,))
        sender_balance = cursor.fetchone()

        if not sender_balance:
            flash("Sender balance not found.", "danger")
            cursor.close()
            return redirect(url_for("exchange"))

        sender_email, btc_balance, eth_balance, usdt_balance = sender_balance

        # Check if sender is sending to their own email
        if recipient_email == sender_email:
            flash("You cannot send cryptocurrency to your own email.", "danger")
            cursor.close()
            return redirect(url_for("exchange"))

        # Fetch recipient's balance
        cursor.execute("""
            SELECT id, btc_balance, eth_balance, usdt_balance FROM crypto_balances WHERE email = %s
        """, (recipient_email,))
        recipient_balance = cursor.fetchone()

        if not recipient_balance:
            flash("Recipient not found. Please check the email and try again.", "danger")
            cursor.close()
            return redirect(url_for("exchange"))

        recipient_id, recipient_btc_balance, recipient_eth_balance, recipient_usdt_balance = recipient_balance

        # Process the transaction
        if crypto_type == "BTC" and btc_balance >= amount:
            btc_balance -= amount
            recipient_btc_balance += amount
            cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE user_id = %s", (btc_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE email = %s", (recipient_btc_balance, recipient_email))
        elif crypto_type == "ETH" and eth_balance >= amount:
            eth_balance -= amount
            recipient_eth_balance += amount
            cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE user_id = %s", (eth_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE email = %s", (recipient_eth_balance, recipient_email))
        elif crypto_type == "USDT" and usdt_balance >= amount:
            usdt_balance -= amount
            recipient_usdt_balance += amount
            cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE user_id = %s", (usdt_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE email = %s", (recipient_usdt_balance, recipient_email))
        else:
            flash(f"Insufficient {crypto_type} balance.", "danger")
            cursor.close()
            return redirect(url_for("exchange"))

        # Commit updates
        mysql.connection.commit()

        # Log the transaction for both sender and recipient
        sender_table = f"transaction_{sender_email.replace('@', '').replace('.', '')}"
        recipient_table = f"transaction_{recipient_email.replace('@', '').replace('.', '')}"

        # Create sender's transaction table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sender_table} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                recipient_email VARCHAR(255),
                sender_email VARCHAR(255),
                crypto_type VARCHAR(50),
                amount DECIMAL(20, 8),
                transaction_time DATETIME,
                status VARCHAR(50)
            )
        """)

        # Create recipient's transaction table if it doesn't exist
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {recipient_table} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                recipient_email VARCHAR(255),
                sender_email VARCHAR(255),
                crypto_type VARCHAR(50),
                amount DECIMAL(20, 8),
                transaction_time DATETIME,
                status VARCHAR(50)
            )
        """)

        # Insert transaction into sender's table
        cursor.execute(f"""
            INSERT INTO {sender_table} (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

        # Insert transaction into recipient's table
        cursor.execute(f"""
            INSERT INTO {recipient_table} (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

        mysql.connection.commit()

        flash(f"{amount} {crypto_type} sent successfully!", "success")
        cursor.close()
        return redirect(url_for("dashboard"))

    # Render exchange page for GET request
    return render_template('exchange.html')

@app.route('/transactions', methods=['GET'])
def transactions():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor()

    # Get the user's email to locate the transaction table
    cursor.execute("SELECT email FROM crypto_balances WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()

    if not result:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    user_email = result[0]

    # Dynamically create the transaction table name
    transaction_table = f"transaction_{user_email.replace('@', '').replace('.', '')}"

    # Check if the transaction table exists in the database
    cursor.execute(f"SHOW TABLES LIKE '{transaction_table}'")
    table_exists = cursor.fetchone()

    if not table_exists:
        flash("No transactions found.", "info")
        return render_template('transaction.html', transactions=[])

    # Fetch transaction records
    cursor.execute(f"SELECT id, recipient_email, sender_email, crypto_type, amount, transaction_time, status FROM {transaction_table}")
    transactions = cursor.fetchall()

    # Convert data to a list of dictionaries for better handling in the template
    transaction_list = [
        {
            "id": t[0],
            "recipient_email": t[1],
            "sender_email": t[2],
            "crypto_type": t[3],
            "amount": float(t[4]),
            "transaction_time": t[5].strftime("%Y-%m-%d %H:%M:%S"),
            "status": t[6]
        }
        for t in transactions
    ]

    cursor.close()

    return render_template('transaction.html', transactions=transaction_list)


if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)