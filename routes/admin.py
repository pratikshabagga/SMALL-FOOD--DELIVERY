import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
from functools import wraps
from .. import mysql
from init_db import get_db_connection
bp = Blueprint('admin', __name__, url_prefix='/admin')

Folderupload = os.path.join('static', 'img')
fileExtensions = {'png', 'jpg', 'jpeg', 'gif','webp'}

def fileAllowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in fileExtensions

def imagefilesave(image_file):
    """saveing an  image and returning its relative path."""
    if image_file and fileAllowed(image_file.filename):
        filename = secure_filename(image_file.filename)
        image_path = os.path.join(current_app.root_path, Folderupload, filename)
        image_file.save(image_path)
        return f'img/{filename}'
    return None

#---------------------------------------  Role-based restriction for admin-------------------------------------------------
def adminonly(f):
    @wraps(f)
    def functionDecorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Access denied to admins only!', 'danger')
            return redirect(url_for('auth_bp.login_admin'))
        return f(*args, **kwargs)
    return functionDecorated


def admin_or_partner(f):
    """Allow either admin or partner (logged-in restaurant owner)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') not in ('admin', 'partner'):
            flash('Please log in to continue.', 'danger')
            return redirect(url_for('auth_bp.login_admin'))
        return f(*args, **kwargs)
    return wrapper


def product_owner_or_admin(cur, prod_id):
    """Return True if the current session may mutate this product."""
    role = session.get('role')
    if role == 'admin':
        return True
    if role == 'partner':
        cur.execute("SELECT restaurant_id FROM products WHERE id = %s", (prod_id,))
        row = cur.fetchone()
        return bool(row) and row[0] == session.get('restaurant_id')
    return False
# --------------------------------------------------ADMIN------------------------------------------
# ------------------------------------- dashboard for admin -----------------------------------------------
@bp.route('/dashboard')
@adminonly
def admindashboard():
    # creating  a Database  connection
    db = get_db_connection()
    cursor = db.cursor()

    # geting the number of restaurants from the database
    cursor.execute("SELECT COUNT(id) FROM restaurants")
    restcount = cursor.fetchone()[0]
    # getting  number of products from database
    cursor.execute("SELECT COUNT(id) FROM products")
    totalproduct= cursor.fetchone()[0]

    # Total sum of all product prices 
    cursor.execute("SELECT SUM(price) FROM products")
    totalsale = cursor.fetchone()[0] or 0  

    # Fetch latest 5 activities for display
    cursor.execute("""
        SELECT 
            DATE(date) AS date,
            activity,
            details
        FROM recent_activities
        ORDER BY date DESC
        LIMIT 5
    """)
    activity = cursor.fetchall()
    # Close the cursor 
    cursor.close()
    # closing the database
    db.close()

    return render_template(
        'admin/dashboard.html',
       restcount = restcount,
            totalproduct =    totalproduct,
        totalsale=totalsale,
        activity=activity
    )

# -----------restaurant stats-----------------------------------------
@bp.route('/restaurant-stats')
@adminonly
def restaurant_stats():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, image_url, address, contact FROM restaurants")
    restaurants = cursor.fetchall()
    cursor.close()
    return render_template('admin/restaurant_stats.html', restaurants=restaurants, total=len(restaurants))


# ----------------------------list of restaraunt for admin here admin can update the details of restauarant------------------------------------

@bp.route('/manage-restaurants', methods=['GET', 'POST'])
@adminonly
def manage_restaurants():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, address, contact, image_url, abn FROM restaurants")
    restaurants = cur.fetchall()

    editrestaurant = request.args.get('restaurant_id')

    if request.method == 'POST':
        restaurant_id = request.form['restaurant_id']
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']
        abn = request.form['abn']
        image = request.files.get('image_file')

        imagepath = imagefilesave(image)
        if not imagepath:
            cur.execute("SELECT image_url FROM restaurants WHERE id = %s", (restaurant_id,))
            imagepath = cur.fetchone()[0]

        cur.execute("""
            UPDATE restaurants
            SET name=%s, address=%s, contact=%s, image_url=%s, abn=%s
            WHERE id = %s
        """, (name, address, contact, imagepath, abn, restaurant_id))
        mysql.connection.commit()
        flash('Restaurant updated successfully!', 'success')
        return redirect(url_for('admin.manage_restaurants'))

    cur.close()
    role = session.get('role')
    return render_template('admin/manage_restaurants.html', restaurants=restaurants, editrestaurant=editrestaurant, role=role)

#------------------------------- delete the retauarnt route only for admin---------------------------------------------------
@bp.route('/delete-restaurant/<int:restaurant_id>', methods=['POST'])
@adminonly
def delete_restaurant(restaurant_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM restaurants WHERE id = %s", (restaurant_id,))
    mysql.connection.commit()
    cur.close()
    flash('Restaurant deleted successfully!', 'info')
    return redirect(url_for('admin.manage_restaurants'))


#---------------------------- parter view of restaurant here you can update the details of restaurant ------------------------------
@bp.route('/my-restaurant', methods=['GET', 'POST'])
def my_restaurant():
    # Check if the partner is logged in and has a restaurant ID in the session
    if session.get('role') != 'partner' or 'restaurant_id' not in session:
        flash('You need to log in as a partner to access this page.', 'danger')
        return redirect(url_for('auth_bp.login_partner'))

    restid = session['restaurant_id']
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        # Collect form data
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']
        abn = request.form['abn']
        imagefile = request.files.get('image_file')

        # Save the image if it exists
        imagepath = imagefilesave(imagefile) if imagefile else None
        
        # If no image is uploaded, retain the old image
        if not imagepath:
            cur.execute("SELECT image_url FROM restaurants WHERE id = %s", (restid))
            imagepath = cur.fetchone()
            imagepath = imagepath[0] if imagepath else None

        # Update the restaurant details
        cur.execute("""
            UPDATE restaurants 
            SET name=%s, address=%s, contact=%s, image_url=%s, abn=%s
            WHERE id = %s
        """, (name, address, contact, imagepath, abn, restid))
        mysql.connection.commit()
        flash('Your restaurant details have been updated.', 'success')
        return redirect(url_for('admin.my_restaurant'))

    # Fetch restaurant details for the form
    cur.execute("SELECT name, address, contact, abn, image_url FROM restaurants WHERE id = %s", (restid,))
    restaurant = cur.fetchone()
    cur.close()

    # If restaurant is not found, handle it gracefully
    if not restaurant:
        flash('Restaurant not found.', 'danger')
        return redirect(url_for('auth_bp.login_partner'))

    # Render the form with restaurant data
    return render_template('partner/my_restaurant.html', restaurant=restaurant)

# ---------------------------------------------- ADMIN AND PARTNER ROUTES---------------------------------------------
# -------------------list of products or adding the product ----------------------------------------------------------
@bp.route('/products', methods=['GET', 'POST'])
@admin_or_partner
def products():

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM categories")
    categories = cur.fetchall()

    role = session.get('role')
    show_restaurant_column = False

    if role == 'partner':
        user_id = session.get('restaurant_id')
        cur.execute("""
            SELECT p.id, p.name, p.description, p.price, p.image_url, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.restaurant_id = %s
            ORDER BY p.id
        """, (user_id,))
    else:
        user_id = session.get('user_id')
        cur.execute("""
            SELECT p.id, p.name, p.description, p.price, p.image_url, c.name AS category_name, r.name AS restaurant_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN restaurants r ON p.restaurant_id = r.id
            ORDER BY p.id
        """)
        show_restaurant_column = True

    products = cur.fetchall()

    if request.method == 'POST':
        if role != 'partner':
            flash('Only partners can add products.', 'danger')
            return redirect(url_for('admin.products'))

        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form.get('category_id') or None
        image_file = request.files.get('image_file')

        imagepath = imagefilesave(image_file)
        if imagepath:
            cur.execute("""
                INSERT INTO products (name, description, price, image_url, category_id, restaurant_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (name, description, price, imagepath, category_id, user_id))
            mysql.connection.commit()
            flash('Product uploaded successfully!', 'success')
            return redirect(url_for('admin.products'))
        else:
            flash('Invalid file format!', 'danger')

    cur.close()
    return render_template('products.html', categories=categories, products=products, show_restaurant=show_restaurant_column, role=role)

