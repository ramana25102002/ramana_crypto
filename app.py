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
                user_folder = os.path.join("static/uploads", email)
                os.makedirs(user_folder, exist_ok=True)

                profile_photo_filename = os.path.splitext(profile_photo.filename)[0] + ".jpg"
                profile_photo_path = os.path.join(user_folder, profile_photo_filename)
                img = Image.open(profile_photo)
                img = img.convert("RGB")
                img.save(profile_photo_path, "JPEG")
                profile_photo_data = open(profile_photo_path, "rb").read()

                hashed_password = hashlib.sha256(password.encode()).hexdigest()

                key = RSA.generate(2048)
                private_key = key.export_key().decode()
                public_key = key.publickey().export_key().decode()

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(public_key)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_code_filename = os.path.join(user_folder, f"{email}_qr_code.jpg")
                qr_img.save(qr_code_filename, "JPEG")
                qr_code_data = open(qr_code_filename, "rb").read()

                cursor.execute("""
                    INSERT INTO users (name, age, phone, email, gender, monthly_income, profile_photo, password, public_key, private_key, qr_code)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (name, age, phone, email, gender, monthly_income, profile_photo_data, hashed_password, public_key, private_key, qr_code_data))
                mysql.connection.commit()

                # Get the newly created user's ID
                user_id = cursor.lastrowid

                # Generate random balances and insert them into the crypto_balances table
                btc_balance = round(random.uniform(0.001, 10.0), 4)
                eth_balance = round(random.uniform(0.001, 50.0), 4)
                usdt_balance = round(random.uniform(1.0, 10000.0), 2)
                cursor.execute("""
                    INSERT INTO crypto_balances (user_id, email, btc_balance, eth_balance, usdt_balance)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, email, btc_balance, eth_balance, usdt_balance))
                mysql.connection.commit()

                # Create a table for the user's transactions
                transaction_table = f"transactions_{name.replace(' ', '_').lower()}"
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {transaction_table} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        recipient_email VARCHAR(255) NOT NULL,
                        sender_email VARCHAR(255) NOT NULL,
                        crypto_type VARCHAR(10) NOT NULL,
                        amount DECIMAL(10, 4) NOT NULL,
                        transaction_time DATETIME NOT NULL,
                        status VARCHAR(20) NOT NULL
                    );
                """)
                mysql.connection.commit()

                flash("Signup successful! You can log in now.", "success")
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
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))

from decimal import Decimal
@app.route('/exchange', methods=["GET", "POST"])
def exchange():
    if "user_id" in session:
        user_id = session["user_id"]
        cursor = mysql.connection.cursor()

        if request.method == "POST":
            # Get form data using .get() to avoid KeyError
            recipient_email = request.form.get("recipient_email")
            crypto_type = request.form.get("crypto_type")
            amount = request.form.get("amount")

            # Check if all required fields are filled
            if not recipient_email or not crypto_type or not amount:
                flash("All fields are required.", "danger")
                return redirect(url_for("exchange"))

            try:
                amount = Decimal(amount)  # Convert the amount to Decimal
            except ValueError:
                flash("Invalid amount entered.", "danger")
                return redirect(url_for("exchange"))

            # Fetch the sender's email and balances from the database
            cursor.execute("""
                SELECT email, btc_balance, eth_balance, usdt_balance FROM crypto_balances WHERE user_id = %s
            """, (user_id,))
            sender_balance = cursor.fetchone()

            if sender_balance:
                sender_email = sender_balance[0]  # Access the sender's email from the result

                # Check if sender tries to send to their own email
                if recipient_email == sender_email:
                    flash("You cannot send cryptocurrency to your own email.", "danger")
                    cursor.close()
                    return redirect(url_for("exchange"))

                # Fetch the recipient's crypto balance
                cursor.execute("""
                    SELECT id, btc_balance, eth_balance, usdt_balance FROM crypto_balances WHERE email = %s
                """, (recipient_email,))
                recipient_balance = cursor.fetchone()

                if recipient_balance:
                    # Perform balance checks and updates for each crypto type
                    if crypto_type == "BTC" and sender_balance[1] >= amount:
                        new_sender_btc_balance = sender_balance[1] - amount
                        new_recipient_btc_balance = recipient_balance[1] + amount
                        cursor.execute("""
                            UPDATE crypto_balances SET btc_balance = %s WHERE user_id = %s
                        """, (new_sender_btc_balance, user_id))
                        cursor.execute("""
                            UPDATE crypto_balances SET btc_balance = %s WHERE email = %s
                        """, (new_recipient_btc_balance, recipient_email))

                    elif crypto_type == "ETH" and sender_balance[2] >= amount:
                        new_sender_eth_balance = sender_balance[2] - amount
                        new_recipient_eth_balance = recipient_balance[2] + amount
                        cursor.execute("""
                            UPDATE crypto_balances SET eth_balance = %s WHERE user_id = %s
                        """, (new_sender_eth_balance, user_id))
                        cursor.execute("""
                            UPDATE crypto_balances SET eth_balance = %s WHERE email = %s
                        """, (new_recipient_eth_balance, recipient_email))

                    elif crypto_type == "USDT" and sender_balance[3] >= amount:
                        new_sender_usdt_balance = sender_balance[3] - amount
                        new_recipient_usdt_balance = recipient_balance[3] + amount
                        cursor.execute("""
                            UPDATE crypto_balances SET usdt_balance = %s WHERE user_id = %s
                        """, (new_sender_usdt_balance, user_id))
                        cursor.execute("""
                            UPDATE crypto_balances SET usdt_balance = %s WHERE email = %s
                        """, (new_recipient_usdt_balance, recipient_email))

                    else:
                        flash(f"Insufficient {crypto_type} balance.", "danger")
                        cursor.close()
                        return redirect(url_for("exchange"))

                    # Commit the balance updates
                    mysql.connection.commit()

                    # Create a user-specific transaction table based on the username
                    user_name = session.get("user_name", "default_user")  # Get user name from session (or default if missing)
                    table_name = f"transaction_{user_name}"  # Table name based on the user name

                    # Check if the table exists, and create it if it doesn't
                    cursor.execute(f"""
                        CREATE TABLE IF NOT EXISTS `{table_name}` (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            recipient_email VARCHAR(255),
                            sender_email VARCHAR(255),
                            crypto_type VARCHAR(50),
                            amount DECIMAL(20, 8),
                            transaction_time DATETIME,
                            status VARCHAR(50)
                        )
                    """)

                    # Log the transaction in the dynamically created table
                    cursor.execute(f"""
                        INSERT INTO `{table_name}` (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

                    # Commit the transaction log
                    mysql.connection.commit()

                    flash(f"{amount} {crypto_type} sent successfully!", "success")
                    cursor.close()
                    return redirect(url_for("dashboard"))
                else:
                    flash("Recipient not found.", "danger")
                    cursor.close()
                    return redirect(url_for("exchange"))
            else:
                flash("Sender balance not found.", "danger")
                cursor.close()
                return redirect(url_for("exchange"))
        else:
            return render_template('exchange.html')  # For GET request, render the exchange page

    else:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))




if __name__ == "__main__":
    with app.app_context():
        create_tables()
    app.run(debug=True)
