from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
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
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from datetime import timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import io
from Crypto.Cipher import PKCS1_OAEP

app = Flask(__name__)
app.secret_key = "a6d4c5f91b7a3c81d2e3f4c5b6a7d8f9d0e1c2b3a4f5c6d7e8f9a0b1c2d3e4f5"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# MySQL configurations
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "crypto_wallets"
app.config["MYSQL_CONNECT_TIMEOUT"] = 30
app.config['MYSQL_MAX_ALLOWED_PACKET'] = 16 * 1024 * 1024  # 16MB

mysql = MySQL(app)

def create_tables():
    """Create necessary database tables if they don't exist."""
    try:
        cursor = mysql.connection.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                age INT NOT NULL,
                phone VARCHAR(10) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                gender VARCHAR(10) NOT NULL,
                monthly_income DECIMAL(10, 2) NOT NULL,
                profile_photo LONGBLOB,
                password VARCHAR(255) NOT NULL,
                public_key TEXT NOT NULL,
                private_key TEXT NOT NULL,
                qr_code LONGBLOB
            )
        """)

        # Crypto balances table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crypto_balances (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                email VARCHAR(255) NOT NULL,
                btc_balance DECIMAL(20, 8) DEFAULT 0,
                eth_balance DECIMAL(20, 8) DEFAULT 0,
                usdt_balance DECIMAL(20, 2) DEFAULT 0,
                btc_cvv VARCHAR(3),
                eth_cvv VARCHAR(3),
                usdt_cvv VARCHAR(3),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # Chat tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user1_id INT NOT NULL,
                user2_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users(id),
                FOREIGN KEY (user2_id) REFERENCES users(id),
                UNIQUE KEY unique_conversation (user1_id, user2_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                conversation_id INT NOT NULL,
                sender_id INT NOT NULL,
                message TEXT NOT NULL,
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id),
                FOREIGN KEY (sender_id) REFERENCES users(id)
        """)

        mysql.connection.commit()
        cursor.close()
    except Exception as e:
        print(f"Error creating tables: {e}")
        if mysql.connection:
            mysql.connection.rollback()
        raise

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.before_request
def check_session():
    if request.endpoint not in ['login', 'signup', 'static', 'logout', 'main', 'index']:
        if 'user_id' not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))

@app.route('/')
def index():
    return render_template("main1.html")

@app.route('/main', methods=["GET"])
def main():
    return render_template("main1.html")