# --------------------------------------list of products for editing the product details-------------------------------------------

@bp.route('/edit/<int:prod_id>', methods=['GET', 'POST'])
@admin_or_partner
def edit_product(prod_id):
    cur = mysql.connection.cursor()

    if not product_owner_or_admin(cur, prod_id):
        cur.close()
        flash('You are not allowed to edit this product.', 'danger')
        return redirect(url_for('admin.products'))

    cur.execute("SELECT id, name FROM categories")
    categories = cur.fetchall()

    cur.execute("""
        SELECT name, description, price, image_url, category_id
        FROM products WHERE id = %s
    """, (prod_id,))
    product = cur.fetchone()

    if not product:
        flash('Product not found.', 'warning')
        cur.close()
        return redirect(url_for('admin.products'))

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        category_id = request.form.get('category_id') or None
        image_file = request.files.get('image_file')

        image_url = imagefilesave(image_file) or product[3]

        cur.execute("""
            UPDATE products
            SET name=%s, description=%s, price=%s, image_url=%s, category_id=%s
            WHERE id = %s
        """, (name, description, price, image_url, category_id, prod_id))
        mysql.connection.commit()
        flash('Product updated.', 'success')
        return redirect(url_for('admin.products'))

    cur.close()
    return render_template('edit.html', prod_id=prod_id, product=product, categories=categories)

#--------------------------------- list of products for deleting the product details-------------------------------------------
@bp.route('/delete-product/<int:prod_id>', methods=['POST'])
@admin_or_partner
def delete_product(prod_id):
    cur = mysql.connection.cursor()
    if not product_owner_or_admin(cur, prod_id):
        cur.close()
        flash('You are not allowed to delete this product.', 'danger')
        return redirect(url_for('admin.products'))
    cur.execute("DELETE FROM products WHERE id = %s", (prod_id,))
    mysql.connection.commit()
    cur.close()
    flash('Product deleted.', 'info')
    return redirect(url_for('admin.products'))