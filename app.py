import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from flask_talisman import Talisman

app = Flask(__name__)
Talisman(app)

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='your_secret_key',
    SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'pharmacy.sqlite'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='alalani@phldistributions.com',  # Replace with your Gmail address
    MAIL_PASSWORD='lzcl toul sczv afst',  # Replace with your Gmail password
    MAIL_DEFAULT_SENDER='alalani@phldistributions.com',  # Replace with your Gmail address
)

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager()
login_manager.init_app(app)
AUTHORIZED_USERS = ['itstirm@gmail.com', 'alalani@phldistributions.com']

# Create instance folder if it doesn't exist
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    pharmacy_phone = db.Column(db.String(150), nullable=False)
    pharmacy_name = db.Column(db.String(150), nullable=False)
    payment_method = db.Column(db.String(150), nullable=False)
    counseling_fees = db.Column(db.Float, default=0.0)
    wheel_total = db.Column(db.Float, default=0.0)

    def __init__(self, email, password, full_name, pharmacy_phone, pharmacy_name, payment_method):
        self.email = email
        self.password = password
        self.full_name = full_name
        self.pharmacy_phone = pharmacy_phone
        self.pharmacy_name = pharmacy_name
        self.payment_method = payment_method

class Counseling(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product = db.Column(db.String(100), nullable=False)
    fee = db.Column(db.Float, nullable=False)
    indication = db.Column(db.String(200), nullable=False)
    cashed_out = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        password = request.form.get('password')
        pharmacy_phone = request.form.get('pharmacy_phone')
        pharmacy_name = request.form.get('pharmacy_name')
        payment_method = request.form.get('payment_method')
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, full_name=full_name, password=hashed_password, pharmacy_phone=pharmacy_phone, pharmacy_name=pharmacy_name, payment_method=payment_method)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if current_user.email not in AUTHORIZED_USERS:
        return "Unauthorized", 403
    
    users = User.query.all()
    counselings = Counseling.query.all()

    return render_template('admin_dashboard.html', users=users, counselings=counselings)


@app.route('/dashboard')
@login_required
def dashboard():
    counselings = Counseling.query.filter_by(user_id=current_user.id).all()
    cashout_total = sum(c.fee for c in counselings if not c.cashed_out)
    wheel_total = current_user.wheel_total
    fee_added = request.args.get('fee_added', 'false').lower() == 'true'

    # Hardcoded counseling points for products
    counseling_points = {
        "Zensa 30g": [
            "Clean and exfoliate skin",
            "DO NOT RUB IN",
            "Leave on the skin for 20-40 minutes",
            "Apply a Thick Layer of cream",
            "Cover with seran wrap or air tight dressing"
        ],
        "Optibac S.Boulardii": [
            "Yeast Based Probiotic so not eliminated by antibiotics",
            "Take with your antibiotics to reduce antibiotic associated diarrhea"
        ]
    }

    return render_template('dashboard.html', counselings=counselings, cashout_total=cashout_total, wheel_total=wheel_total, fee_added=fee_added, counseling_points=counseling_points)

@app.route('/counsel', methods=['POST'])
@login_required
def counsel():
    product = request.form.get('product')
    fee = 5.00 if product == "Zensa 30g" else 2.00
    indication = request.form.get('indication')
    new_counseling = Counseling(user_id=current_user.id, product=product, fee=fee, indication=indication)
    current_user.counseling_fees += fee
    db.session.add(new_counseling)
    db.session.commit()
    return redirect(url_for('dashboard', fee_added=True))