@app.route('/signup', methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        cursor = None
        try:
            # Get form data
            name = request.form["name"]
            age = int(request.form["age"])
            phone = request.form["phone"]
            email = request.form["email"]
            gender = request.form["gender"]
            monthly_income = float(request.form["monthly_income"])
            password = request.form["password"]
            profile_photo = request.files["profile_photo"]

            cursor = mysql.connection.cursor()

            # Check if user already exists
            cursor.execute("SELECT * FROM users WHERE name = %s OR email = %s OR phone = %s", (name, email, phone))
            existing_user = cursor.fetchone()

            if existing_user:
                if existing_user[1] == name:
                    flash("Username already exists.", "danger")
                elif existing_user[4] == email:
                    flash("Email already registered.", "danger")
                elif existing_user[3] == phone:
                    flash("Phone number already registered.", "danger")
                return render_template("signup.html")

            # Process profile photo
            img = Image.open(profile_photo)
            img = img.convert("RGB")
            img.thumbnail((500, 500))
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=70)
            profile_photo_data = img_byte_arr.getvalue()

            # Generate RSA keys
            key = RSA.generate(2048)
            private_key = key.export_key().decode()
            public_key = key.publickey().export_key().decode()

            # Generate QR code
            qr_img = qrcode.make(public_key)
            qr_byte_arr = io.BytesIO()
            qr_img.save(qr_byte_arr, format='JPEG', quality=70)
            qr_code_data = qr_byte_arr.getvalue()

            # Hash password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()

            # Insert user data
            cursor.execute("""
                INSERT INTO users (name, age, phone, email, gender, monthly_income,
                profile_photo, password, public_key, private_key, qr_code)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (name, age, phone, email, gender, monthly_income, profile_photo_data,
                  hashed_password, public_key, private_key, qr_code_data))

            user_id = cursor.lastrowid

            # Generate random CVVs and initial balances
            cursor.execute("""
                INSERT INTO crypto_balances (user_id, email, btc_balance, eth_balance, usdt_balance, btc_cvv, eth_cvv, usdt_cvv)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, email,
                  round(random.uniform(0.01, 10.0), 8),
                  round(random.uniform(0.01, 50.0), 8),
                  round(random.uniform(1.0, 5000.0), 2),
                  str(random.randint(100, 999)),
                  str(random.randint(100, 999)),
                  str(random.randint(100, 999))))

            mysql.connection.commit()
            flash("Signup successful. Please login.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            if mysql.connection:
                mysql.connection.rollback()
            flash(f"Error during signup: {str(e)}", "danger")
            print(f"Signup error: {e}")
            return render_template("signup.html")
        finally:
            if cursor:
                cursor.close()

    return render_template("signup.html")

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = None
        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT id, name, password FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user and user[2] == hashlib.sha256(password.encode()).hexdigest():
                session["user_id"] = user[0]
                session["name"] = user[1]
                flash("Login successful!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash("Invalid email or password.", "danger")
        except Exception as e:
            flash("Error during login. Please try again.", "danger")
            print(f"Login error: {e}")
        finally:
            if cursor:
                cursor.close()

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("main"))

@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cursor = mysql.connection.cursor()

    try:
        # Get user data
        cursor.execute("""
            SELECT id, name, age, phone, email, gender, monthly_income, profile_photo, qr_code
            FROM users WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()

        if not user:
            flash("User not found.", "danger")
            return redirect(url_for("login"))

        # Get crypto balances
        cursor.execute("""
            SELECT btc_balance, eth_balance, usdt_balance, btc_cvv, eth_cvv, usdt_cvv 
            FROM crypto_balances WHERE user_id = %s
        """, (user_id,))
        balances = cursor.fetchone()

        if not balances:
            flash("Balance information not found.", "danger")
            return redirect(url_for("login"))

        # Prepare data for template
        profile_photo_base64 = base64.b64encode(user[7]).decode('utf-8') if user[7] else None
        qr_code_base64 = base64.b64encode(user[8]).decode('utf-8') if user[8] else None

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
                            btc_balance=balances[0],
                            eth_balance=balances[1],
                            usdt_balance=balances[2],
                            btc_cvv=balances[3],
                            eth_cvv=balances[4],
                            usdt_cvv=balances[5])

    except Exception as e:
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return redirect(url_for("login"))
    finally:
        cursor.close()

@app.route('/exchange', methods=["GET", "POST"])
def exchange():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            recipient_email = request.form["recipient_email"]
            crypto_type = request.form["crypto_type"]
            amount = Decimal(request.form["amount"])

            # Basic validation
            if not recipient_email or not crypto_type or not amount:
                flash("All fields are required.", "danger")
                return redirect(url_for("exchange"))

            # Check internet connection
            try:
                socket.create_connection(("www.google.com", 80), timeout=5)
            except OSError:
                flash("No internet connection. Please check your connection.", "danger")
                return redirect(url_for("exchange"))

            cursor = mysql.connection.cursor()
            user_id = session["user_id"]

            # Get sender balances
            cursor.execute("""
                SELECT email, btc_balance, eth_balance, usdt_balance 
                FROM crypto_balances WHERE user_id = %s
            """, (user_id,))
            sender_balance = cursor.fetchone()

            if not sender_balance:
                flash("Sender balance not found.", "danger")
                return redirect(url_for("exchange"))

            sender_email, btc_balance, eth_balance, usdt_balance = sender_balance

            # Check if sending to self
            if recipient_email == sender_email:
                flash("Cannot send to yourself.", "danger")
                return redirect(url_for("exchange"))

            # Get recipient balances
            cursor.execute("""
                SELECT id, btc_balance, eth_balance, usdt_balance 
                FROM crypto_balances WHERE email = %s
            """, (recipient_email,))
            recipient_balance = cursor.fetchone()

            if not recipient_balance:
                flash("Recipient not found.", "danger")
                return redirect(url_for("exchange"))

            recipient_id, recipient_btc, recipient_eth, recipient_usdt = recipient_balance

            # Process transaction based on crypto type
            if crypto_type == "BTC":
                if btc_balance < amount:
                    flash("Insufficient BTC balance.", "danger")
                    return redirect(url_for("exchange"))
                new_sender_balance = btc_balance - amount
                new_recipient_balance = recipient_btc + amount
                cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE user_id = %s", 
                             (new_sender_balance, user_id))
                cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE id = %s", 
                             (new_recipient_balance, recipient_id))
            elif crypto_type == "ETH":
                if eth_balance < amount:
                    flash("Insufficient ETH balance.", "danger")
                    return redirect(url_for("exchange"))
                new_sender_balance = eth_balance - amount
                new_recipient_balance = recipient_eth + amount
                cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE user_id = %s", 
                             (new_sender_balance, user_id))
                cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE id = %s", 
                             (new_recipient_balance, recipient_id))
            elif crypto_type == "USDT":
                if usdt_balance < amount:
                    flash("Insufficient USDT balance.", "danger")
                    return redirect(url_for("exchange"))
                new_sender_balance = usdt_balance - amount
                new_recipient_balance = recipient_usdt + amount
                cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE user_id = %s", 
                             (new_sender_balance, user_id))
                cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE id = %s", 
                             (new_recipient_balance, recipient_id))
            else:
                flash("Invalid cryptocurrency type.", "danger")
                return redirect(url_for("exchange"))

            # Create transaction tables if they don't exist
            sender_table = f"transaction_{sender_email.replace('@', '').replace('.', '')}"
            recipient_table = f"transaction_{recipient_email.replace('@', '').replace('.', '')}"

            for table in [sender_table, recipient_table]:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        recipient_email VARCHAR(255),
                        sender_email VARCHAR(255),
                        crypto_type VARCHAR(50),
                        amount DECIMAL(20, 8),
                        transaction_time DATETIME,
                        status VARCHAR(50)
                    )
                """)

            # Record transaction for sender
            cursor.execute(f"""
                INSERT INTO {sender_table} 
                (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

            # Record transaction for recipient
            cursor.execute(f"""
                INSERT INTO {recipient_table} 
                (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

            mysql.connection.commit()
            flash(f"{amount} {crypto_type} sent successfully!", "success")
            return redirect(url_for("dashboard"))

        except ValueError:
            flash("Invalid amount entered.", "danger")
            return redirect(url_for("exchange"))
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Transaction failed: {str(e)}", "danger")
            print(f"Exchange error: {e}")
            return redirect(url_for("exchange"))
        finally:
            cursor.close()

    return render_template('exchange.html')

@app.route('/transactions')
def transactions():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    try:
        # Get user email
        cursor.execute("SELECT email FROM crypto_balances WHERE user_id = %s", (session["user_id"],))
        result = cursor.fetchone()
        
        if not result:
            flash("User not found.", "danger")
            return redirect(url_for("dashboard"))

        user_email = result[0]
        transaction_table = f"transaction_{user_email.replace('@', '').replace('.', '')}"

        # Check if transaction table exists
        cursor.execute(f"SHOW TABLES LIKE '{transaction_table}'")
        if not cursor.fetchone():
            flash("No transactions found.", "info")
            return render_template('transaction.html', transactions=[])

        # Get transactions
        cursor.execute(f"""
            SELECT id, recipient_email, sender_email, crypto_type, amount, transaction_time, status 
            FROM {transaction_table} 
            ORDER BY transaction_time DESC
        """)
        transactions = cursor.fetchall()

        # Format transactions for display
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

        return render_template('transaction.html', transactions=transaction_list)

    except Exception as e:
        flash(f"Error loading transactions: {str(e)}", "danger")
        return redirect(url_for("dashboard"))
    finally:
        cursor.close()

@app.route('/analytics')
def analytics():
    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    cursor = mysql.connection.cursor()
    try:
        # Get user email
        cursor.execute("SELECT email FROM crypto_balances WHERE user_id = %s", (session["user_id"],))
        result = cursor.fetchone()
        
        if not result:
            flash("User not found.", "danger")
            return redirect(url_for("dashboard"))

        user_email = result[0]
        transaction_table = f"transaction_{user_email.replace('@', '').replace('.', '')}"

        # Check if transaction table exists
        cursor.execute(f"SHOW TABLES LIKE '{transaction_table}'")
        if not cursor.fetchone():
            flash("No transactions found.", "info")
            return render_template('analytics.html', bar_chart=None, pie_chart=None)

        # Get outgoing transactions
        cursor.execute(f"""
            SELECT recipient_email, amount 
            FROM {transaction_table} 
            WHERE sender_email = %s
        """, (user_email,))
        transactions = cursor.fetchall()

        if not transactions:
            flash("No outgoing transactions found.", "info")
            return render_template('analytics.html', bar_chart=None, pie_chart=None)

        # Calculate recipient amounts and percentages
        recipient_amounts = {}
        for recipient, amount in transactions:
            if recipient in recipient_amounts:
                recipient_amounts[recipient] += float(amount)
            else:
                recipient_amounts[recipient] = float(amount)

        total_amount = sum(recipient_amounts.values())
        if total_amount == 0:
            flash("No transaction amounts to analyze.", "info")
            return render_template('analytics.html', bar_chart=None, pie_chart=None)

        recipient_percentages = {k: (v / total_amount) * 100 for k, v in recipient_amounts.items()}

        # Generate bar chart
        plt.figure(figsize=(10, 5))
        plt.bar(recipient_percentages.keys(), recipient_percentages.values(), color='skyblue')
        plt.xlabel('Recipients')
        plt.ylabel('Percentage of Total Amount Sent')
        plt.title('Percentage of Total Amount Sent to Each Recipient')
        plt.xticks(rotation=45)
        plt.tight_layout()

        bar_chart = BytesIO()
        plt.savefig(bar_chart, format='png')
        bar_chart.seek(0)
        bar_chart_url = base64.b64encode(bar_chart.getvalue()).decode('utf-8')
        plt.close()

        # Generate pie chart
        plt.figure(figsize=(8, 8))
        plt.pie(
            recipient_percentages.values(),
            labels=recipient_percentages.keys(),
            autopct='%1.1f%%',
            startangle=140,
            colors=plt.cm.Paired.colors
        )
        plt.title('Distribution of Total Amount Sent to Recipients')

        pie_chart = BytesIO()
        plt.savefig(pie_chart, format='png')
        pie_chart.seek(0)
        pie_chart_url = base64.b64encode(pie_chart.getvalue()).decode('utf-8')
        plt.close()

        return render_template('analytics.html', bar_chart=bar_chart_url, pie_chart=pie_chart_url)

    except Exception as e:
        flash(f"Error generating analytics: {str(e)}", "danger")
        return redirect(url_for("dashboard"))
    finally:
        cursor.close()

@app.route('/scan_qr')
def scan_qr():
    return render_template("QR.html")

@app.route('/upload_qr', methods=["POST"])
def upload_qr():
    if "user_id" not in session:
        return jsonify({"error": "Please login first."}), 401

    if 'qr_image' not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files['qr_image']
    if file.filename == '':
        return jsonify({"error": "No selected file."}), 400

    try:
        # Read and decode QR code
        file_data = file.read()
        image = cv2.imdecode(np.frombuffer(file_data, np.uint8), cv2.IMREAD_COLOR)
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        decoded_objects = decode(gray_image)
        
        if not decoded_objects:
            return jsonify({"error": "No QR code detected."}), 400

        qr_data = decoded_objects[0].data.decode('utf-8')

        # Get user data from QR code (public key)
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT name, email, profile_photo FROM users WHERE public_key = %s", (qr_data,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "User not found."}), 404

        username, email, profile_photo = user
        profile_photo_base64 = base64.b64encode(profile_photo).decode('utf-8') if profile_photo else None

        return jsonify({
            "username": username,
            "email": email,
            "image_url": f"data:image/jpeg;base64,{profile_photo_base64}" if profile_photo_base64 else None
        })

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        cursor.close()

@app.route('/send_crypto', methods=['POST'])
def send_crypto():
    if "user_id" not in session:
        return jsonify({"error": "Please login first."}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data."}), 400

    required_fields = ['email', 'crypto_type', 'amount']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "All fields are required."}), 400

    try:
        recipient_email = data['email']
        crypto_type = data['crypto_type'].upper()
        amount = Decimal(data['amount'])
    except (ValueError, KeyError) as e:
        return jsonify({"error": f"Invalid data: {str(e)}"}), 400

    cursor = mysql.connection.cursor()
    try:
        user_id = session["user_id"]

        # Get sender balances
        cursor.execute("""
            SELECT email, btc_balance, eth_balance, usdt_balance 
            FROM crypto_balances WHERE user_id = %s
        """, (user_id,))
        sender_balance = cursor.fetchone()

        if not sender_balance:
            return jsonify({"error": "Sender balance not found."}), 400

        sender_email, btc_balance, eth_balance, usdt_balance = sender_balance

        # Check if sending to self
        if recipient_email == sender_email:
            return jsonify({"error": "Cannot send to yourself."}), 400

        # Get recipient balances
        cursor.execute("""
            SELECT id, btc_balance, eth_balance, usdt_balance 
            FROM crypto_balances WHERE email = %s
        """, (recipient_email,))
        recipient_balance = cursor.fetchone()

        if not recipient_balance:
            return jsonify({"error": "Recipient not found."}), 400

        recipient_id, recipient_btc, recipient_eth, recipient_usdt = recipient_balance

        # Process transaction based on crypto type
        if crypto_type == "BTC":
            if btc_balance < amount:
                return jsonify({"error": "Insufficient BTC balance."}), 400
            new_sender_balance = btc_balance - amount
            new_recipient_balance = recipient_btc + amount
            cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE user_id = %s", 
                         (new_sender_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET btc_balance = %s WHERE id = %s", 
                         (new_recipient_balance, recipient_id))
        elif crypto_type == "ETH":
            if eth_balance < amount:
                return jsonify({"error": "Insufficient ETH balance."}), 400
            new_sender_balance = eth_balance - amount
            new_recipient_balance = recipient_eth + amount
            cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE user_id = %s", 
                         (new_sender_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET eth_balance = %s WHERE id = %s", 
                         (new_recipient_balance, recipient_id))
        elif crypto_type == "USDT":
            if usdt_balance < amount:
                return jsonify({"error": "Insufficient USDT balance."}), 400
            new_sender_balance = usdt_balance - amount
            new_recipient_balance = recipient_usdt + amount
            cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE user_id = %s", 
                         (new_sender_balance, user_id))
            cursor.execute("UPDATE crypto_balances SET usdt_balance = %s WHERE id = %s", 
                         (new_recipient_balance, recipient_id))
        else:
            return jsonify({"error": "Invalid cryptocurrency type."}), 400

        # Create transaction tables if they don't exist
        sender_table = f"transaction_{sender_email.replace('@', '').replace('.', '')}"
        recipient_table = f"transaction_{recipient_email.replace('@', '').replace('.', '')}"

        for table in [sender_table, recipient_table]:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    recipient_email VARCHAR(255),
                    sender_email VARCHAR(255),
                    crypto_type VARCHAR(50),
                    amount DECIMAL(20, 8),
                    transaction_time DATETIME,
                    status VARCHAR(50)
                )
            """)

        # Record transactions
        cursor.execute(f"""
            INSERT INTO {sender_table} 
            (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

        cursor.execute(f"""
            INSERT INTO {recipient_table} 
            (recipient_email, sender_email, crypto_type, amount, transaction_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (recipient_email, sender_email, crypto_type, amount, datetime.datetime.now(), "Completed"))

        mysql.connection.commit()
        return jsonify({"message": f"{amount} {crypto_type} sent successfully to {recipient_email}!"}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": f"Transaction failed: {str(e)}"}), 500
    finally:
        cursor.close()


# @app.route('/chat')
# def chat_home():
#     if "user_id" not in session:
#         flash("Please login first.", "danger")
#         return redirect(url_for("login"))

#     user_id = session["user_id"]
#     cursor = mysql.connection.cursor()

#     try:
#         # Get all conversations for the user
#         cursor.execute("""
#             SELECT c.id, 
#                    CASE 
#                        WHEN c.user1_id = %s THEN u2.id
#                        ELSE u1.id
#                    END as other_user_id,
#                    CASE 
#                        WHEN c.user1_id = %s THEN u2.name
#                        ELSE u1.name
#                    END as other_user_name,
#                    CASE 
#                        WHEN c.user1_id = %s THEN u2.email
#                        ELSE u1.email
#                    END as other_user_email,
#                    (SELECT COUNT(*) FROM chat_messages 
#                     WHERE conversation_id = c.id 
#                     AND sender_id != %s 
#                     AND is_read = FALSE) as unread_count,
#                    (SELECT message FROM chat_messages 
#                     WHERE conversation_id = c.id 
#                     ORDER BY sent_at DESC LIMIT 1) as last_message,
#                    (SELECT sent_at FROM chat_messages 
#                     WHERE conversation_id = c.id 
#                     ORDER BY sent_at DESC LIMIT 1) as last_message_time
#             FROM chat_conversations c
#             JOIN users u1 ON c.user1_id = u1.id
#             JOIN users u2 ON c.user2_id = u2.id
#             WHERE c.user1_id = %s OR c.user2_id = %s
#             ORDER BY last_message_time DESC
#         """, (user_id, user_id, user_id, user_id, user_id, user_id))
        
#         conversations = cursor.fetchall()
        
#         # Format conversations
#         conversation_list = []
#         for conv in conversations:
#             conversation_list.append({
#                 "id": conv[0],
#                 "other_user_id": conv[1],
#                 "other_user_name": conv[2],
#                 "other_user_email": conv[3],
#                 "unread_count": conv[4],
#                 "last_message": conv[5],
#                 "last_message_time": conv[6].strftime("%Y-%m-%d %H:%M:%S") if conv[6] else None
#             })
        
#         return render_template('chat_home.html', conversations=conversation_list)
    
#     except Exception as e:
#         flash(f"Error loading chat: {str(e)}", "danger")
#         return redirect(url_for("dashboard"))
#     finally:
#         cursor.close()

# @app.route('/chat/search', methods=['GET'])
# def chat_search():
#     if "user_id" not in session:
#         return jsonify({"error": "Please login first."}), 401

#     search_term = request.args.get('q', '')
#     if not search_term:
#         return jsonify({"error": "Search term required."}), 400

#     cursor = mysql.connection.cursor()
#     try:
#         user_id = session["user_id"]
        
#         # Search users by name or email (excluding current user)
#         cursor.execute("""
#             SELECT id, name, email, profile_photo 
#             FROM users 
#             WHERE (name LIKE %s OR email LIKE %s) 
#             AND id != %s
#             LIMIT 10
#         """, (f"%{search_term}%", f"%{search_term}%", user_id))
        
#         users = cursor.fetchall()
        
#         user_list = []
#         for user in users:
#             profile_photo_base64 = base64.b64encode(user[3]).decode('utf-8') if user[3] else None
#             user_list.append({
#                 "id": user[0],
#                 "name": user[1],
#                 "email": user[2],
#                 "profile_photo": f"data:image/jpeg;base64,{profile_photo_base64}" if profile_photo_base64 else None
#             })
        
#         return jsonify({"users": user_list})
    
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
#     finally:
#         cursor.close()

# @app.route('/chat/start', methods=['POST'])
# def start_chat():
#     if "user_id" not in session:
#         return jsonify({"error": "Please login first."}), 401

#     data = request.get_json()
#     if not data or 'other_user_id' not in data:
#         return jsonify({"error": "Other user ID required."}), 400

#     cursor = mysql.connection.cursor()
#     try:
#         user_id = session["user_id"]
#         other_user_id = data['other_user_id']
        
#         # Check if conversation already exists
#         cursor.execute("""
#             SELECT id FROM chat_conversations 
#             WHERE (user1_id = %s AND user2_id = %s) 
#             OR (user1_id = %s AND user2_id = %s)
#         """, (user_id, other_user_id, other_user_id, user_id))
        
#         conversation = cursor.fetchone()
        
#         if conversation:
#             conversation_id = conversation[0]
#         else:
#             # Create new conversation (always store with lower ID first to avoid duplicates)
#             user1_id, user2_id = sorted([user_id, other_user_id])
#             cursor.execute("""
#                 INSERT INTO chat_conversations (user1_id, user2_id)
#                 VALUES (%s, %s)
#             """, (user1_id, user2_id))
#             conversation_id = cursor.lastrowid
#             mysql.connection.commit()
        
#         return jsonify({"conversation_id": conversation_id})
    
#     except Exception as e:
#         mysql.connection.rollback()
#         return jsonify({"error": str(e)}), 500
#     finally:
#         cursor.close()

# @app.route('/chat/<int:conversation_id>')
# def chat_conversation(conversation_id):
#     if "user_id" not in session:
#         flash("Please login first.", "danger")
#         return redirect(url_for("login"))

#     cursor = mysql.connection.cursor()
#     try:
#         user_id = session["user_id"]
        
#         # Verify user is part of this conversation
#         cursor.execute("""
#             SELECT id FROM chat_conversations 
#             WHERE id = %s AND (user1_id = %s OR user2_id = %s)
#         """, (conversation_id, user_id, user_id))
        
#         if not cursor.fetchone():
#             flash("You don't have access to this conversation.", "danger")
#             return redirect(url_for("chat_home"))
        
#         # Get conversation details
#         cursor.execute("""
#             SELECT 
#                 CASE 
#                     WHEN user1_id = %s THEN user2_id
#                     ELSE user1_id
#                 END as other_user_id,
#                 CASE 
#                     WHEN user1_id = %s THEN (SELECT name FROM users WHERE id = user2_id)
#                     ELSE (SELECT name FROM users WHERE id = user1_id)
#                 END as other_user_name,
#                 CASE 
#                     WHEN user1_id = %s THEN (SELECT email FROM users WHERE id = user2_id)
#                     ELSE (SELECT email FROM users WHERE id = user1_id)
#                 END as other_user_email,
#                 CASE 
#                     WHEN user1_id = %s THEN (SELECT profile_photo FROM users WHERE id = user2_id)
#                     ELSE (SELECT profile_photo FROM users WHERE id = user1_id)
#                 END as other_user_photo
#             FROM chat_conversations 
#             WHERE id = %s
#         """, (user_id, user_id, user_id, user_id, conversation_id))
        
#         conv_details = cursor.fetchone()
        
#         if not conv_details:
#             flash("Conversation not found.", "danger")
#             return redirect(url_for("chat_home"))
        
#         # Get messages
#         cursor.execute("""
#             SELECT m.id, m.sender_id, u.name, u.profile_photo, m.message, m.sent_at, m.is_read
#             FROM chat_messages m
#             JOIN users u ON m.sender_id = u.id
#             WHERE m.conversation_id = %s
#             ORDER BY m.sent_at ASC
#         """, (conversation_id,))
        
#         messages = cursor.fetchall()
        
#         # Mark messages as read
#         cursor.execute("""
#             UPDATE chat_messages 
#             SET is_read = TRUE 
#             WHERE conversation_id = %s AND sender_id != %s AND is_read = FALSE
#         """, (conversation_id, user_id))
#         mysql.connection.commit()
        
#         # Format messages
#         message_list = []
#         for msg in messages:
#             profile_photo_base64 = base64.b64encode(msg[3]).decode('utf-8') if msg[3] else None
#             message_list.append({
#                 "id": msg[0],
#                 "sender_id": msg[1],
#                 "sender_name": msg[2],
#                 "sender_photo": f"data:image/jpeg;base64,{profile_photo_base64}" if profile_photo_base64 else None,
#                 "message": msg[4],
#                 "sent_at": msg[5].strftime("%Y-%m-%d %H:%M:%S"),
#                 "is_read": msg[6],
#                 "is_me": msg[1] == user_id
#             })
        
#         other_user = {
#             "id": conv_details[0],
#             "name": conv_details[1],
#             "email": conv_details[2],
#             "photo": f"data:image/jpeg;base64,{base64.b64encode(conv_details[3]).decode('utf-8')}" if conv_details[3] else None
#         }
        
#         return render_template('chat_conversation.html', 
#                              messages=message_list, 
#                              conversation_id=conversation_id,
#                              other_user=other_user)
    
#     except Exception as e:
#         flash(f"Error loading conversation: {str(e)}", "danger")
#         return redirect(url_for("chat_home"))
#     finally:
#         cursor.close()

# @app.route('/chat/send', methods=['POST'])
# def send_message():
#     if "user_id" not in session:
#         return jsonify({"error": "Please login first."}), 401

#     data = request.get_json()
#     if not data or 'conversation_id' not in data or 'message' not in data:
#         return jsonify({"error": "Conversation ID and message required."}), 400

#     cursor = mysql.connection.cursor()
#     try:
#         user_id = session["user_id"]
#         conversation_id = data['conversation_id']
#         message = data['message'].strip()
        
#         if not message:
#             return jsonify({"error": "Message cannot be empty."}), 400
        
#         # Verify user is part of this conversation
#         cursor.execute("""
#             SELECT id FROM chat_conversations 
#             WHERE id = %s AND (user1_id = %s OR user2_id = %s)
#         """, (conversation_id, user_id, user_id))
        
#         if not cursor.fetchone():
#             return jsonify({"error": "You don't have access to this conversation."}), 403
        
#         # Insert message
#         cursor.execute("""
#             INSERT INTO chat_messages (conversation_id, sender_id, message)
#             VALUES (%s, %s, %s)
#         """, (conversation_id, user_id, message))
        
#         mysql.connection.commit()
        
#         return jsonify({"success": True})
    
#     except Exception as e:
#         mysql.connection.rollback()
#         return jsonify({"error": str(e)}), 500
#     finally:
#         cursor.close()

# @app.route('/chat/unread_count')
# def unread_count():
#     if "user_id" not in session:
#         return jsonify({"error": "Please login first."}), 401

#     cursor = mysql.connection.cursor()
#     try:
#         user_id = session["user_id"]
        
#         cursor.execute("""
#             SELECT COUNT(*) 
#             FROM chat_messages m
#             JOIN chat_conversations c ON m.conversation_id = c.id
#             WHERE (c.user1_id = %s OR c.user2_id = %s)
#             AND m.sender_id != %s
#             AND m.is_read = FALSE
#         """, (user_id, user_id, user_id))
        
#         count = cursor.fetchone()[0]
        
#         return jsonify({"unread_count": count})
    
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500
#     finally:
#         cursor.close()



if __name__ == "__main__":
    with app.app_context():
        try:
            create_tables()
        except Exception as e:
            print(f"Error during table creation: {e}")
            print("Continuing with existing tables...")

    app.run(host='0.0.0.0', port=5000, debug=True)