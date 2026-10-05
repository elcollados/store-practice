from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import DictCursor


load_dotenv()

app = Flask(__name__)


SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

app.secret_key = SECRET_KEY


orders = []
products = [
    {"id": 0, "name": "zero", "price": 1, "stock": 0, "image": "zero.jpg"},
    {"id": 1, "name": "one", "price": 100, "stock": 10, "image": "one.jpg"},
    {"id": 2, "name": "two", "price": 200, "stock": 22, "image": "two.jpg"},
    {"id": 3, "name": "three", "price": 300, "stock": 33, "image": "three.jpg"},
    {"id": 4, "name": "four", "price": 400, "stock": 44, "image": "four.jpg"},
    {"id": 5, "name": "five", "price": 500, "stock": 55, "image": "five.jpg"},
    {"id": 6, "name": "six", "price": 600, "stock": 66, "image": "six.jpg"},
    {"id": 7, "name": "seven", "price": 700, "stock": 77, "image": "seven.jpg"},
    {"id": 8, "name": "eight", "price": 800, "stock": 88, "image": "eight.jpg"},
    {"id": 9, "name": "nine", "price": 900, "stock": 99, "image": "nine.jpg"},
    {"id": 10, "name": "ten", "price": 1000, "stock": 100, "image": "ten.jpg"}
]


def get_db():
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
        return conn

    conn = sqlite3.connect("store.db")
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(cursor, query, values):
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        query = query.replace("?", "%s")

    cursor.execute(query, values)

def create_tables():
    conn = get_db()
    cursor = conn.cursor()

    database_url = os.getenv("DATABASE_URL")
    id_column = "id SERIAL PRIMARY KEY" if database_url else "id INTEGER PRIMARY KEY AUTOINCREMENT"
    

    execute_query(cursor, f"""
        CREATE TABLE IF NOT EXISTS users2 (
            {id_column},
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
         )
    """,())

    execute_query(cursor, f"""
        CREATE TABLE IF NOT EXISTS orders2 (
            {id_column},
            user_id INTEGER,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """,())

    execute_query(cursor, f"""
        CREATE TABLE IF NOT EXISTS order_items2 (
            {id_column},
            order_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            subtotal REAL NOT NULL
        )
    """,())

    conn.commit()
    conn.close()

create_tables()

