from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from .. import mysql
from decimal import Decimal
from datetime import datetime
user_bp = Blueprint('user', __name__)

# ------------------------- searching the restauarnt ----------------------------
#  seraching the restaurant 
@user_bp.route('/search', methods=['GET'])
def search_restaurants():
#  stripiing thequery from the form
    query = request.args.get('query', '').strip()
    cur = mysql.connection.cursor()
    cur.execute(
    "SELECT id, name, address, contact, image_url FROM restaurants WHERE LOWER(name) LIKE %s OR LOWER(address) LIKE %s",
    (f'%{query.lower()}%', f'%{query.lower()}%')
)

    results = cur.fetchall()
    cur.close()

    return render_template('user/restaurant.html', restaurants=results, search_query=query)

# ----------------- viewing the restaurant list ----------------------
@user_bp.route('/restaurants')
def view_restaurants():
    # fetching the data from the databse
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, address, contact, image_url FROM restaurants")
    restaurants = cur.fetchall()
    cur.close()
    return render_template('user/restaurant.html', restaurants=restaurants)

  
# -------------- showing the restaurant details to the user ----------------------
@user_bp.route('/restaurant/<int:restaurant_id>')

def restaurant_detail(restaurant_id):
    cur = mysql.connection.cursor()
    # Fetch restaurant details from the database
    cur.execute("SELECT name, address FROM restaurants WHERE id = %s", (restaurant_id,))
    restaurant = cur.fetchone()

    if not restaurant:
        flash("Restaurant not found.", "warning")
        return redirect(url_for('admin.view_restaurants'))

    # Fetch products with category name and image_url
    cur.execute("""
    SELECT
        p.id,              
        p.name,
        p.description,
        p.price,
        p.image_url,
        c.name AS category_name
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.id
    WHERE p.restaurant_id = %s
""", (restaurant_id,))
    products = cur.fetchall()
    cur.close()

    return render_template('user/restaurant_detail.html', restaurant=restaurant, products=products)

# ---------------------------view cart ------------------------------------
@user_bp.route('/cart')
def view_cart():
    cart = session.get('cart', {})

    if not cart:
        products = []
        subtotal = Decimal('0.00')
    else:
        product_ids = tuple(map(int, cart.keys()))

        if not product_ids:  #Empty tuple
            products = []
            subtotal = Decimal('0.00')
        else:
            cur = mysql.connection.cursor()
            format_strings = ','.join(['%s'] * len(product_ids))
            query = f"SELECT id, name, description, price, image_url, restaurant_id FROM products WHERE id IN ({format_strings})"
            cur.execute(query, product_ids)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            cur.close()

            products = []
            for row in rows:
                product_dict = dict(zip(columns, row))
                product_id_str = str(product_dict['id'])
                quantity = cart.get(product_id_str, 0)

                #  price is handled as Decimal
                price = Decimal(str(product_dict['price']))

                product_dict['quantity'] = quantity
                product_dict['total_price'] = price * quantity
                products.append(product_dict)

            #  Use Decimal for precision
            subtotal = sum(p['total_price'] for p in products)

    delivery_fee = Decimal('2.99') if subtotal > 0 else Decimal('0.00')
    tax = (subtotal * Decimal('0.08')).quantize(Decimal('0.01'))
    total = (subtotal + delivery_fee + tax).quantize(Decimal('0.01'))

    return render_template('user/cart.html', products=products, subtotal=subtotal, delivery_fee=delivery_fee, tax=tax, total=total)

# ------------------------------------------ add to cart -----------------------------------------------------------

@user_bp.route('/add_to_cart/<int:product_id>', methods=['POST'])

def add_to_cart(product_id):
    cart = session.get('cart', {})
    pid = str(product_id)
    cart[pid] = cart.get(pid, 0) + 1
    session['cart'] = cart
    flash("Product added to cart!", "success")
    return redirect(request.referrer or url_for('user.view_cart'))
# ----------------------------------------- INCREASE THE PRODUCT QUANTITY-----------------------------------------------------
@user_bp.route('/cart/increase/<int:product_id>', methods=['POST'])
def increase_quantity(product_id):
    cart = session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        cart[pid] += 1  # Increase the quantity by 1
    else:
        cart[pid] = 1

    session['cart'] = cart
    flash(f"Quantity updated for product ID: {product_id}", "success")
    return redirect(url_for('user.view_cart'))



# ----------------------------------------- DECREASE THE QUANTITY OF PRODUCT ------------------------------------------------------

