from flask import Flask, render_template, request, url_for, redirect, session
from flask_sqlalchemy import SQLAlchemy
import uuid
import json
from datetime import datetime
import os
from slugify import slugify

app = Flask(__name__)
app.secret_key = 'FLkey'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///all.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


@app.route('/')
def landing():
    return render_template("index.html")


class Catalog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(150), unique = True, nullable=False)
    image = db.Column(db.String(100), nullable=False)
    item = db.Column(db.String(100), nullable=False)
    manufacturer = db.Column(db.String(100), nullable=False)
    cost = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(300), nullable=False)

    def __repr__(self):
        return '<Catalog %r>' % self.id

@app.route('/create-product', methods=['GET', 'POST'])
def create_product():
    if request.method == 'POST':
        name = request.form["name"]
        image = request.files["image"]
        item = request.form["item"]
        manufacturer = request.form["manufacturer"]
        cost = request.form["cost"]
        description = request.form["description"]

        if image and name and item and manufacturer and cost and description:
            filename = image.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)

            catalog = Catalog(name=name, slug=slugify(str(name)), image=filename, item=item, manufacturer=manufacturer, cost=float(cost), description=description)
            db.session.add(catalog)
            db.session.commit()

            return redirect("/catalog")

    return render_template("create-product.html")

@app.route('/catalog', methods=['GET', 'POST'])
def catalog():
    selected_manufacturers = request.args.getlist('manufacturer')
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'name_asc')

    manufacturers = db.session.query(Catalog.manufacturer).distinct().all()
    manufacturers = [m[0] for m in manufacturers] if manufacturers else []

    if selected_manufacturers:
        catalogs = Catalog.query.filter(Catalog.manufacturer.in_(selected_manufacturers))
    else:
        catalogs = Catalog.query

    if search_query:
        catalogs = catalogs.filter(
            (Catalog.name.ilike(f'%{search_query}%')) |
            (Catalog.item.ilike(f'%{search_query}%'))
        )

    if sort_by == 'name_asc':
        catalogs = catalogs.order_by(Catalog.name.asc())
    elif sort_by == 'name_desc':
        catalogs = catalogs.order_by(Catalog.name.desc())
    elif sort_by == 'price_asc':
        catalogs = catalogs.order_by(Catalog.cost.asc())
    elif sort_by == 'price_desc':
        catalogs = catalogs.order_by(Catalog.cost.desc())

    catalogs = catalogs.all()

    return render_template('catalog.html', catalogs=catalogs, manufacturers=manufacturers, selected_manufacturers=selected_manufacturers, search_query=search_query, sort_by=sort_by)

@app.route('/product/<string:slug>')
def product(slug):

    catalog_item = Catalog.query.filter_by(slug=slug).first_or_404()
    return render_template('product.html', catalog=catalog_item)

@app.route('/product/<string:slug>/delete')
def product_delete(slug):
    catalog_item = Catalog.query.filter_by(slug=slug).first_or_404()
    try:
        db.session.delete(catalog_item)
        db.session.commit()
        return redirect("/catalog")
    except:
        return "При удалении товара произошла ошибка"

@app.route('/product/<string:slug>/update', methods=['GET', 'POST'])
def update_product(slug):
    catalog_item = Catalog.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        catalog_item.name = request.form.get('name')
        catalog_item.slug = slugify(request.form.get('name'))
        catalog_item.item = request.form.get('item')
        catalog_item.manufacturer = request.form.get('manufacturer')
        catalog_item.cost = float(request.form.get('cost'))
        catalog_item.description = request.form.get('description')

        if 'image' in request.files:
            image = request.files['image']
            if image.filename != '':
                filename = image.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(filepath)
                catalog_item.image = filename

        db.session.commit()
        return redirect(url_for('product', slug=catalog_item.slug))

    return render_template('product-update.html', catalog=catalog_item)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    items = db.Column(db.Text, nullable=False)  # Будем хранить JSON с товарами
    status = db.Column(db.String(20), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Order %r>' % self.id


@app.route('/add-to-cart/<int:product_id>')
def add_to_cart(product_id):
    product = Catalog.query.get_or_404(product_id)
    cart = session.get('cart', {})

    if str(product_id) in cart:
        cart[str(product_id)]['quantity'] += 1
    else:
        cart[str(product_id)] = {
            'id': product.id,
            'name': product.name,
            'price': float(product.cost),
            'quantity': 1,
            'image': product.image
        }

    session['cart'] = cart
    return redirect(request.referrer or url_for('catalog'))


@app.route('/remove-from-cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    if str(product_id) in cart:
        del cart[str(product_id)]
        session['cart'] = cart
    return redirect(url_for('view_cart'))


@app.route('/update-cart/<int:product_id>/<action>')
def update_cart(product_id, action):
    cart = session.get('cart', {})
    if str(product_id) in cart:
        if action == 'increase':
            cart[str(product_id)]['quantity'] += 1
        elif action == 'decrease' and cart[str(product_id)]['quantity'] > 1:
            cart[str(product_id)]['quantity'] -= 1

    session['cart'] = cart
    return redirect(url_for('view_cart'))


@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    products = []
    total = 0

    for item in cart.values():
        product = {
            'id': item['id'],
            'name': item['name'],
            'price': item['price'],
            'quantity': item['quantity'],
            'image': item['image'],
            'subtotal': item['price'] * item['quantity']
        }
        products.append(product)
        total += product['subtotal']

    return render_template('cart.html', products=products, total=total)


@app.route('/submit-order', methods=['POST'])
def submit_order():
    if request.method == 'POST':
        cart = session.get('cart', {})
        if not cart:
            return redirect(url_for('view_cart'))

        order = Order(customer_name=request.form['name'], phone=request.form['phone'], address=request.form['address'], items=json.dumps(cart))

        try:
            db.session.add(order)
            db.session.commit()
            session.pop('cart', None)  # Очищаем корзину после оформления
            return redirect(url_for('order_success', order_id=order.id))
        except Exception as e:
            return f"При оформлении заказа произошла ошибка: {str(e)}"


@app.route('/order-success/<int:order_id>')
def order_success(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('order_success.html', order=order)


# Добавим контекстный процессор для отображения количества в корзине во всех шаблонах
@app.context_processor
def cart_quantity():
    cart = session.get('cart', {})
    quantity = sum(item['quantity'] for item in cart.values()) if cart else 0
    return {'cart_quantity': quantity}

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)

# .venv/scripts/activate
# python app.py
# pip install --upgrade python-slugify