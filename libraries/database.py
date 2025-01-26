import MySQLdb
from flask_mysqldb import MySQL

# Function to connect to MySQL
def connect_to_mysql(host, user, passwd, db=None):
    return MySQLdb.connect(
        host=host,
        user=user,
        passwd=passwd,
        db=db  # Optional db parameter to specify the database
    )

# Function to create the database if it doesn't exist
def create_database():
    db = None
    try:
        db = connect_to_mysql("localhost", "root", "")  # Replace '' with your MySQL root password
        cursor = db.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS crypto_wallets")
        db.commit()
        print("Database 'crypto_wallets' created successfully!")
    except Exception as e:
        print(f"Error creating database: {e}")
    finally:
        if db:
            db.close()

# Function to initialize MySQL for Flask
def init_mysql(app):
    mysql = MySQL(app)
    return mysql

# Function to create the users table if it doesn't exist
def create_table(mysql):
    cursor = None
    try:
        cursor = mysql.connection.cursor()
        # Switch to the correct database
        cursor.execute("USE crypto_wallets")
        
        # Create the 'users' table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                age INT NOT NULL,
                phone VARCHAR(15) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                gender ENUM('Male', 'Female', 'Other') NOT NULL,
                monthly_income DECIMAL(10, 2) NOT NULL,
                profile_photo LONGBLOB,
                password VARCHAR(255) NOT NULL,
                public_key TEXT NOT NULL,
                private_key TEXT NOT NULL,
                qr_code LONGBLOB
            )
        """)
        mysql.connection.commit()
        print("Table 'users' created successfully!")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        if cursor:
            cursor.close()