@app.route('/cashout', methods=['POST'])
@login_required
def cashout():
    uncased_counselings = db.session.query(Counseling).filter_by(user_id=current_user.id, cashed_out=False).all()
    total_amount = sum(counseling.fee for counseling in uncased_counselings)

    # Mark the entries as cashed out
    for counseling in uncased_counselings:
        counseling.cashed_out = True
    current_user.wheel_total += total_amount  # Update the wheel total on cashout
    current_user.counseling_fees = 0.0  # Reset cashout total
    db.session.commit()

    # Send email
    try:
        msg = Message('Cashout Summary', recipients=['hassan.l@phldistributions.com', current_user.email])
        msg.body = f"User {current_user.full_name} has cashed out.\n\n"
        msg.body += "Counselings:\n"
        for counseling in uncased_counselings:
            msg.body += f"- {counseling.product}: ${counseling.fee} for {counseling.indication}\n"
        msg.body += f"\nTotal cashed out: ${total_amount}\n"
        msg.body += f"\nProfile Information:\nFull Name: {current_user.full_name}\nEmail: {current_user.email}\nPharmacy Phone: {current_user.pharmacy_phone}\nPharmacy Name: {current_user.pharmacy_name}\nPayment Method: {current_user.payment_method}"

        mail.send(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

    flash('You have successfully cashed out.')
    return redirect(url_for('dashboard'))

@app.route('/edit_user/<int:user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    if current_user.email not in AUTHORIZED_USERS:
        return "Unauthorized", 403

    user = User.query.get_or_404(user_id)
    user.email = request.form.get('email')
    user.full_name = request.form.get('full_name')
    user.pharmacy_phone = request.form.get('pharmacy_phone')
    user.pharmacy_name = request.form.get('pharmacy_name')
    user.payment_method = request.form.get('payment_method')
    user.counseling_fees = float(request.form.get('counseling_fees'))
    user.wheel_total = float(request.form.get('wheel_total'))
    
    db.session.commit()
    flash('User information updated successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_counseling/<int:counseling_id>', methods=['POST'])
@login_required
def edit_counseling(counseling_id):
    if current_user.email not in AUTHORIZED_USERS:
        return "Unauthorized", 403

    counseling = Counseling.query.get_or_404(counseling_id)
    counseling.product = request.form.get('product')
    counseling.fee = float(request.form.get('fee'))
    counseling.indication = request.form.get('indication')
    counseling.cashed_out = request.form.get('cashed_out') == 'True'
    
    db.session.commit()
    flash('Counseling information updated successfully.')
    return redirect(url_for('admin_dashboard'))




@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        print(f"Login attempt for email: {email}")
        user = User.query.filter_by(email=email).first()
        if user:
            print(f"User found: {user.email}")
        else:
            print("User not found")
        if user and check_password_hash(user.password, password):
            print("Password is correct")
            login_user(user)
            if user.email in AUTHORIZED_USERS:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password')
            return render_template('login.html', error='Invalid email or password')  # Return render_template to keep form filled
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset_wheel_total')
@login_required
def reset_wheel_total():
    if current_user.is_authenticated and current_user.email == 'hassan.l@phldistributions.com':  # Replace with your admin email
        current_user.wheel_total = 0
        db.session.commit()
        return "Wheel total reset to 0"
    else:
        return "Unauthorized", 403

@app.route('/delete_counseling/<int:id>', methods=['POST'])
@login_required
def delete_counseling(id):
    counseling = Counseling.query.get(id)
    if counseling and counseling.user_id == current_user.id:
        db.session.delete(counseling)
        db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name')
        current_user.pharmacy_phone = request.form.get('pharmacy_phone')
        current_user.pharmacy_name = request.form.get('pharmacy_name')
        current_user.email = request.form.get('email')
        current_user.payment_method = request.form.get('payment_method')
        if request.form.get('password'):
            current_user.password = generate_password_hash(request.form.get('password'), method='pbkdf2:sha256')
        db.session.commit()
        flash('Profile updated successfully.')
        return redirect(url_for('dashboard'))
    return render_template('profile.html')

if __name__ == '__main__':
    with app.app_context():
        print("Creating database tables...")
        db.create_all()  # Create tables if they don't exist
        print("Database tables created.")
    app.run(debug=True)
