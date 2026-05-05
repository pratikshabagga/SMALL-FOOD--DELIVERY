from flask import Blueprint, request, render_template, redirect, url_for, session, flash,current_app
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from .. import mysql
import os
bp = Blueprint('auth_bp', __name__)
Folderupload = os.path.join('static', 'img')
fileExtensions = {'png', 'jpg', 'jpeg', 'gif','webp'}

def fileextension(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in fileExtensions

def validatinguser(table, username):
    cur = mysql.connection.cursor()
    query = f"SELECT id, password FROM {table} WHERE username = %s"
    cur.execute(query, (username,))
    result = cur.fetchone()
    cur.close()
    return result


def saveimage(image_file):
    """Helper to save image and return relative path."""
    if image_file and fileextension(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(current_app.root_path, Folderupload, filename)
        image_file.save(image_path)
        return f'img/{filename}'
    return None

# ------------------------------------------------------ USER ROUTES ------------------------------------------------------
# -------------------------------------------------------SIGNUP-------------------------------------------------------------

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Collect the data from the page
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        street_address = request.form['street_address']
        city = request.form['city']
        state = request.form['state']
        postal_code = request.form['postal_code']
        delivery_instructions = request.form.get('delivery_instructions', '')

        # Validation checking 
        if not all([fullname, username, email, password, phone, street_address, city, state, postal_code]):
            flash('All fields are required!', 'danger')
            return render_template('user/signup.html')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM customers WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone():
            flash('Username or Email already taken.', 'danger')
            cur.close()
            return render_template('user/signup.html')

        # Hashing  the pwd before saving it 
        hashed_password = generate_password_hash(password)

        # Insert user details into the form  with hashed pwd
        cur.execute("""
            INSERT INTO customers (fullname, username, email, password, phone, street_address, city, state, postal_code, delivery_instructions)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (fullname, username, email, hashed_password, phone, street_address, city, state, postal_code, delivery_instructions))
        
        mysql.connection.commit()
        cur.close()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth_bp.login_customer'))

    return render_template('user/signup.html')
# ---------------------------------------------------------------- LOGIN ---------------------------------------------------------------

@bp.route('/login/customer', methods=['GET', 'POST'])
def login_customer():
    # getting the details fromthye user
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password FROM customers WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        # if user and password is correct then

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['role'] = 'customer'
            flash('Customer login successful.', 'success')
            return redirect(url_for('main.index'))
# otherwise 
        flash('Invalid customer credentials.', 'danger')

    return render_template('user/login_customer.html')

# ------------------------------------------------------ ADMIN ROUTES ---------------------------------------------------
# ------------------------------------------------------ LOGIN ----------------------------------------------------------
@bp.route('/login/admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        # Clear flash messages before new login
        session.pop('_flashes', None)
        username = request.form['username']
        password = request.form['password']
# checking the user and validating it with function
        admin = validatinguser('admins', username)
        if admin and check_password_hash(admin[1], password):
            session['user_id'] = admin[0]
            session['role'] = 'admin'
            flash('Admin login successful.', 'success')
            return redirect(url_for('admin.admindashboard'))

        flash('Invalid admin credentials.', 'danger')

    return render_template('admin/admin_login.html')

# --------------------------------------------------- PARTNER ROUTES --------------------------------------------------------------------
# --------------------------------------------------- LOGIN -----------------------------------------------------------------------------
@bp.route('/login/partner', methods=['GET', 'POST'])
def login_partner():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password FROM restaurants WHERE email = %s",
                    (username,))
        partner = cur.fetchone()
        cur.close()

        if partner and check_password_hash(partner[1], password):
            session.clear()  # clearing old session to avoid unecessary flash messages
            session['restaurant_id'] = partner[0]
            session['role'] = 'partner'
            flash('Partner login successful.', 'success')
            return redirect(url_for('admin.products'))

        flash('Invalid partner credentials. Please try again.', 'danger')
        return render_template('partner/partner_login.html')

    return render_template('partner/partner_login.html')

# -------------------------------------------------------- REGISTERATION FOR PARTNER -----------------------------------------------------

#  partner registration route 
@bp.route('/partner-with-us', methods=['GET', 'POST'])
def register_restaurant():
    if request.method == 'POST':
        restaurant_name = request.form['restaurant_name']
        address = request.form['address']
        contact = request.form['contact']
        abn = request.form['abn']
        email = request.form['email']
        pwd = request.form['pwd']
        image_file = request.files.get('image_file')

        if not restaurant_name or not address or not contact or not abn:
            flash('All fields are required!', 'danger')
            return render_template('partnerregister.html')

        image_url = saveimage(image_file)
        if image_url:
            hashed_pwd = generate_password_hash(pwd)
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO restaurants (name, address, contact, image_url, abn,email,password)
                VALUES (%s, %s, %s, %s, %s,%s,%s)
            """, (restaurant_name, address, contact, image_url, abn, email, hashed_pwd))
            mysql.connection.commit()
            flash('Restaurant registered successfully!', 'success')
            return redirect(url_for('admin.my_restaurant'))
        else:
            flash('Invalid file format for restaurant image!', 'danger')
        
    return render_template('partner/partnerregister.html')

# --------------------------------------- LOGOUT -----------------------------------------------------------
@bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
