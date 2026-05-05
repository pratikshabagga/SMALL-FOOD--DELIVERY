from flask import Blueprint, render_template, request  # <-- import request here
from .. import mysql   # import MySQL extension

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    category_filter = request.args.get('filter')  # now works
    cur = mysql.connection.cursor()

    # Fetching all categories dynamically
    cur.execute("SELECT name FROM categories")
    categories = [row[0] for row in cur.fetchall()]

    # Fetching products
    if category_filter:
        query = """
            SELECT p.id, p.name, p.description, p.price, p.image_url, c.name AS category_name, r.name AS restaurant_name, COALESCE(r.id, 0) AS restaurant_id
            FROM products p
            LEFT JOIN restaurants r ON p.restaurant_id = r.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE LOWER(c.name) = %s
        """
        cur.execute(query, (category_filter.lower(),))
    else:
        cur.execute("""
            SELECT 
                p.id,
                p.name,
                p.description,
                p.price,
                p.image_url,
                COALESCE(c.name, 'Uncategorized') AS category_name,
                COALESCE(r.name, 'No Restaurant Assigned') AS restaurant_name,
                COALESCE(r.id, 0) AS restaurant_id
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN restaurants r ON p.restaurant_id = r.id
        """)

    products = cur.fetchall()
    cur.close()
    
    # Pass categories to the template
    return render_template('index2.html', products=products, categories=categories)


# You can put error handlers in the blueprint, but
# they are better registered on the app object for global handling.

@bp.app_errorhandler(404)  # note the use of app_errorhandler here
def not_found(e):
    return render_template('404.html'), 404

@bp.app_errorhandler(500)
def internal_error(e):
    return render_template('500.html'), 500