def admin_required():
    if "user_id" not in session:
        return False
    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"SELECT is_admin FROM users2 WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()
    return user and user["is_admin"] == 1

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        password_hash = generate_password_hash(password)

        conn = get_db()
        cursor = conn.cursor()

        try:
            execute_query(cursor,
                "INSERT INTO users2 (name, email, password_hash) VALUES(?, ?, ?)",
                (name, email, password_hash)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Email already registered"

        conn.close()
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cursor = conn.cursor()
        execute_query(cursor,"SELECT * FROM users2 WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("profile"))
        
        return "Invalid email or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect(url_for("home"))



@app.route("/")
def home():
    return render_template("home.html", products=products)


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    for product in products:
        if product["id"] == product_id:
            return render_template("product.html", product=product) 
    return "Product not found", 404


@app.route("/search")
def search():
    query = request.args.get("search", "")

    results = []
    for product in products:
        if query.lower() in product["name"].lower():
            results.append(product)

    return render_template("search.html", results=results, query=query)


@app.route("/live") 
def live():
    return render_template("live.html")


@app.route("/place-order", methods=["POST"])
def place_order():
    name = request.form["name"]
    address = request.form["address"]

    cart_data = session.get("cart", {})
    user_id = session.get("user_id")


    cart_products = []
    for product in products:
        key = str(product["id"])
        if key in cart_data:
            quantity = cart_data[key]
            subtotal = product["price"] * quantity
            cart_products.append({
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

    total = 0
    for product in cart_products:
        total += product["subtotal"]


    conn = get_db()
    cursor = conn.cursor()
    
    execute_query(cursor,
        "INSERT INTO orders2 (user_id, name, address, total) VALUES (?, ?, ?, ?)",
        (user_id, name, address, total)
    )
    order_id = cursor.lastrowid
    
    for product in cart_products:
        execute_query(cursor,
            "INSERT INTO order_items2 (order_id, name, price, quantity, subtotal) VALUES (?, ?, ?, ?, ?)",
            (order_id, product["name"], product["price"], product["quantity"], product["subtotal"]))
    
    conn.commit()
    conn.close()

    session.pop("cart", None)

    return render_template(
        "order.html",
        name=name,
        address=address,
        cart_products=cart_products,
        total=total
    )


@app.route("/admin/orders")
def admin_orders():
    if not admin_required():
        return redirect(url_for("login"))
    
    conn = get_db()
    cursor = conn.cursor()

    execute_query(cursor,"SELECT * FROM orders2 ORDER BY id DESC",())
    all_orders = cursor.fetchall()
    conn.close()

    return render_template("admin_orders.html", orders=all_orders)



@app.route("/admin/update-status/<int:order_id>", methods=["POST"])
def update_status(order_id):
    if not admin_required():
        return redirect(url_for("login"))

    new_status = request.form["status"]

    conn = get_db()
    cursor = conn.cursor()
    execute_query(cursor,"UPDATE orders2 SET status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_orders"))


@app.route("/checkout")
def checkout():
    cart_data = session.get("cart", {})

    if not cart_data:   
        return redirect(url_for("cart"))

    return render_template("checkout.html")


@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    cart = session.get("cart", {})
    key  = str(product_id)

    if key in cart:
        cart[key] += 1
    else:
        cart[key] = 1

    session["cart"] = cart
    return redirect(request.referrer)


@app.route("/increase-quantity/<int:product_id>")
def increase_quantity(product_id):
    cart = session.get("cart", {})
    key = str(product_id)

    if key in cart:
        cart[key] += 1

    session["cart"] = cart
    return redirect(url_for("cart"))


@app.route("/decrease-quantity/<int:product_id>")
def decrease_quantity(product_id):
    cart = session.get("cart", {})
    key = str(product_id)

    if key in cart:
        cart[key] -= 1
        if cart[key] <=0:
            del cart[key]

    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/remove-cart/<int:product_id>")
def remove_cart(product_id):
    cart = session.get("cart", {})
    key = str(product_id)

    if key in cart:
        del cart[key]

    session["cart"] = cart
    return redirect(url_for("cart"))



@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})

    cart_products = []
    for product in products:
        key = str(product["id"]) 
        if key in cart_data:
            quantity = cart_data[key]
            subtotal = product["price"] * quantity

            cart_products.append({
                "id": product["id"],
                "name": product["name"],
                "price": product["price"],
                "quantity": quantity,
                "subtotal": subtotal
            })

    total_price = 0
    total_quantity = 0
    for product in cart_products:
        total_price += product["subtotal"]
        total_quantity += product["quantity"]
        
    return render_template("cart.html", cart_products=cart_products, total_price=total_price,total_quantity=total_quantity)


@app.route("/clear-cart")
def clear_session():
    session.clear()
    return "Session cleared"


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("register"))

    conn = get_db()
    cursor = conn.cursor()

    execute_query(cursor,"SELECT * FROM users2 WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()

    execute_query(cursor,"SELECT * FROM orders2 WHERE user_id = ? ORDER BY id DESC", (session["user_id"],))
    user_orders = cursor.fetchall()

    orders_with_items = []
    for order in user_orders:
        execute_query(cursor,"SELECT * FROM order_items2 WHERE order_id = ?", (order["id"],))
        items = cursor.fetchall()
        orders_with_items.append({
            "id": order["id"],
            "address": order["address"],
            "total": order["total"],
            "status": order["status"],
            "products": items
        })


    conn.close()

    return render_template("profile.html", user=user, orders=orders_with_items)


DEBUG_MODE = os.getenv("FLASK_DEBUG", "0") == "1"

if __name__ == "__main__":
    app.run(debug=DEBUG_MODE)