@user_bp.route('/cart/decrease/<int:product_id>', methods=['POST'])
def decrease_quantity(product_id):
    cart = session.get('cart', {})
    pid = str(product_id)

    if pid in cart:
        if cart[pid] > 1:
            cart[pid] -= 1
        else:
            del cart[pid]
    session['cart'] = cart
    flash(f"Quantity updated for product ID: {product_id}", "success")
    return redirect(url_for('user.view_cart'))



# ----------------------------------------- REMOVE THE PRODUCT FROM CART ------------------------------------------------

@user_bp.route('/remove_from_cart/<int:product_id>', methods=['POST'])
   
# removing the product quantity in cart for user---
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    pid_str = str(product_id)
    if pid_str in cart:
        del cart[pid_str]
        session['cart'] = cart
        flash("Product removed from cart.", "info")
    return redirect(url_for('user.view_cart'))


@user_bp.route('/checkout', methods=['GET', 'POST'])
#-------------------------------------------------------- check out page for user ----------------------------------------------------------


# --------------------------------- Checkout Route ------------------------------------
@user_bp.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if not session.get('user_id'):
        flash("You must be registered and logged in to proceed to checkout.", "warning")
        return redirect(url_for('auth_bp.signup'))

    cart = session.get('cart', {})

    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('user.view_cart'))

    if request.method == 'POST':
        product_ids = tuple(map(int, cart.keys()))
        cur = mysql.connection.cursor()
        format_strings = ','.join(['%s'] * len(product_ids))
        query = f"SELECT id, price FROM products WHERE id IN ({format_strings})"
        cur.execute(query, product_ids)
        products_data = cur.fetchall()

        # Calculate subtotal
        subtotal = Decimal('0.00')
        product_price_map = {}
        for pid, price in products_data:
            product_price_map[pid] = Decimal(str(price))
            quantity = cart.get(str(pid), 0)
            subtotal += product_price_map[pid] * quantity

        delivery_fee = Decimal('2.99') if subtotal > 0 else Decimal('0.00')
        tax = (subtotal * Decimal('0.08')).quantize(Decimal('0.01'))
        total = (subtotal + delivery_fee + tax).quantize(Decimal('0.01'))

        try:
            # Insert into orders table
            user_id = session['user_id']
            cur.execute("""
                INSERT INTO orders (customer_id, order_date, status, total_amount)
                VALUES (%s, NOW(), %s, %s)
            """, (user_id, 'Pending', total))
            order_id = cur.lastrowid

            # Insert into order_items
            for pid, price in products_data:
                quantity = cart.get(str(pid), 0)
                if quantity > 0:
                    cur.execute("""
                        INSERT INTO order_items (order_id, product_id, quantity, price)
                        VALUES (%s, %s, %s, %s)
                    """, (order_id, pid, quantity, product_price_map[pid]))

            mysql.connection.commit()
            cur.close()

            # Clear the cart
            session['cart'] = {}

            # Flash success message and redirect to main page
            flash("Order placed successfully! Thank you for shopping with us.", "success")
            return redirect(url_for('main.index'))  # Redirect to main page

        except Exception as e:
            mysql.connection.rollback()
            cur.close()
            flash(f"Error placing order: {e}", "danger")
            return redirect(url_for('user.view_cart'))

    # If it's a GET request, render the checkout page as usual
    else:
        product_ids = tuple(map(int, cart.keys()))
        if not product_ids:
            products = []
            subtotal = Decimal('0.00')
        else:
            cur = mysql.connection.cursor()
            format_strings = ','.join(['%s'] * len(product_ids))
            query = f"SELECT id, name, description, price, image_url, restaurant_id FROM products WHERE id IN ({format_strings})"
            cur.execute(query, product_ids)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            cur.close()

            products = []
            for row in rows:
                product_dict = dict(zip(columns, row))
                product_id_str = str(product_dict['id'])
                quantity = cart.get(product_id_str, 0)
                price = Decimal(str(product_dict['price']))
                product_dict['quantity'] = quantity
                product_dict['total_price'] = price * quantity
                products.append(product_dict)

            subtotal = sum(p['total_price'] for p in products)

        delivery_fee = Decimal('2.99') if subtotal > 0 else Decimal('0.00')
        tax = (subtotal * Decimal('0.08')).quantize(Decimal('0.01'))
        total = (subtotal + delivery_fee + tax).quantize(Decimal('0.01'))

        return render_template('user/checkout.html', products=products, subtotal=subtotal, delivery_fee=delivery_fee, tax=tax, total=total)
