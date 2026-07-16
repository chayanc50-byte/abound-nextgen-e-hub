from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import random
import string
from sqlalchemy import text, or_, func
from dotenv import load_dotenv
from integrations.resend_email import send_email

import hierarchy as hierarchy_config

load_dotenv()

app = Flask(__name__)
#app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY',
    'dev-secret-key'
)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sales_team.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'images')
app.config['CATEGORY_UPLOAD_URL_PREFIX'] = '/static/uploads/categories'
app.config['CATEGORY_UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads', 'categories')
app.config['CATEGORY_PERSIST_FOLDER'] = os.path.join(app.instance_path, 'uploads', 'categories')
# Email config - set in environment or .env for production
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_FROM'] = os.environ.get('MAIL_FROM', 'noreply@uniquejewels.com')
app.config['APP_URL'] = os.environ.get('APP_URL', 'http://localhost:5001')
# Firebase FCM - set in .env for push notifications
app.config['FIREBASE_API_KEY'] = os.environ.get('FIREBASE_API_KEY', '')
app.config['FIREBASE_PROJECT_ID'] = os.environ.get('FIREBASE_PROJECT_ID', '')
app.config['FIREBASE_APP_ID'] = os.environ.get('FIREBASE_APP_ID', '')
app.config['FIREBASE_MESSAGING_SENDER_ID'] = os.environ.get('FIREBASE_MESSAGING_SENDER_ID', '')
app.config['FIREBASE_VAPID_KEY'] = os.environ.get('FIREBASE_VAPID_KEY', '')
app.config['FIREBASE_SERVICE_ACCOUNT_PATH'] = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')
app.config['RAZORPAY_KEY_ID'] = os.environ.get('RAZORPAY_KEY_ID', '').strip()
app.config['RAZORPAY_KEY_SECRET'] = os.environ.get('RAZORPAY_KEY_SECRET', '').strip()

# Configurable constants for retail customer system
SAVINGS_POINT_RATE = 0.10  # 0.1 points per rupee (10 points per ₹100)
REWARD_THRESHOLD = 5000  # Points needed to be eligible for a reward

db = SQLAlchemy(app)

# Firebase Admin (lazy init)
_firebase_app = None
_firebase_import_unavailable = False

def ensure_category_upload_folder():
    persist_dir = app.config['CATEGORY_PERSIST_FOLDER']
    static_dir = app.config['CATEGORY_UPLOAD_FOLDER']
    os.makedirs(persist_dir, exist_ok=True)
    os.makedirs(os.path.dirname(static_dir), exist_ok=True)
    if not os.path.exists(static_dir):
        try:
            os.symlink(persist_dir, static_dir, target_is_directory=True)
        except Exception:
            os.makedirs(static_dir, exist_ok=True)

ensure_category_upload_folder()

def save_category_image(file_storage):
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return None
    fn = secure_filename(file_storage.filename)
    if not fn:
        return None
    ext = fn.rsplit('.', 1)[-1].lower() if '.' in fn else 'jpg'
    fn = f"category_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{ext}"
    up_dir = app.config['CATEGORY_UPLOAD_FOLDER']
    os.makedirs(up_dir, exist_ok=True)
    file_storage.save(os.path.join(up_dir, fn))
    return f"{app.config['CATEGORY_UPLOAD_URL_PREFIX']}/{fn}"

def get_firebase_app():
    global _firebase_app, _firebase_import_unavailable
    if _firebase_app is not None:
        return _firebase_app
    if _firebase_import_unavailable:
        return None
    path = app.config.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')
    if not path or not os.path.isfile(path):
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        _firebase_import_unavailable = True
        app.logger.warning(
            'firebase-admin is not installed; push notifications are disabled. '
            'Install with: pip install firebase-admin'
        )
        return None
    cred = credentials.Certificate(path)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app

def generate_referral_id():
    """Generate unique referral ID: ABN + 5 alphanumeric (e.g. ABN10245)."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):
        suffix = ''.join(random.choices(chars, k=5))
        ref_id = f'ABN{suffix}'
        if not User.query.filter_by(referral_id=ref_id).first():
            return ref_id
    raise ValueError('Could not generate unique referral ID')

def generate_product_sku():
    """Generate a unique product SKU when the admin leaves it blank."""
    for _ in range(100):
        sku = f"SKU-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(1000,9999)}"
        if not Product.query.filter_by(sku=sku).first():
            return sku
    return f"SKU-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(10000,99999)}"

def decrement_tracked_stock(product, quantity):
    """Reduce inventory only for tracked-stock products."""
    if product.stock_quantity is not None and product.stock_quantity > 0:
        product.stock_quantity = max(0, product.stock_quantity - quantity)

def send_welcome_email(user):
    """Send welcome email to new registrants."""

    try:
        app_url = app.config.get(
            "APP_URL",
            "https://aboundehub.com"
        )

        body = render_template(
            "email_welcome.html",
            full_name=user.full_name,
            username=user.username,
            referral_id=user.referral_id,
            app_url=app_url,
        )

        return send_email(
            to=user.email,
            subject="Welcome to Abound Next-Gen E-Hub - Your Account Details",
            html=body,
        )

    except Exception as e:
        app.logger.exception(
            f"Failed to prepare welcome email: {e}"
        )
        return False

def send_order_notification(order):
    """Email admin when order is placed."""

    admins = User.query.filter(
        User.user_role.in_(["admin", "super_admin"])
    ).all()

    if not admins:
        return False

    try:

        body = render_template(
            "email_order_notification.html",
            order=order,
            app_url=app.config["APP_URL"],
        )

        return send_email(
            to=[a.email for a in admins],
            subject=f"New Order #{order.id} - Abound Next-Gen E-Hub",
            html=body,
        )

    except Exception as e:
        app.logger.exception(e)
        return False

def send_order_confirmation_buyer(order):
    """Email buyer when order is placed."""

    try:

        body = render_template(
            "email_order_confirmation_buyer.html",
            order=order,
            app_url=app.config["APP_URL"],
        )

        return send_email(
            to=order.user.email,
            subject=f"Order Confirmation #{order.id} - Abound Next-Gen E-Hub",
            html=body,
        )

    except Exception as e:
        app.logger.exception(e)
        return False


def send_order_shipped_buyer(order):
    """Email buyer when order is shipped."""

    try:

        body = render_template(
            "email_order_shipped_buyer.html",
            order=order,
            app_url=app.config["APP_URL"],
        )

        return send_email(
            to=order.user.email,
            subject="Your Order Has Been Shipped - Abound Next-Gen E-Hub",
            html=body,
        )

    except Exception as e:
        app.logger.exception(e)
        return False


def send_push_notification(user_ids, title, body, click_action=None, icon=None):
    """Send FCM push notification to users. user_ids can be int or list of ints."""
    if not isinstance(user_ids, (list, tuple)):
        user_ids = [user_ids]
    fa = get_firebase_app()
    if not fa:
        return False
    try:
        from firebase_admin import messaging
        tokens = []
        for uid in user_ids:
            for dt in DeviceToken.query.filter_by(user_id=uid).all():
                if dt.token and dt.token not in tokens:
                    tokens.append(dt.token)
        if not tokens:
            return False
        app_url = app.config.get('APP_URL', 'http://localhost:5001').rstrip('/')
        full_url = (click_action if click_action and click_action.startswith('http') else f'{app_url}{click_action or "/"}') if click_action else app_url + '/'
        data = {'url': full_url}
        notif = messaging.Notification(title=title, body=body, image=icon)
        webpush_cfg = None
        if full_url and full_url.startswith('https'):
            webpush_cfg = messaging.WebpushConfig(fcm_options=messaging.WebpushFCMOptions(link=full_url))
        elif full_url:
            data['click_action'] = full_url
        payload = messaging.MulticastMessage(
            notification=notif,
            data=data,
            tokens=tokens,
            android=messaging.AndroidConfig(priority='high', notification=messaging.AndroidNotification(click_action=full_url)) if full_url else None,
            webpush=webpush_cfg
        )
        messaging.send_each_for_multicast(payload)
        return True
    except Exception as e:
        app.logger.error(f'FCM push failed: {e}')
        return False

def send_order_shipped_admin(order):
    """Email admins when order is shipped."""
    admins = User.query.filter(User.user_role.in_(['admin', 'super_admin'])).all()
    if not admins:
        return False
    try:
        body = render_template('email_order_shipped_admin.html', order=order, app_url=app.config['APP_URL'])
        return send_email(
            to=[a.email for a in admins],
            subject=f'Order Shipped Notification #{order.id} - Abound NextGen E Hub',
            html=body,
        )
    except Exception as e:
        app.logger.error(f'Failed to send order shipped notification to admin: {e}')
        return False

def send_credentials_email(user, password):
    """Email login credentials to user (e.g. when admin creates user with auto-generated password)."""
    try:
        body = render_template('email_credentials.html', user=user, password=password, app_url=app.config['APP_URL'])
        return send_email(
            to=user.email,
            subject='Your Abound Next-Gen E-Hub Login Credentials',
            html=body,
        )
    except Exception as e:
        app.logger.error(f'Failed to send credentials email: {e}')
        return False

def send_notification_email(to_email, title, message, click_action=None):
    """Send admin announcement email to a single recipient."""
    try:
        app_url = app.config.get('APP_URL', 'http://localhost:5001').rstrip('/')
        body = render_template('email_notification.html',
            title=title,
            message=message,
            click_action=click_action,
            app_url=app_url
        )
        return send_email(
            to=to_email,
            subject=f'{title} - Abound NextGen E Hub',
            html=body,
        )
    except Exception as e:
        app.logger.error(f'Failed to send notification email to {to_email}: {e}')
        return False

def send_contact_form_email(name, email, subject, message):
    """Send contact form submission to support email."""
    support_email = 'aboundehub@gmail.com'
    try:
        body = f"""New Contact Form Message

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}
"""
        html = f'<pre>{body}</pre>'
        return send_email(
            to=support_email,
            subject='New Contact Form Message',
            html=html,
        )
    except Exception as e:
        app.logger.error(f'Failed to send contact form email: {e}')
        return False

def get_logo_url():
    """Return logo URL if a logo file exists."""
    img_dir = app.config['UPLOAD_FOLDER']
    if not os.path.isdir(img_dir):
        return None
    for ext in ['png', 'jpg', 'jpeg', 'webp', 'svg', 'gif']:
        path = os.path.join(img_dir, f'logo.{ext}')
        if os.path.isfile(path):
            return url_for('static', filename=f'images/logo.{ext}')
    return None

def get_director_profile_url():
    """Return director profile image URL if file exists. Place director-profile.png/jpg in static/images/."""
    img_dir = app.config['UPLOAD_FOLDER']
    if not os.path.isdir(img_dir):
        return None
    for ext in ['png', 'jpg', 'jpeg', 'webp']:
        path = os.path.join(img_dir, f'director-profile.{ext}')
        if os.path.isfile(path):
            return url_for('static', filename=f'images/director-profile.{ext}')
    return None

def get_director_signature_url():
    """Return director signature image URL if file exists. Place director-signature.png in static/images/."""
    img_dir = app.config['UPLOAD_FOLDER']
    if not os.path.isdir(img_dir):
        return None
    for ext in ['png', 'jpg', 'jpeg', 'webp']:
        path = os.path.join(img_dir, f'director-signature.{ext}')
        if os.path.isfile(path):
            return url_for('static', filename=f'images/director-signature.{ext}')
    return None

@app.context_processor
def inject_globals():
    d = {
        'logo_url': get_logo_url(),
        'director_profile_url': get_director_profile_url(),
        'director_signature_url': get_director_signature_url(),
        'app_url': app.config['APP_URL']
    }
    if 'user_id' in session:
        u = User.query.get(session['user_id'])
        d['is_admin'] = u.is_admin_role if u else False
        d['is_super_admin'] = u.is_super_admin if u else False
        d['current_user'] = u
    else:
        d['is_admin'] = False
        d['is_super_admin'] = False
        d['current_user'] = None
    return d

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    user_level = db.Column(db.Integer, default=1)  # 1-10 for sales; 0/None = admin/super_admin (no level)
    parent_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referral_id = db.Column(db.String(12), unique=True, nullable=True)  # ABN + 5 chars
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    user_status = db.Column(db.String(20), default='active')  # active, inactive, suspended
    is_admin = db.Column(db.Boolean, default=False)  # Legacy
    user_role = db.Column(db.String(20), default='user')  # user, admin, super_admin, customer
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    # Legacy: position kept for migration, maps to user_level
    position = db.Column(db.String(80), nullable=True)
    # For retail customers: assigned sales member
    assigned_member_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    children = db.relationship('User', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', foreign_keys='User.parent_id')
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_sales_children(self):
        """Children that are sales users (user_role=user) only."""
        return [c for c in self.children if getattr(c, 'user_role', None) == 'user']
    
    def get_team_count(self):
        return sum(1 for c in self.children if getattr(c, 'user_role', None) == 'user')
    
    def get_direct_referrals(self):
        return [c for c in self.children.all() if getattr(c, 'user_role', None) == 'user']
    
    def get_all_descendants(self):
        """Only sales users (user_role=user) in the pyramid."""
        descendants = []
        for child in self.children:
            if getattr(child, 'user_role', None) == 'user':
                descendants.append(child)
                descendants.extend(child.get_all_descendants())
        return descendants
    
    @property
    def level_name(self):
        r = getattr(self, 'user_role', None)
        if r == 'super_admin':
            return 'Super Admin'
        if r == 'admin':
            return 'Admin'
        for lvl, name in hierarchy_config.LEVELS:
            if lvl == self.user_level:
                return name
        return hierarchy_config.LEVELS[0][1]  # Sales Executive
    
    def get_upline_chain(self, max_levels=10):
        """Trace referral chain upward - only sales users, stop at admin/super_admin."""
        chain = []
        current = self.parent
        while current and len(chain) < max_levels:
            if getattr(current, 'user_role', None) in ('admin', 'super_admin'):
                break  # Stop chain, do not include admin in commission
            chain.append(current)
            current = current.parent
        return chain

    def get_commission_upline_chain(self, max_levels=10):
        """Upline chain for commission: sponsor first, then sponsor's upline. Skip inactive, stop at admin."""
        chain = []
        current = self.parent
        while current and len(chain) < max_levels:
            if getattr(current, 'user_role', None) in ('admin', 'super_admin'):
                break  # Admin/Super Admin never receive commission
            if not getattr(current, 'is_user_active', True):
                current = current.parent  # Skip inactive, continue upward
                continue
            if getattr(current, 'user_role', None) == 'user':
                chain.append(current)
            current = current.parent
        return chain
    
    @property
    def is_super_admin(self):
        return getattr(self, 'user_role', None) == 'super_admin'
    
    @property
    def is_admin_role(self):
        r = getattr(self, 'user_role', None)
        return r in ('admin', 'super_admin')
    
    @property
    def is_sales_user(self):
        return getattr(self, 'user_role', None) == 'user'

    @property
    def is_user_active(self):
        """User can login, place orders, and receive commissions only when active."""
        st = getattr(self, 'user_status', None) or 'active'
        if st == 'active':
            return True
        return False

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    image_url = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    products = db.relationship('Product', backref='category', lazy='dynamic')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    stock_quantity = db.Column(db.Integer, nullable=True)  # None = unlimited, 0 = out of stock
    sku = db.Column(db.String(50), nullable=True)
    weight = db.Column(db.Float, nullable=True)
    dimensions = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def is_out_of_stock(self):
        return self.stock_quantity == 0

class Address(db.Model):
    """Saved delivery address for a user."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    street_address = db.Column(db.String(255), nullable=False)
    landmark = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(6), nullable=False)
    country = db.Column(db.String(100), default='India')
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('addresses', lazy='dynamic', cascade='all, delete-orphan'))

    def to_shipping_string(self):
        """Format address for order shipping_address field."""
        lines = [self.full_name, self.street_address]
        if self.landmark:
            lines.append(self.landmark)
        lines.append(', '.join(filter(None, [self.city, self.state])) + (f' - {self.pincode}' if self.pincode else ''))
        lines.append(self.country or 'India')
        lines.append(f'Phone: {self.phone}')
        return '\n'.join(lines)

    def to_display_lines(self):
        """For card display."""
        lines = [self.full_name, self.street_address]
        if self.landmark:
            lines.append(self.landmark)
        lines.append(', '.join(filter(None, [self.city, self.state])) + (f' - {self.pincode}' if self.pincode else ''))
        lines.append(f'Phone: {self.phone}')
        return lines

class DeviceToken(db.Model):
    """FCM device tokens for push notifications. One user can have multiple devices."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('device_tokens', lazy='dynamic', cascade='all, delete-orphan'))
    __table_args__ = (db.UniqueConstraint('user_id', 'token', name='uq_user_token'),)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, default=1)
    shipping_address = db.Column(db.String(500), nullable=True)
    shipment_notes = db.Column(db.String(500), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), default='Pending')  # Pending, Processing, Shipped, Delivered, Cancelled
    payment_status = db.Column(db.String(20), default='Pending')  # Pending, Paid - commission only when Paid
    razorpay_order_id = db.Column(db.String(64), nullable=True)
    commission_generated = db.Column(db.Boolean, default=False)
    shipped_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='orders')
    product = db.relationship('Product', backref='orders')

class Wallet(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_earnings = db.Column(db.Float, default=0)
    available_balance = db.Column(db.Float, default=0)
    withdrawn_balance = db.Column(db.Float, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('wallet', uselist=False))

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50), nullable=True)  # user, product, order
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    admin = db.relationship('User', backref='activity_logs')

class Notification(db.Model):
    """Log of admin-sent notifications (push/email)."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    audience_type = db.Column(db.String(50), nullable=False)  # all, specific, with_orders, without_orders, by_level
    target_level = db.Column(db.Integer, nullable=True)  # when audience_type=by_level
    delivery_methods = db.Column(db.String(50), nullable=False)  # push, email, push+email
    recipient_count = db.Column(db.Integer, default=0)
    sent_by_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_by = db.relationship('User', backref='sent_notifications')

class Commission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    commission_amount = db.Column(db.Float, nullable=False)
    commission_percent = db.Column(db.Float, nullable=True)
    commission_level = db.Column(db.Integer, nullable=False)  # 1-10 in upline chain
    commission_level_name = db.Column(db.String(80), nullable=True)  # e.g. Sales Executive
    status = db.Column(db.String(20), default='active')  # active, reversed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='commissions')
    order = db.relationship('Order', backref='commissions')

def log_activity(admin_id, action, target_type=None, target_id=None, details=None):
    """Record admin activity for audit trail."""
    db.session.add(ActivityLog(admin_id=admin_id, action=action, target_type=target_type, target_id=target_id, details=details))

def require_super_admin(f):
    """Decorator: require super_admin role. Admin cannot access."""
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        u = User.query.get(session['user_id'])
        if not u or not u.is_super_admin:
            flash('Super Admin access required.', 'error')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return wrapped

class PromotionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    from_level = db.Column(db.Integer, nullable=False)
    to_level = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='promotion_history')

class SavingsAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    current_points = db.Column(db.Integer, default=0)
    lifetime_points = db.Column(db.Integer, default=0)
    eligible_since = db.Column(db.DateTime, nullable=True)
    reward_status = db.Column(db.String(20), default='NORMAL')
    eligibility_email_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    customer = db.relationship('User', backref=db.backref('savings_account', uselist=False))

class SavingsRedemption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    points_redeemed = db.Column(db.Integer, nullable=False)
    reward_name = db.Column(db.String(255), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer = db.relationship('User', foreign_keys=[customer_id], backref='savings_redemptions')
    admin = db.relationship('User', foreign_keys=[admin_id], backref='processed_redemptions')

def count_direct_at_level(user, level):
    """Count direct sales-user children who have the given level."""
    if level is None:
        return 0
    return sum(1 for c in user.children if getattr(c, 'user_role', None) == 'user' and c.user_level == level)

def check_and_promote_user(user_id):
    """Promote if sales user has 10 direct referrals at their current level. Skip admin/super_admin."""
    user = User.query.get(user_id)
    if not user or not user.is_sales_user or not user.user_level or user.user_level >= 10:
        return False
    direct_same_level = count_direct_at_level(user, user.user_level)
    if direct_same_level >= hierarchy_config.PROMOTION_DIRECT_COUNT:
        from_lvl = user.user_level
        user.user_level = min(10, user.user_level + 1)
        db.session.add(PromotionHistory(user_id=user.id, from_level=from_lvl, to_level=user.user_level))
        db.session.commit()
        return True
    return False

def get_or_create_wallet(user_id):
    """Get or create wallet for user."""
    w = Wallet.query.filter_by(user_id=user_id).first()
    if not w:
        w = Wallet(user_id=user_id)
        db.session.add(w)
    return w

def get_or_create_savings_account(customer_id):
    """Get or create savings account for retail customer."""
    sa = SavingsAccount.query.filter_by(customer_id=customer_id).first()
    if not sa:
        sa = SavingsAccount(customer_id=customer_id)
        db.session.add(sa)
    return sa

def distribute_commission(order):
    """Sponsor-based commission: buyer gets 0. Level 1=sponsor, Level 2=sponsor's upline, etc.
    Skip inactive uplines. Only when payment_status=Paid and commission_generated=false."""
    if getattr(order, 'payment_status', None) != 'Paid':
        return
    if getattr(order, 'commission_generated', False):
        return  # Prevent duplicate
    buyer = order.user
    if not buyer.is_sales_user:
        return
    if not buyer.is_user_active:
        return  # Inactive buyer cannot place orders (safety check)
    chain = buyer.get_commission_upline_chain(10)
    if not chain:
        order.commission_generated = True
        db.session.commit()
        return  # No sponsor - no commission
    amount = order.amount * (order.quantity or 1)
    for i, upline_user in enumerate(chain[:10]):
        level = i + 1
        pct = hierarchy_config.COMMISSION_BY_LEVEL.get(level, 0)
        if pct <= 0:
            continue
        level_name = next((n for l, n in hierarchy_config.LEVELS if l == level), '')
        comm_amount = round(amount * (pct / 100), 2)
        comm = Commission(user_id=upline_user.id, order_id=order.id, commission_amount=comm_amount,
            commission_percent=pct, commission_level=level, commission_level_name=level_name, status='active')
        db.session.add(comm)
        w = get_or_create_wallet(upline_user.id)
        w.total_earnings = (w.total_earnings or 0) + comm_amount
        w.available_balance = (w.available_balance or 0) + comm_amount
    order.commission_generated = True
    db.session.commit()

def reverse_commission(order):
    """Reverse commissions when order is cancelled."""
    if not getattr(order, 'commission_generated', False):
        return
    for comm in Commission.query.filter_by(order_id=order.id, status='active').all():
        comm.status = 'reversed'
        w = Wallet.query.filter_by(user_id=comm.user_id).first()
        if w:
            w.available_balance = max(0, (w.available_balance or 0) - comm.commission_amount)
            w.total_earnings = max(0, (w.total_earnings or 0) - comm.commission_amount)
    order.commission_generated = False
    db.session.commit()

def _clear_order_commissions(order):
    """Remove commission records for an order and adjust wallets. Used before recalculating."""
    for comm in Commission.query.filter_by(order_id=order.id, status='active').all():
        w = Wallet.query.filter_by(user_id=comm.user_id).first()
        if w:
            w.available_balance = max(0, (w.available_balance or 0) - comm.commission_amount)
            w.total_earnings = max(0, (w.total_earnings or 0) - comm.commission_amount)
        db.session.delete(comm)
    order.commission_generated = False

def recalculate_commissions_for_orders(orders):
    """Clear existing commissions and re-run distribution for given orders (Paid only)."""
    paid_orders = [o for o in orders if getattr(o, 'payment_status', None) == 'Paid']
    for order in paid_orders:
        if getattr(order, 'commission_generated', False):
            _clear_order_commissions(order)
    if paid_orders:
        db.session.commit()
    for order in paid_orders:
        distribute_commission(order)

# Before request: block inactive sales users from accessing app
@app.before_request
def check_user_active():
    if 'user_id' not in session or request.endpoint in (None, 'logout', 'login'):
        return
    user = User.query.get(session.get('user_id'))
    if user and user.is_sales_user and not user.is_user_active:
        session.clear()
        flash('Your account is inactive. Please contact administrator.', 'error')
        return redirect(url_for('login'))

# PWA routes (served at root for correct scope)
@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(app.static_folder, 'manifest.json', mimetype='application/manifest+json')

@app.route('/service-worker.js')
def pwa_service_worker():
    """Serve combined service worker (caching + FCM when configured)."""
    firebase_enabled = bool(app.config.get('FIREBASE_API_KEY') and app.config.get('FIREBASE_VAPID_KEY'))
    if firebase_enabled:
        config = {
            'apiKey': app.config.get('FIREBASE_API_KEY', ''),
            'projectId': app.config.get('FIREBASE_PROJECT_ID', ''),
            'appId': app.config.get('FIREBASE_APP_ID', ''),
            'messagingSenderId': app.config.get('FIREBASE_MESSAGING_SENDER_ID', ''),
            'storageBucket': app.config.get('FIREBASE_PROJECT_ID', '') + '.appspot.com',
            'authDomain': app.config.get('FIREBASE_PROJECT_ID', '') + '.firebaseapp.com',
        }
        icon_url = request.url_root.rstrip('/') + '/static/images/icon-192.png'
        from flask import Response
        return Response(
            render_template('service_worker.js', firebase_enabled=True, firebase_config=config, icon_url=icon_url),
            mimetype='application/javascript'
        )
    return send_from_directory(app.static_folder, 'service-worker.js', mimetype='application/javascript')

@app.route('/downloads/abound-ehub.apk')
def download_apk():
    """Serve APK with Content-Disposition: attachment to force download (not direct install)."""
    return send_from_directory(
        app.static_folder,
        'downloads/abound-ehub.apk',
        mimetype='application/vnd.android.package-archive',
        as_attachment=True,
        download_name='abound-ehub.apk'
    )

@app.route('/offline')
def pwa_offline():
    return render_template('offline.html', logo_url=get_logo_url())

def get_active_categories_with_counts():
    return (db.session.query(Category, func.count(Product.id).label('product_count'))
        .outerjoin(Product, Product.category_id == Category.id)
        .filter(or_(Category.is_active == True, Category.is_active.is_(None)))
        .group_by(Category.id)
        .order_by(Category.name)
        .all())

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    products = Product.query.limit(8).all()
    categories = get_active_categories_with_counts()
    return render_template('index.html', products=products, categories=categories)

@app.route('/catalog')
def catalog():
    """Public product catalog - redirect to /products when logged in for sidebar layout."""
    if 'user_id' in session:
        return redirect(url_for('products'))
    category_id = request.args.get('category_id', type=int)
    q = Product.query
    selected_category = None
    if category_id:
        selected_category = Category.query.get(category_id)
        if selected_category:
            q = q.filter(Product.category_id == category_id)
    products = q.all()
    categories = get_active_categories_with_counts()
    return render_template('catalog.html', products=products, categories=categories, selected_category=selected_category)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/about/director-message')
def director_message():
    return render_template('director_message.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not all([name, email, subject, message]):
            flash('Please fill in all fields.', 'error')
            return render_template('contact.html')
        if send_contact_form_email(name, email, subject, message):
            flash('Thank you for contacting us. We will get back to you shortly.', 'success')
        else:
            flash('Sorry, we could not send your message. Please try emailing us directly.', 'error')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/profile')
def profile():
    """My Profile - redirect to dashboard if logged in, else login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/faq')
def faq():
    return render_template('faq.html')

def require_admin(f):
    """Decorator: require admin or super_admin role."""
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        u = User.query.get(session['user_id'])
        if not u or not u.is_admin_role:
            flash('You are not authorized as Admin', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def require_super_admin(f):
    """Decorator: require super_admin role."""
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in.', 'error')
            return redirect(url_for('login'))
        u = User.query.get(session['user_id'])
        if not u or not u.is_super_admin:
            flash('Super Admin access required', 'error')
            return redirect(url_for('admin_dashboard'))
        return f(*args, **kwargs)
    return wrapped

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip()
        password = request.form.get('password')
        admin_login = request.form.get('submit_type') == 'admin'
        
        user = None
        if '@' in login_input:
            user = User.query.filter_by(email=login_input).first()
        else:
            user = User.query.filter_by(username=login_input).first()
        if not user:
            user = User.query.filter_by(email=login_input).first()
        
        if not user or not user.check_password(password):
            flash('Invalid credentials', 'error')
            return render_template('login.html')
        if not user.is_user_active:
            flash('Your account is inactive. Please contact administrator.', 'error')
            return render_template('login.html')
        
        if admin_login:
            if not user.is_admin_role:
                flash('You are not authorized as Admin', 'error')
                return render_template('login.html')
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_role'] = user.user_role
            session['user_level'] = user.user_level
            session['level_name'] = user.level_name
            session['referral_id'] = user.referral_id or ''
            session['is_admin'] = True
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        
        session['user_id'] = user.id
        session['username'] = user.username
        session['user_role'] = getattr(user, 'user_role', None) or 'user'
        session['user_level'] = user.user_level
        session['level_name'] = user.level_name
        session['referral_id'] = user.referral_id or ''
        session['is_admin'] = user.is_admin_role
        flash('Login successful!', 'success')
        if user.is_admin_role:
            return redirect(url_for('admin_dashboard'))  # Admin/super_admin go to admin panel
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if user.user_role == 'customer':
        return redirect(url_for('customer_dashboard'))  # Customers go to customer dashboard
    if user.is_admin_role:
        return redirect(url_for('admin_dashboard'))  # Admin/super_admin: admin-only view
    
    team_count = len(user.get_all_descendants())
    direct_count = user.get_team_count()
    wallet = get_or_create_wallet(user.id)
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).limit(20).all()
    has_push_token = DeviceToken.query.filter_by(user_id=user.id).count() > 0
    
    # Get my customers
    my_customers = User.query.filter_by(assigned_member_id=user.id, user_role='customer').all()
    # Add last_purchase and total_purchases to each customer
    for customer in my_customers:
        customer_orders = Order.query.filter_by(user_id=customer.id).order_by(Order.created_at.desc()).all()
        customer.total_purchases = len(customer_orders)
        customer.last_purchase = customer_orders[0].created_at if customer_orders else None
    
    return render_template('dashboard.html', user=user, team_count=team_count,
        direct_count=direct_count, wallet=wallet, orders=orders, has_push_token=has_push_token,
        levels=hierarchy_config.LEVELS, commission_by_level=hierarchy_config.COMMISSION_BY_LEVEL,
        my_customers=my_customers)

@app.route('/products')
def products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user and user.is_admin_role:
        return redirect(url_for('admin_dashboard'))
    
    user = User.query.get(session['user_id'])
    products = Product.query.all()
    return render_template('products.html', products=products, user=user)

@app.route('/checkout')
def checkout():
    """Checkout page: product summary, user info, shipping form."""
    if 'user_id' not in session:
        flash('Please log in to checkout.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or user.is_admin_role:
        return redirect(url_for('admin_dashboard'))
    product_id = request.args.get('productId', type=int) or request.args.get('product_id', type=int)
    qty = request.args.get('qty', type=int) or request.args.get('quantity', type=int) or 1
    if not product_id:
        flash('Please select a product.', 'error')
        return redirect(url_for('products'))
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))
    if product.is_out_of_stock:
        flash('Product is out of stock.', 'error')
        return redirect(url_for('products'))
    qty = max(1, min(qty, 99))
    addresses = Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    default_addr = next((a for a in addresses if a.is_default), addresses[0] if addresses else None)
    return render_template('checkout.html', product=product, quantity=qty, user=user,
        addresses=addresses, default_address_id=default_addr.id if default_addr else None,
        razorpay_key_id=app.config.get('RAZORPAY_KEY_ID', ''))

def _checkout_user_or_error():
    """Return (user, None) or (None, flask_response)."""
    if 'user_id' not in session:
        return None, (jsonify({'error': 'Not authenticated'}), 401)
    user = User.query.get(session['user_id'])
    if not user or not user.is_sales_user:
        return None, (jsonify({'error': 'Only sales users can place orders.'}), 403)
    if not user.is_user_active:
        return None, (jsonify({'error': 'Your account is inactive.'}), 403)
    return user, None

def _parse_checkout_shipping(user, product_id, quantity):
    """Build shipping fields from current request.form. Returns (fields, error_message)."""
    selected_address_id = request.form.get('selected_address_id', type=int)
    shipping_address = request.form.get('shipping_address', '').strip() or None
    phone = request.form.get('addr_phone', '').strip() or user.phone or ''
    if selected_address_id:
        addr = Address.query.filter_by(id=selected_address_id, user_id=user.id).first()
        if addr:
            shipping_address = addr.to_shipping_string()
            phone = addr.phone
    elif not shipping_address:
        parts = []
        name = request.form.get('addr_full_name', '').strip()
        street = request.form.get('addr_street', '').strip()
        landmark = request.form.get('addr_landmark', '').strip()
        city = request.form.get('addr_city', '').strip()
        state = request.form.get('addr_state', '').strip()
        pincode = request.form.get('addr_pincode', '').strip()
        country = request.form.get('addr_country', 'India').strip() or 'India'
        phone = request.form.get('addr_phone', '').strip() or user.phone or ''
        if name:
            parts.append(name)
        if street:
            parts.append(street)
        if landmark:
            parts.append(landmark)
        if city or state or pincode:
            parts.append(', '.join(filter(None, [city, state])) + (f' - {pincode}' if pincode else ''))
        if country:
            parts.append(country)
        if phone:
            parts.append(f'Phone: {phone}')
        shipping_address = '\n'.join(parts) if parts else None
    shipment_notes = request.form.get('shipment_notes', '').strip() or None
    if not shipping_address:
        return None, 'Shipping address is required. Please fill all address fields.'
    pincode = request.form.get('addr_pincode', '').strip()
    if pincode and not (len(pincode) == 6 and pincode.isdigit()):
        return None, 'Please enter a valid 6-digit PIN code.'
    return {
        'quantity': quantity,
        'shipping_address': shipping_address,
        'phone': phone or None,
        'shipment_notes': shipment_notes,
        'selected_address_id': selected_address_id,
    }, None

def _maybe_save_checkout_address(user, selected_address_id, form_data=None):
    """Save manual address from checkout form when requested."""
    form = form_data if form_data is not None else request.form
    if selected_address_id or form.get('save_address') not in ('true', 'on', '1'):
        return False
    name = (form.get('addr_full_name') or '').strip()
    street = (form.get('addr_street') or '').strip()
    landmark = (form.get('addr_landmark') or '').strip()
    city = (form.get('addr_city') or '').strip()
    state = (form.get('addr_state') or '').strip()
    pincode = (form.get('addr_pincode') or '').strip()
    country = (form.get('addr_country') or 'India').strip() or 'India'
    addr_phone = (form.get('addr_phone') or '').strip() or user.phone or ''
    if not (name and street and city and state and len(pincode) == 6 and pincode.isdigit()
            and len(addr_phone) == 10 and addr_phone.isdigit()):
        return False
    existing = Address.query.filter_by(
        user_id=user.id,
        street_address=street,
        city=city,
        state=state,
        pincode=pincode,
        phone=addr_phone,
    ).first()
    if existing:
        return False
    new_addr = Address(
        user_id=user.id,
        full_name=name,
        phone=addr_phone,
        street_address=street,
        landmark=landmark or None,
        city=city,
        state=state,
        pincode=pincode,
        country=country,
        is_default=False,
    )
    db.session.add(new_addr)
    db.session.commit()
    return True

@app.route('/api/checkout/prepare-pending', methods=['POST'])
def checkout_prepare_pending():
    """Create a pending app order before opening Razorpay checkout."""
    user, err = _checkout_user_or_error()
    if err:
        return err
    product_id = request.form.get('product_id', type=int)
    if not product_id:
        return jsonify({'error': 'product_id is required'}), 400
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    if product.is_out_of_stock:
        return jsonify({'error': 'Product is out of stock.'}), 400
    quantity = request.form.get('quantity', 1, type=int) or 1
    quantity = max(1, min(quantity, 99))
    fields, msg = _parse_checkout_shipping(user, product_id, quantity)
    if msg:
        return jsonify({'error': msg}), 400
    amount_paise = int(round(product.price * quantity * 100))
    if amount_paise < 100:
        return jsonify({'error': 'Amount must be at least ₹1.00 (100 paise).'}), 400
    order = Order(
        user_id=user.id,
        product_id=product.id,
        amount=product.price,
        quantity=quantity,
        shipping_address=fields['shipping_address'],
        shipment_notes=fields['shipment_notes'],
        phone=fields['phone'],
        payment_status='Pending',
    )
    db.session.add(order)
    db.session.commit()
    session['pending_checkout_form'] = dict(request.form)
    return jsonify({
        'app_order_id': order.id,
        'amount_paise': amount_paise,
        'receipt': f'order_{order.id}',
        'product_name': product.name,
    })

@app.route('/api/create-order', methods=['POST'])
def api_create_order():
    """Create a Razorpay order (amount in paise)."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    key_id = app.config.get('RAZORPAY_KEY_ID', '')
    key_secret = app.config.get('RAZORPAY_KEY_SECRET', '')
    if not key_id or not key_secret:
        return jsonify({'error': 'Razorpay is not configured'}), 500
    data = request.get_json(silent=True) or {}
    amount = data.get('amount')
    currency = (data.get('currency') or 'INR').strip().upper()
    receipt = (data.get('receipt') or '').strip()
    if amount is None:
        return jsonify({'error': 'amount is required'}), 400
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return jsonify({'error': 'amount must be an integer (paise)'}), 400
    if amount < 100:
        return jsonify({'error': 'amount must be at least 100 paise'}), 400
    if not receipt:
        return jsonify({'error': 'receipt is required'}), 400
    if receipt.startswith('order_'):
        try:
            app_order_id = int(receipt.split('_', 1)[1])
            order = Order.query.get(app_order_id)
            if not order or order.user_id != session['user_id'] or order.payment_status != 'Pending':
                return jsonify({'error': 'Invalid order'}), 400
        except ValueError:
            return jsonify({'error': 'Invalid receipt'}), 400
    try:
        from integrations.razorpay_checkout import create_razorpay_order, get_razorpay_client
        client = get_razorpay_client(key_id, key_secret)
        rzp_order = create_razorpay_order(client, amount, currency, receipt)
    except Exception as e:
        app.logger.error(f'Razorpay create order failed: {e}')
        err_text = str(e)
        if '401' in err_text or 'Authentication' in err_text:
            return jsonify({'error': 'Razorpay authentication failed'}), 401
        return jsonify({'error': 'Failed to create payment order'}), 500
    if receipt.startswith('order_'):
        try:
            app_order_id = int(receipt.split('_', 1)[1])
            order = Order.query.get(app_order_id)
            if order and order.user_id == session['user_id']:
                order.razorpay_order_id = rzp_order.get('id')
                db.session.commit()
        except ValueError:
            pass
    return jsonify({
        'order_id': rzp_order.get('id'),
        'amount': rzp_order.get('amount', amount),
        'currency': rzp_order.get('currency', currency),
    })

@app.route('/api/verify-payment', methods=['POST'])
def api_verify_payment():
    """Verify Razorpay payment signature and mark the app order as paid."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated', 'success': False}), 401
    data = request.get_json(silent=True) or {}
    payment_id = (data.get('razorpay_payment_id') or '').strip()
    rzp_order_id = (data.get('razorpay_order_id') or '').strip()
    signature = (data.get('razorpay_signature') or '').strip()
    app_order_id = data.get('app_order_id')
    if not payment_id or not rzp_order_id or not signature:
        return jsonify({'error': 'Missing payment verification fields', 'success': False}), 400
    key_secret = app.config.get('RAZORPAY_KEY_SECRET', '')
    if not key_secret:
        return jsonify({'error': 'Razorpay is not configured', 'success': False}), 500
    from integrations.razorpay_checkout import verify_payment_signature
    if not verify_payment_signature(key_secret, rzp_order_id, payment_id, signature):
        return jsonify({'error': 'Invalid payment signature', 'success': False}), 400
    if not app_order_id:
        return jsonify({'success': True, 'verified': True})
    order = Order.query.get(int(app_order_id))
    if not order or order.user_id != session['user_id']:
        return jsonify({'error': 'Order not found', 'success': False}), 404
    if order.payment_status == 'Paid':
        return jsonify({'success': True, 'app_order_id': order.id})
    if order.payment_status != 'Pending':
        return jsonify({'error': 'Order is not payable', 'success': False}), 400
    if order.razorpay_order_id and order.razorpay_order_id != rzp_order_id:
        return jsonify({'error': 'Payment order mismatch', 'success': False}), 400
    product = order.product
    if product.is_out_of_stock:
        return jsonify({'error': 'Product is out of stock', 'success': False}), 400
    order.payment_status = 'Paid'
    order.razorpay_order_id = rzp_order_id
    decrement_tracked_stock(product, order.quantity)
    db.session.commit()
    distribute_commission(order)
    send_order_notification(order)
    send_order_confirmation_buyer(order)
    send_push_notification(
        order.user_id,
        'Order Placed',
        f'Your order #{order.id} has been placed successfully.',
        f'/orders/{order.id}',
    )
    address_saved = False
    pending_form = session.pop('pending_checkout_form', None)
    if pending_form:
        sel_raw = pending_form.get('selected_address_id')
        sel_id = None
        if sel_raw not in (None, '', 'None'):
            try:
                sel_id = int(sel_raw)
            except (TypeError, ValueError):
                sel_id = None
        address_saved = _maybe_save_checkout_address(order.user, sel_id, pending_form)
    return jsonify({
        'success': True,
        'app_order_id': order.id,
        'address_saved': address_saved,
    })

@app.route('/place-order/<int:product_id>', methods=['POST'])
def place_order(product_id):
    """Create order from checkout form and redirect to order-success."""
    if 'user_id' not in session:
        flash('Please log in to place order.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_sales_user:
        flash('Only sales users can place orders.', 'error')
        return redirect(url_for('products'))
    if not user.is_user_active:
        flash('Your account is inactive.', 'error')
        return redirect(url_for('login'))
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('products'))
    if product.is_out_of_stock:
        flash('Product is out of stock.', 'error')
        return redirect(url_for('products'))
    quantity = request.form.get('quantity', 1, type=int) or 1
    selected_address_id = request.form.get('selected_address_id', type=int)
    shipping_address = request.form.get('shipping_address', '').strip() or None
    # Prefer selected saved address
    phone = request.form.get('addr_phone', '').strip() or user.phone or ''
    if selected_address_id:
        addr = Address.query.filter_by(id=selected_address_id, user_id=user.id).first()
        if addr:
            shipping_address = addr.to_shipping_string()
            phone = addr.phone
    # Else if not from hidden (JS), build from structured fields
    elif not shipping_address:
        parts = []
        name = request.form.get('addr_full_name', '').strip()
        street = request.form.get('addr_street', '').strip()
        landmark = request.form.get('addr_landmark', '').strip()
        city = request.form.get('addr_city', '').strip()
        state = request.form.get('addr_state', '').strip()
        pincode = request.form.get('addr_pincode', '').strip()
        country = request.form.get('addr_country', 'India').strip() or 'India'
        phone = request.form.get('addr_phone', '').strip() or user.phone or ''
        if name:
            parts.append(name)
        if street:
            parts.append(street)
        if landmark:
            parts.append(landmark)
        if city or state or pincode:
            parts.append(', '.join(filter(None, [city, state])) + (f' - {pincode}' if pincode else ''))
        if country:
            parts.append(country)
        if phone:
            parts.append(f'Phone: {phone}')
        shipping_address = '\n'.join(parts) if parts else None
    shipment_notes = request.form.get('shipment_notes', '').strip() or None
    if not shipping_address:
        flash('Shipping address is required. Please fill all address fields.', 'error')
        return redirect(url_for('checkout', productId=product_id, qty=quantity))
    pincode = request.form.get('addr_pincode', '').strip()
    if pincode and not (len(pincode) == 6 and pincode.isdigit()):
        flash('Please enter a valid 6-digit PIN code.', 'error')
        return redirect(url_for('checkout', productId=product_id, qty=quantity))
    order = Order(
        user_id=user.id, product_id=product.id, amount=product.price, quantity=quantity,
        shipping_address=shipping_address, shipment_notes=shipment_notes, phone=phone or None,
        payment_status='Paid'
    )
    db.session.add(order)
    decrement_tracked_stock(product, quantity)
    db.session.commit()

    # Save address if checkbox selected and using manual address (not saved address)
    address_saved = False
    if not selected_address_id and request.form.get('save_address') in ('true', 'on', '1'):
        name = request.form.get('addr_full_name', '').strip()
        street = request.form.get('addr_street', '').strip()
        landmark = request.form.get('addr_landmark', '').strip()
        city = request.form.get('addr_city', '').strip()
        state = request.form.get('addr_state', '').strip()
        pincode = request.form.get('addr_pincode', '').strip()
        country = request.form.get('addr_country', 'India').strip() or 'India'
        addr_phone = request.form.get('addr_phone', '').strip() or user.phone or ''
        if name and street and city and state and len(pincode) == 6 and pincode.isdigit() and len(addr_phone) == 10 and addr_phone.isdigit():
            existing = Address.query.filter_by(
                user_id=user.id,
                street_address=street,
                city=city,
                state=state,
                pincode=pincode,
                phone=addr_phone
            ).first()
            if not existing:
                new_addr = Address(
                    user_id=user.id,
                    full_name=name,
                    phone=addr_phone,
                    street_address=street,
                    landmark=landmark or None,
                    city=city,
                    state=state,
                    pincode=pincode,
                    country=country,
                    is_default=False
                )
                db.session.add(new_addr)
                db.session.commit()
                address_saved = True

    distribute_commission(order)
    send_order_notification(order)
    send_order_confirmation_buyer(order)
    send_push_notification(order.user_id, 'Order Placed', f'Your order #{order.id} has been placed successfully.', f'/orders/{order.id}')
    flash('Your order has been placed successfully.', 'success')
    if address_saved:
        flash('Your delivery address has been saved to your address book.', 'success')
    return redirect(url_for('order_success') + '?order_id=' + str(order.id))

@app.route('/orders/<int:order_id>')
def order_detail_redirect(order_id):
    """Redirect to order confirmation (used by push notification click_action)."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('order_success', order_id=order_id))

@app.route('/order-success')
def order_success():
    """Order confirmation page after successful purchase."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    order_id = request.args.get('order_id', type=int)
    order = Order.query.get(order_id) if order_id else None
    if order and order.user_id != session.get('user_id'):
        order = None
    return render_template('order_success.html', order=order)

@app.route('/retail-checkout')
def retail_checkout():
    """Retail checkout page (no login required)."""
    product_id = request.args.get('product_id', type=int)
    qty = request.args.get('qty', type=int) or 1
    if not product_id:
        flash('Please select a product.', 'error')
        return redirect(url_for('catalog'))
    product = Product.query.get(product_id)
    if not product:
        flash('Product not found.', 'error')
        return redirect(url_for('catalog'))
    if product.is_out_of_stock:
        flash('Product is out of stock.', 'error')
        return redirect(url_for('catalog'))
    qty = max(1, min(qty, 99))
    # Get all active sales members for the dropdown
    sales_members = User.query.filter_by(user_role='user', user_status='active').order_by(User.full_name).all()
    return render_template('retail_checkout.html', product=product, quantity=qty, sales_members=sales_members,
        razorpay_key_id=app.config.get('RAZORPAY_KEY_ID', ''))

@app.route('/api/retail-checkout/prepare-pending', methods=['POST'])
def retail_checkout_prepare_pending():
    """Prepare pending order for retail checkout (no login required)."""
    # First, get the customer info and selected sales member
    product_id = request.form.get('product_id', type=int)
    if not product_id:
        return jsonify({'error': 'product_id is required'}), 400
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    if product.is_out_of_stock:
        return jsonify({'error': 'Product is out of stock.'}), 400
    quantity = request.form.get('quantity', 1, type=int) or 1
    quantity = max(1, min(quantity, 99))
    
    # Get customer details
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    shipping_address = request.form.get('shipping_address', '').strip()
    assigned_member_id = request.form.get('assigned_member_id', type=int)
    
    if not all([full_name, phone, email, shipping_address, assigned_member_id]):
        return jsonify({'error': 'Please fill all fields'}), 400
    
    # Validate assigned member is an active sales user
    assigned_member = User.query.filter_by(id=assigned_member_id, user_role='user', user_status='active').first()
    if not assigned_member:
        return jsonify({'error': 'Invalid sales member selected'}), 400
    
    # Create a temporary order or just store the data in session for now? Wait, we need to create an order but without a user yet?
    # Wait, let's create a pending order but we need to assign user later. Wait no, let's first store all the data in session, then after payment, create the customer/order.
    # Wait, let's store the checkout data in session, create a pending order (maybe with a temporary user? Or wait, let's create the order after payment is verified.)
    # Alternatively, let's store all the checkout info in session, then in verify-payment, we process it. Let's do that.
    session['retail_checkout_data'] = {
        'product_id': product_id,
        'quantity': quantity,
        'full_name': full_name,
        'phone': phone,
        'email': email,
        'shipping_address': shipping_address,
        'assigned_member_id': assigned_member_id
    }
    
    amount_paise = int(round(product.price * quantity * 100))
    if amount_paise < 100:
        return jsonify({'error': 'Amount must be at least ₹1.00 (100 paise).'}), 400
    
    return jsonify({
        'amount_paise': amount_paise,
        'receipt': f'retail_{int(datetime.utcnow().timestamp())}',
        'product_name': product.name
    })

@app.route('/api/retail-checkout/verify-payment', methods=['POST'])
def retail_checkout_verify_payment():
    """Verify Razorpay payment for retail checkout, create customer account, order, and savings points."""
    data = request.get_json(silent=True) or {}
    payment_id = (data.get('razorpay_payment_id') or '').strip()
    razorpay_order_id = (data.get('razorpay_order_id') or '').strip()
    signature = (data.get('razorpay_signature') or '').strip()
    
    if not all([payment_id, razorpay_order_id, signature]):
        return jsonify({'error': 'Missing payment verification fields', 'success': False}), 400
    
    # Verify Razorpay signature
    key_secret = app.config.get('RAZORPAY_KEY_SECRET', '')
    if not key_secret:
        return jsonify({'error': 'Razorpay is not configured', 'success': False}), 500
    
    from integrations.razorpay_checkout import verify_payment_signature
    if not verify_payment_signature(key_secret, razorpay_order_id, payment_id, signature):
        return jsonify({'error': 'Invalid payment signature', 'success': False}), 400
    
    # Get retail checkout data from session
    retail_data = session.pop('retail_checkout_data', None)
    if not retail_data:
        return jsonify({'error': 'Checkout session expired. Please try again.', 'success': False}), 400
    
    # Get product and check stock
    product = Product.query.get(retail_data['product_id'])
    if not product or product.is_out_of_stock:
        return jsonify({'error': 'Product is no longer available.', 'success': False}), 400
    
    # Find or create customer account
    customer = User.query.filter_by(email=retail_data['email']).first()
    if not customer:
        # Try to find by phone
        customer = User.query.filter_by(phone=retail_data['phone']).first()
    
    if customer:
        # Update customer details if needed?
        customer.full_name = retail_data['full_name']
        customer.phone = retail_data['phone']
        # If customer already has an assigned member, don't change it?
        if not customer.assigned_member_id:
            customer.assigned_member_id = retail_data['assigned_member_id']
    else:
        # Create new customer account
        # Generate a unique username
        username_base = retail_data['email'].split('@')[0].replace('.', '_').replace('+', '_')
        username = username_base
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{username_base}{counter}"
            counter += 1
        
        # Generate a random password
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(12))
        
        customer = User(
            username=username,
            email=retail_data['email'],
            password_hash=generate_password_hash(password),
            full_name=retail_data['full_name'],
            phone=retail_data['phone'],
            user_role='customer',
            assigned_member_id=retail_data['assigned_member_id'],
            user_level=0,
            is_active=True
        )
        db.session.add(customer)
        db.session.flush()  # To get customer.id
        
        # Send credentials email
        send_credentials_email(customer, password)
    
    # Create order
    order = Order(
        user_id=customer.id,
        product_id=product.id,
        amount=product.price,
        quantity=retail_data['quantity'],
        shipping_address=retail_data['shipping_address'],
        phone=retail_data['phone'],
        payment_status='Paid'
    )
    db.session.add(order)
    
    # Update stock
    decrement_tracked_stock(product, order.quantity)
    
    # Calculate and add savings points
    savings_account = get_or_create_savings_account(customer.id)
    order_total = product.price * order.quantity
    points_earned = int(round(order_total * SAVINGS_POINT_RATE))
    savings_account.current_points += points_earned
    savings_account.lifetime_points += points_earned
    
    # Check if customer is eligible for reward
    if savings_account.current_points >= REWARD_THRESHOLD and savings_account.reward_status == 'NORMAL' and not savings_account.eligibility_email_sent:
        savings_account.reward_status = 'ELIGIBLE'
        savings_account.eligible_since = datetime.utcnow()
        savings_account.eligibility_email_sent = True
        # Send email to all admins
        admins = User.query.filter(User.user_role.in_(['admin', 'super_admin'])).all()
        if admins:
            try:
                assigned_member = User.query.get(customer.assigned_member_id)
                body = f"""
Customer Eligible for Reward!

Customer: {customer.full_name}
Email: {customer.email}
Phone: {customer.phone}
Current Points: {savings_account.current_points}
Assigned Sales Member: {assigned_member.full_name if assigned_member else 'N/A'}
                """.strip()
                send_email(
                    to=[a.email for a in admins],
                    subject='Customer Eligible for Reward - Abound Next-Gen E-Hub',
                    html=f"<pre>{body}</pre>"
                )
            except Exception as e:
                app.logger.error(f"Failed to send eligibility email: {e}")
    
    db.session.commit()
    
    # Send order notifications
    send_order_notification(order)
    # Check if customer email works for order confirmation
    try:
        send_order_confirmation_buyer(order)
    except Exception as e:
        app.logger.error(f"Failed to send order confirmation to customer: {e}")
    
    return jsonify({
        'success': True,
        'order_id': order.id
    })

@app.route('/customer-dashboard')
def customer_dashboard():
    """Customer dashboard (requires login)."""
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('login'))
    if user.user_role != 'customer':
        # Redirect sales users and admins to their respective dashboards
        if user.is_admin_role:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('dashboard'))
    # Get savings account
    savings_account = get_or_create_savings_account(user.id)
    # Get orders
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    # Get assigned member
    assigned_member = User.query.get(user.assigned_member_id)
    return render_template('customer_dashboard.html', user=user, savings_account=savings_account,
        orders=orders, assigned_member=assigned_member)

@app.route('/admin/customer-rewards')
@require_admin
def admin_customer_rewards():
    """Admin page to manage customer rewards."""
    # Get all customers with savings accounts
    customers = User.query.filter_by(user_role='customer').all()
    for customer in customers:
        customer.savings_account = get_or_create_savings_account(customer.id)
        customer.assigned_member = User.query.get(customer.assigned_member_id)
    return render_template('admin/customer_rewards.html', customers=customers)

@app.route('/admin/customer/<int:customer_id>/mark-gift-delivered', methods=['POST'])
@require_admin
def admin_mark_gift_delivered(customer_id):
    """Mark a customer's gift as delivered, reset current points, create redemption record."""
    admin_user = User.query.get(session['user_id'])
    customer = User.query.get_or_404(customer_id)
    if customer.user_role != 'customer':
        flash('Only customers can have gift rewards.', 'error')
        return redirect(url_for('admin_customer_rewards'))
    savings_account = get_or_create_savings_account(customer.id)
    if savings_account.reward_status != 'ELIGIBLE' and savings_account.reward_status != 'PENDING':
        flash('Customer is not eligible for a gift.', 'error')
        return redirect(url_for('admin_customer_rewards'))
    # Get reward name/description from form
    reward_name = request.form.get('reward_name', 'Gift')
    remarks = request.form.get('remarks', '')
    # Create redemption record
    redemption = SavingsRedemption(
        customer_id=customer.id,
        points_redeemed=savings_account.current_points,
        reward_name=reward_name,
        admin_id=admin_user.id,
        remarks=remarks
    )
    db.session.add(redemption)
    # Reset current points
    savings_account.current_points = 0
    savings_account.reward_status = 'DELIVERED'
    db.session.commit()
    log_activity(admin_user.id, f'Marked gift delivered for customer {customer.full_name}', 'customer', customer.id)
    flash('Gift marked as delivered!', 'success')
    return redirect(url_for('admin_customer_rewards'))

@app.route('/order/<int:product_id>', methods=['POST'])
def create_order(product_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_sales_user:
        return jsonify({'success': False, 'message': 'Only sales users can place orders.'}), 403
    if not user.is_user_active:
        return jsonify({'success': False, 'message': 'Your account is inactive. Please contact administrator.'}), 403
    product = Product.query.get(product_id)
    if not product:
        return jsonify({'success': False, 'message': 'Product not found'}), 404
    if product.is_out_of_stock:
        return jsonify({'success': False, 'message': 'Product is out of stock.'}), 400
    quantity = request.form.get('quantity', request.json.get('quantity') if request.is_json else 1, type=int) or 1
    shipping_address = request.form.get('shipping_address') or request.json.get('shipping_address', '') if request.is_json else request.form.get('shipping_address', '')
    phone = request.form.get('phone') or request.json.get('phone', '') if request.is_json else request.form.get('phone', '')
    if not shipping_address:
        shipping_address = user.address or ''
    if not phone:
        phone = user.phone or ''
    order = Order(user_id=user.id, product_id=product.id, amount=product.price, quantity=quantity,
        shipping_address=shipping_address or None, phone=phone or None, payment_status='Paid')
    db.session.add(order)
    decrement_tracked_stock(product, quantity)
    db.session.commit()
    distribute_commission(order)
    send_order_notification(order)
    send_order_confirmation_buyer(order)
    send_push_notification(order.user_id, 'Order Placed', f'Your order #{order.id} has been placed successfully.', f'/orders/{order.id}')
    return jsonify({'success': True, 'message': f'Order placed. Commission distributed.'})

def _validate_address_form(data):
    """Validate address form data. Returns (ok, error_msg)."""
    name = (data.get('full_name') or '').strip()
    phone = (data.get('phone') or '').strip()
    street = (data.get('street_address') or '').strip()
    city = (data.get('city') or '').strip()
    state = (data.get('state') or '').strip()
    pincode = (data.get('pincode') or '').strip()
    if not name:
        return False, 'Full name is required.'
    if not phone:
        return False, 'Phone number is required.'
    if not (len(phone) == 10 and phone.isdigit()):
        return False, 'Please enter a valid 10-digit phone number.'
    if not street:
        return False, 'Street address is required.'
    if not city:
        return False, 'City is required.'
    if not state:
        return False, 'State is required.'
    if not (len(pincode) == 6 and pincode.isdigit()):
        return False, 'Please enter a valid 6-digit PIN code.'
    return True, None

@app.route('/profile/addresses')
def profile_addresses():
    """View and manage saved addresses."""
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    addresses = Address.query.filter_by(user_id=user.id).order_by(Address.is_default.desc(), Address.created_at.desc()).all()
    return render_template('profile_addresses.html', addresses=addresses)

@app.route('/profile/addresses/add', methods=['GET', 'POST'])
def profile_address_add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        data = request.form
        ok, err = _validate_address_form(data)
        if not ok:
            flash(err, 'error')
            return render_template('address_form.html', address=None, form_data=request.form, is_edit=False)
        addr = Address(
            user_id=user.id,
            full_name=(data.get('full_name') or '').strip(),
            phone=(data.get('phone') or '').strip(),
            street_address=(data.get('street_address') or '').strip(),
            landmark=(data.get('landmark') or '').strip() or None,
            city=(data.get('city') or '').strip(),
            state=(data.get('state') or '').strip(),
            pincode=(data.get('pincode') or '').strip(),
            country=(data.get('country') or 'India').strip() or 'India',
            is_default=Address.query.filter_by(user_id=user.id).count() == 0
        )
        db.session.add(addr)
        db.session.commit()
        flash('Address added successfully.', 'success')
        return redirect(url_for('profile_addresses'))
    return render_template('address_form.html', address=None, form_data=None, is_edit=False)

@app.route('/profile/addresses/<int:addr_id>/edit', methods=['GET', 'POST'])
def profile_address_edit(addr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    addr = Address.query.filter_by(id=addr_id, user_id=user.id).first_or_404()
    if request.method == 'POST':
        data = request.form
        ok, err = _validate_address_form(data)
        if not ok:
            flash(err, 'error')
            return render_template('address_form.html', address=addr, form_data=request.form if request.form else None, is_edit=True)
        addr.full_name = (data.get('full_name') or '').strip()
        addr.phone = (data.get('phone') or '').strip()
        addr.street_address = (data.get('street_address') or '').strip()
        addr.landmark = (data.get('landmark') or '').strip() or None
        addr.city = (data.get('city') or '').strip()
        addr.state = (data.get('state') or '').strip()
        addr.pincode = (data.get('pincode') or '').strip()
        addr.country = (data.get('country') or 'India').strip() or 'India'
        db.session.commit()
        flash('Address updated successfully.', 'success')
        return redirect(url_for('profile_addresses'))
    return render_template('address_form.html', address=addr, form_data=None, is_edit=True)

@app.route('/profile/addresses/<int:addr_id>/delete', methods=['POST'])
def profile_address_delete(addr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    addr = Address.query.filter_by(id=addr_id, user_id=user.id).first_or_404()
    was_default = addr.is_default
    db.session.delete(addr)
    if was_default:
        first = Address.query.filter_by(user_id=user.id).first()
        if first:
            first.is_default = True
    db.session.commit()
    flash('Address deleted.', 'success')
    return redirect(url_for('profile_addresses'))

@app.route('/api/addresses', methods=['POST'])
def api_address_create():
    """Create address via AJAX (for checkout modal). Returns JSON."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 401
    data = request.get_json() or {}
    # Support form data too
    if not data and request.form:
        data = {k: v for k, v in request.form.items()}
    ok, err = _validate_address_form(data)
    if not ok:
        return jsonify({'success': False, 'error': err}), 400
    is_first = Address.query.filter_by(user_id=user.id).count() == 0
    addr = Address(
        user_id=user.id,
        full_name=(data.get('full_name') or '').strip(),
        phone=(data.get('phone') or '').strip(),
        street_address=(data.get('street_address') or '').strip(),
        landmark=(data.get('landmark') or '').strip() or None,
        city=(data.get('city') or '').strip(),
        state=(data.get('state') or '').strip(),
        pincode=(data.get('pincode') or '').strip(),
        country=(data.get('country') or 'India').strip() or 'India',
        is_default=is_first
    )
    db.session.add(addr)
    db.session.commit()
    return jsonify({
        'success': True,
        'address': {
            'id': addr.id,
            'full_name': addr.full_name,
            'phone': addr.phone,
            'street_address': addr.street_address,
            'landmark': addr.landmark or '',
            'city': addr.city,
            'state': addr.state,
            'pincode': addr.pincode,
            'country': addr.country or 'India',
            'is_default': addr.is_default,
            'shipping_string': addr.to_shipping_string(),
            'display_lines': addr.to_display_lines()
        }
    })

@app.route('/api/save-device-token', methods=['POST'])
def api_save_device_token():
    """Store FCM device token for the logged-in user. Prevents duplicates."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user_id = session['user_id']
    data = request.get_json() or request.form or {}
    token = (data.get('device_token') or data.get('token') or '').strip()
    if not token:
        return jsonify({'success': False, 'message': 'Device token is required'}), 400
    existing = DeviceToken.query.filter_by(user_id=user_id, token=token).first()
    if existing:
        return jsonify({'success': True, 'message': 'Token already registered'})
    dt = DeviceToken(user_id=user_id, token=token)
    db.session.add(dt)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Device token saved'})

@app.route('/api/remove-device-token', methods=['POST'])
def api_remove_device_token():
    """Remove FCM device token when user disables notifications. Accepts token or remove_all=1."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    user_id = session['user_id']
    data = request.get_json() or request.form or {}
    if data.get('remove_all'):
        DeviceToken.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'All device tokens removed'})
    token = (data.get('device_token') or data.get('token') or '').strip()
    if not token:
        return jsonify({'success': False, 'message': 'Device token is required, or pass remove_all=1'}), 400
    DeviceToken.query.filter_by(user_id=user_id, token=token).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Device token removed'})

@app.route('/api/firebase-config')
def api_firebase_config():
    """Return Firebase web config for frontend (safe to expose)."""
    return jsonify({
        'apiKey': app.config.get('FIREBASE_API_KEY', ''),
        'projectId': app.config.get('FIREBASE_PROJECT_ID', ''),
        'appId': app.config.get('FIREBASE_APP_ID', ''),
        'messagingSenderId': app.config.get('FIREBASE_MESSAGING_SENDER_ID', ''),
        'storageBucket': app.config.get('FIREBASE_PROJECT_ID', '') + '.appspot.com',
        'authDomain': app.config.get('FIREBASE_PROJECT_ID', '') + '.firebaseapp.com',
        'vapidKey': app.config.get('FIREBASE_VAPID_KEY', '')
    })


@app.route('/profile/notifications')
def profile_notifications():
    """Notification settings: enable/disable push notifications."""
    if 'user_id' not in session:
        flash('Please log in.', 'error')
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    has_token = DeviceToken.query.filter_by(user_id=user.id).count() > 0
    return render_template('profile_notifications.html', has_token=has_token)

@app.route('/profile/addresses/<int:addr_id>/set-default', methods=['POST'])
def profile_address_set_default(addr_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    addr = Address.query.filter_by(id=addr_id, user_id=user.id).first_or_404()
    for a in Address.query.filter_by(user_id=user.id).all():
        a.is_default = (a.id == addr_id)
    db.session.commit()
    flash('Default address updated.', 'success')
    return redirect(url_for('profile_addresses'))

@app.route('/my-commissions')
def my_commissions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if not user or user.is_admin_role:
        return redirect(url_for('admin_dashboard'))
    commissions = Commission.query.filter_by(user_id=user.id).order_by(Commission.created_at.desc()).all()
    return render_template('my_commissions.html', commissions=commissions)

@app.route('/my-team')
def my_team():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if user and user.is_admin_role:
        return redirect(url_for('admin_dashboard'))

    # Upline: sponsor and above (sales users only)
    upline = []
    current = user.parent
    while current:
        if getattr(current, 'user_role', None) == 'user':
            upline.append(current)
        current = current.parent

    # Peers: others with same sponsor (siblings)
    peers = []
    if user.parent_id:
        peers = User.query.filter(
            User.parent_id == user.parent_id,
            User.id != user.id,
            User.user_role == 'user'
        ).order_by(User.created_at).all()

    # Downline: direct referrals
    downline = user.get_direct_referrals()
    team_count = len(user.get_all_descendants())
    direct_count = user.get_team_count()

    return render_template('my_team.html', user=user, upline=upline, peers=peers,
        team_members=downline, team_count=team_count, direct_count=direct_count)

@app.route('/onboard', methods=['POST'])
def onboard():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    parent_user = User.query.get(session['user_id'])
    if not parent_user or not parent_user.is_sales_user:
        return jsonify({'success': False, 'message': 'Only sales users can onboard team members.'}), 403
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    full_name = request.form.get('full_name')
    referral_id = request.form.get('referral_id', '').strip().upper()
    
    # If valid referral ID provided, use that user as parent instead
    if referral_id:
        referrer = User.query.filter_by(referral_id=referral_id, user_role='user').first()
        if referrer:
            parent_user = referrer
    
    # Check if username or email already exists
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400
    
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already exists'}), 400
    
    ref_id = generate_referral_id()
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        full_name=full_name,
        parent_id=parent_user.id,
        user_level=1,
        user_role='user',
        referral_id=ref_id
    )
    
    db.session.add(new_user)
    db.session.commit()
    get_or_create_wallet(new_user.id)
    email_sent = send_welcome_email(new_user)
    
    # Check promotion up the chain (parent, then grandparent, etc.)
    promoted_user = None
    current = parent_user
    while current:
        if check_and_promote_user(current.id):
            db.session.refresh(current)
            promoted_user = current
        current = current.parent
    
    if promoted_user and promoted_user.id == parent_user.id:
        session['user_level'] = parent_user.user_level
        session['level_name'] = parent_user.level_name
        msg = f'Agent onboarded successfully! You have been promoted to {parent_user.level_name}!'
        if email_sent:
            msg += ' A welcome email has been sent to the new agent.'
        return jsonify({
            'success': True,
            'message': msg,
            'promoted': True,
            'new_position': parent_user.level_name
        })
    
    msg = 'Agent onboarded successfully!'
    if email_sent:
        msg += ' A welcome email has been sent to the new agent.'
    return jsonify({'success': True, 'message': msg, 'promoted': False})

@app.route('/api/team-stats')
def team_stats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_sales_user:
        return jsonify({'error': 'Sales users only'}), 403
    
    direct_count = count_direct_at_level(user, user.user_level)
    next_level = None
    if user.user_level and user.user_level < 10:
        next_level = {
            'name': hierarchy_config.LEVELS[user.user_level][1],
            'required': hierarchy_config.PROMOTION_DIRECT_COUNT,
            'remaining': max(0, hierarchy_config.PROMOTION_DIRECT_COUNT - direct_count)
        }
    
    return jsonify({
        'team_count': len(user.get_all_descendants()),
        'direct_count': user.get_team_count(),
        'direct_at_level': direct_count,
        'current_level': user.level_name,
        'next_level': next_level
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Public registration - supports ?ref=REFERRAL_ID to join under referrer."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    ref_id = request.args.get('ref', '').strip().upper()
    referrer = User.query.filter_by(referral_id=ref_id, user_role='user').first() if ref_id else None
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        ref_input = request.form.get('referral_id', ref_id).strip().upper()
        
        parent = User.query.filter_by(referral_id=ref_input, user_role='user').first() if ref_input else referrer
        if not parent:
            flash('Invalid referral ID. Please get a valid link from your referrer.', 'error')
            return render_template('register.html', referral_id=ref_id, referrer=referrer)
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('register.html', referral_id=ref_id, referrer=referrer)
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('register.html', referral_id=ref_id, referrer=referrer)
        
        new_ref_id = generate_referral_id()
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password),
            full_name=full_name, parent_id=parent.id, user_level=1, user_role='user', referral_id=new_ref_id)
        db.session.add(new_user)
        db.session.commit()
        get_or_create_wallet(new_user.id)
        email_sent = send_welcome_email(new_user)
        current = parent
        while current:
            check_and_promote_user(current.id)
            current = current.parent
        
        if email_sent:
            flash('Registration successful! Check your email for your account details and Referral ID. Please login.', 'success')
        else:
            flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', referral_id=ref_id, referrer=referrer)

# Admin route to create initial admin user
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.count() > 0:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        admin = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            user_level=0,
            parent_id=None,
            referral_id=None,
            is_admin=True,
            user_role='admin'
        )
        
        db.session.add(admin)
        db.session.commit()
        
        send_welcome_email(admin)
        
        flash('Admin user created! Please login. Check your email for your Referral ID.', 'success')
        return redirect(url_for('login'))
    
    return render_template('setup.html')

@app.route('/test-send-welcome-email')
def test_send_welcome_email_redirect():
    return redirect(url_for('email_test'))

@app.route('/email-test', methods=['GET', 'POST'])
@app.route('/admin-email-test', methods=['GET', 'POST'])
def email_test():
    """Troubleshoot email: shows config status and sends test with full error display."""
    if 'user_id' not in session:
        flash('Please log in to test email.', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    config_ok = bool(os.environ.get('RESEND_API_KEY'))
    
    if request.method == 'POST':
        error_msg = None
        success = False
        try:
            if not config_ok:
                error_msg = 'Email not configured. Add RESEND_API_KEY to your .env file.'
            else:
                body = render_template('email_welcome.html',
                    full_name=user.full_name,
                    username=user.username,
                    referral_id=user.referral_id or '',
                    app_url=app.config['APP_URL']
                )
                success = send_email(
                    to=user.email,
                    subject='Welcome to Abound Next-Gen E-Hub - Your Account Details',
                    html=body,
                )
                if not success:
                    error_msg = 'Resend email failed. Check application logs for the provider response.'
        except Exception as e:
            error_msg = f'{type(e).__name__}: {e}'
        
        return render_template('email_test.html',
            user=user,
            config_ok=config_ok,
            mail_server=app.config['MAIL_SERVER'],
            mail_port=app.config['MAIL_PORT'],
            mail_username=app.config['MAIL_USERNAME'],
            success=success,
            error_msg=error_msg
        )
    
    return render_template('email_test.html',
        user=user,
        config_ok=config_ok,
        mail_server=app.config['MAIL_SERVER'],
        mail_port=app.config['MAIL_PORT'],
        mail_username=app.config['MAIL_USERNAME'],
        success=None,
        error_msg=None
    )

def migrate_db():
    """Migrate schema and backfill data."""
    db.create_all()
    # Add new columns if missing (SQLite)
    user_cols = [('user_level', 'INTEGER DEFAULT 1'), ('is_admin', 'INTEGER DEFAULT 0'), ('user_role', "VARCHAR(20) DEFAULT 'user'"),
        ('phone', 'VARCHAR(20)'), ('address', 'VARCHAR(255)'), ('user_status', "VARCHAR(20) DEFAULT 'active'"),
        ('assigned_member_id', 'INTEGER')]
    for col, def_sql in user_cols:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"SELECT {col} FROM user LIMIT 1"))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {def_sql}"))
            except Exception:
                pass
    # Add new columns to savings_account if missing
    savings_account_cols = [('eligibility_email_sent', 'INTEGER DEFAULT 0')]
    for col, def_sql in savings_account_cols:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"SELECT {col} FROM savings_account LIMIT 1"))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE savings_account ADD COLUMN {col} {def_sql}"))
            except Exception:
                pass
    for col, def_sql in [('image_url', 'VARCHAR(255)'), ('is_active', 'INTEGER DEFAULT 1')]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"SELECT {col} FROM category LIMIT 1"))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE category ADD COLUMN {col} {def_sql}"))
            except Exception:
                pass
    for col, def_sql in [('category_id', 'INTEGER'), ('stock_quantity', 'INTEGER'), ('sku', 'VARCHAR(50)'), ('weight', 'REAL'), ('dimensions', 'VARCHAR(100)')]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text(f"SELECT {col} FROM product LIMIT 1"))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE product ADD COLUMN {col} {def_sql}"))
            except Exception:
                pass
    for col, def_sql in [('quantity', 'INTEGER DEFAULT 1'), ('shipping_address', 'VARCHAR(500)'), ('shipment_notes', 'VARCHAR(500)'), ('phone', 'VARCHAR(20)'), ('status', "VARCHAR(20) DEFAULT 'Pending'"),
            ('payment_status', "VARCHAR(20) DEFAULT 'Pending'"), ('commission_generated', 'INTEGER DEFAULT 0'), ('shipped_at', 'DATETIME'),
            ('razorpay_order_id', 'VARCHAR(64)')]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text('SELECT {} FROM "order" LIMIT 1'.format(col)))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE "order" ADD COLUMN {} {}'.format(col, def_sql)))
            except Exception:
                pass
    for col, def_sql in [('commission_percent', 'REAL'), ('commission_level_name', 'VARCHAR(80)'), ('status', "VARCHAR(20) DEFAULT 'active'")]:
        try:
            with db.engine.connect() as conn:
                conn.execute(text('SELECT {} FROM commission LIMIT 1'.format(col)))
        except Exception:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text('ALTER TABLE commission ADD COLUMN {} {}'.format(col, def_sql)))
            except Exception:
                pass
    # Create Super Admin if not exists (distinct username to avoid setup conflicts)
    SUPER_ADMIN_EMAIL = 'chayanc50@gmail.com'
    SUPER_ADMIN_USERNAME = 'SUP_ADMIN_ABOUND'
    SUPER_ADMIN_PASSWORD = 'Wellington@123'
    super_admin = User.query.filter_by(email=SUPER_ADMIN_EMAIL).first()
    if not super_admin:
        super_admin = User.query.filter_by(username=SUPER_ADMIN_USERNAME).first()
    if not super_admin:
        super_admin = User(
            username=SUPER_ADMIN_USERNAME,
            email=SUPER_ADMIN_EMAIL,
            password_hash=generate_password_hash(SUPER_ADMIN_PASSWORD),
            full_name='Super Admin',
            user_level=0,
            parent_id=None,
            user_role='super_admin',
            referral_id=None,
            is_admin=True,
            is_active=True
        )
        db.session.add(super_admin)
    else:
        if getattr(super_admin, 'user_role', None) != 'super_admin':
            super_admin.user_role = 'super_admin'
        super_admin.user_level = 0
        super_admin.parent_id = None
        super_admin.referral_id = None
        super_admin.username = SUPER_ADMIN_USERNAME
        super_admin.password_hash = generate_password_hash(SUPER_ADMIN_PASSWORD)
    # Backfill: user_level from position, referral_id (sales users only), ensure roles
    level_map = {'Sales Agent': 1, 'Team Leader': 2, 'Senior Team Leader': 3, 'Manager': 4, 'Senior Manager': 5}
    for user in User.query.all():
        if getattr(user, 'user_status', None) in (None, ''):
            user.user_status = 'inactive' if not getattr(user, 'is_active', True) else 'active'
        r = getattr(user, 'user_role', None)
        if r is None or str(r).strip() == '':
            user.user_role = 'super_admin' if user.email == SUPER_ADMIN_EMAIL else ('admin' if getattr(user, 'is_admin', False) else 'user')
        if user.user_role in ('admin', 'super_admin'):
            user.user_level = 0
            user.referral_id = None
            user.parent_id = None
        else:
            if getattr(user, 'user_level', None) in (None, 0):
                user.user_level = level_map.get(user.position, 1) if user.position else 1
            if user.referral_id is None:
                user.referral_id = generate_referral_id()
        if user.parent_id:
            parent = User.query.get(user.parent_id)
            if parent and getattr(parent, 'user_role', None) in ('admin', 'super_admin'):
                user.parent_id = None  # Orphan from admin - not in pyramid
    if Category.query.count() == 0:
        for name in ['Grocery', 'Cosmetics', 'Household', 'Personal Care']:
            db.session.add(Category(name=name))
    # Backfill: payment_status/commission_generated for existing orders; create wallets for sales users
    for order in Order.query.all():
        if getattr(order, 'commission_generated', None) is None:
            order.commission_generated = bool(order.commissions)  # True if has commission records
        if getattr(order, 'payment_status', None) in (None, '') and order.commission_generated:
            order.payment_status = 'Paid'
    for u in User.query.filter_by(user_role='user').all():
        w = get_or_create_wallet(u.id)
        if (w.total_earnings or 0) == 0:
            total = sum(c.commission_amount for c in u.commissions if getattr(c, 'status', 'active') != 'reversed')
            if total > 0:
                w.total_earnings = total
                w.available_balance = total
    db.session.commit()

def has_sales_users():
    return User.query.filter(User.user_role == 'user').count() > 0

@app.route('/admin')
@app.route('/admin-dashboard')
@require_admin
def admin_dashboard():
    user = User.query.get(session['user_id'])
    if user.is_super_admin:
        total_users = User.query.count()
        orders = Order.query.all()
        total_sales = sum(o.amount * (o.quantity or 1) for o in orders)
        total_commissions = sum(c.commission_amount for c in Commission.query.all())
        total_orders = Order.query.count()
        users = User.query.order_by(User.created_at.desc()).limit(50).all()
        return render_template('admin/super_admin_dashboard.html', users=users,
            total_users=total_users, total_sales=total_sales, total_commissions=total_commissions, total_orders=total_orders,
            can_create_first_sales=not has_sales_users())
    else:
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='Pending').count()
        total_products = Product.query.count()
        low_stock = sum(1 for p in Product.query.all() if getattr(p, 'stock_quantity', None) is not None and p.stock_quantity <= 5 and p.stock_quantity > 0)
        return render_template('admin/admin_dashboard.html',
            total_orders=total_orders, pending_orders=pending_orders, total_products=total_products, low_stock=low_stock)

@app.route('/admin/create-first-sales-user', methods=['GET', 'POST'])
@require_admin
def create_first_sales_user():
    admin_user = User.query.get(session['user_id'])
    if not admin_user.is_super_admin:
        flash('Only Super Admin can create the first sales user.', 'error')
        return redirect(url_for('admin_dashboard'))
    if has_sales_users():
        flash('Sales users already exist. Use registration or onboarding to add more.', 'info')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        full_name = request.form.get('full_name', '').strip()
        if not all([username, email, password, full_name]):
            flash('All fields are required.', 'error')
            return render_template('admin/create_first_sales.html')
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return render_template('admin/create_first_sales.html')
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return render_template('admin/create_first_sales.html')
        
        ref_id = generate_referral_id()
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
            parent_id=None,
            user_level=1,
            user_role='user',
            referral_id=ref_id
        )
        db.session.add(new_user)
        db.session.commit()
        get_or_create_wallet(new_user.id)
        send_welcome_email(new_user)
        flash(f'First sales user created! Referral ID: {ref_id}', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/create_first_sales.html')

@app.route('/admin/users')
@app.route('/admin-users')
@require_super_admin
def admin_users():
    q = User.query
    search = request.args.get('search', '').strip()
    if search:
        q = q.filter(or_(User.full_name.ilike(f'%{search}%'), User.email.ilike(f'%{search}%'), User.referral_id.ilike(f'%{search}%')))
    users = q.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, search=search)

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@require_super_admin
def admin_user(user_id):
    admin_user = User.query.get(session['user_id'])
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'reset_password':
            pw = request.form.get('new_password')
            if pw:
                user.password_hash = generate_password_hash(pw)
                db.session.commit()
                log_activity(admin_user.id, f'Reset password for user: {user.full_name}', 'user', user.id)
                flash('Password reset', 'success')
        elif action == 'update':
            user.full_name = request.form.get('full_name', user.full_name)
            user.email = request.form.get('email', user.email)
            user.phone = request.form.get('phone') or None
            user.address = request.form.get('address') or None
            user_status = request.form.get('user_status', 'active')
            if user_status in ('active', 'inactive', 'suspended'):
                user.user_status = user_status
                user.is_active = (user_status == 'active')
            if user.is_sales_user:
                lvl = request.form.get('user_level', type=int)
                if lvl and 1 <= lvl <= 10:
                    user.user_level = lvl
            ref = request.form.get('referral_id', '').strip().upper()
            if ref and user.is_sales_user:
                existing = User.query.filter_by(referral_id=ref).first()
                if not existing or existing.id == user.id:
                    user.referral_id = ref
            db.session.commit()
            log_activity(admin_user.id, f'Updated user: {user.full_name}', 'user', user.id)
            flash('User updated', 'success')
    commissions = user.commissions
    total_comm = sum(c.commission_amount for c in commissions)
    return render_template('admin/user_detail.html', user=user, commissions=commissions, total_comm=total_comm, config=hierarchy_config)

@app.route('/admin/user/create', methods=['GET', 'POST'])
@app.route('/admin-create-user', methods=['GET', 'POST'])
@require_super_admin
def admin_user_create():
    admin_user = User.query.get(session['user_id'])
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        phone = request.form.get('phone') or None
        address = request.form.get('address') or None
        role = request.form.get('role', 'user')  # user or admin
        pw_option = request.form.get('password_option')
        password = request.form.get('password') or None
        auto_pw = pw_option == 'auto'
        if auto_pw:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        if not all([full_name, email, username, password]):
            flash('Name, Email, Username and Password required', 'error')
            return redirect(url_for('admin_user_create'))
        if User.query.filter_by(username=username).first():
            flash('Username exists', 'error')
            return redirect(url_for('admin_user_create'))
        if User.query.filter_by(email=email).first():
            flash('Email exists', 'error')
            return redirect(url_for('admin_user_create'))
        if role == 'admin':
            u = User(username=username, email=email, password_hash=generate_password_hash(password),
                full_name=full_name, phone=phone, address=address, user_level=0, referral_id=None,
                parent_id=None, user_role='admin')
        else:
            parent_id = request.form.get('parent_id', type=int)
            ref_id = request.form.get('referral_id', '').strip().upper() or generate_referral_id()
            level = request.form.get('user_level', 1, type=int)
            u = User(username=username, email=email, password_hash=generate_password_hash(password),
                full_name=full_name, phone=phone, address=address, user_level=max(1, min(10, level)),
                referral_id=ref_id, parent_id=parent_id if parent_id else None, user_role='user')
        db.session.add(u)
        db.session.commit()
        if u.user_role == 'user':
            get_or_create_wallet(u.id)
        if auto_pw:
            send_credentials_email(u, password)
        else:
            send_welcome_email(u)
        log_activity(admin_user.id, f'Created user: {u.full_name} (role={role})', 'user', u.id)
        flash(f'User created. {"Credentials emailed." if auto_pw else ""}', 'success')
        return redirect(url_for('admin_users'))
    sales_users = User.query.filter_by(user_role='user').order_by(User.full_name).all()
    return render_template('admin/user_create.html', config=hierarchy_config, sales_users=sales_users)

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@require_super_admin
def admin_delete_user(user_id):
    """Permanently delete a user only if safe (no downline, no promotion impact, not admin/super_admin)."""
    target_user = User.query.get_or_404(user_id)
    
    # RULE 3: System users cannot be deleted
    if getattr(target_user, 'user_role', None) in ('admin', 'super_admin'):
        return jsonify({'status': 'error', 'message': 'Admin accounts cannot be deleted.'}), 400
    
    # RULE 1: User must have no downline
    descendants = target_user.get_all_descendants()
    if descendants:
        return jsonify({'status': 'error', 'message': 'User cannot be deleted because they have downline members.'}), 400
    
    # Extra: Preserve order history - cannot delete users who have placed orders
    order_count = Order.query.filter_by(user_id=target_user.id).count()
    if order_count > 0:
        return jsonify({'status': 'error', 'message': 'User cannot be deleted because they have order history.'}), 400
    
    # RULE 2: Deletion must not break upline promotion requirement
    upline = target_user.parent
    if upline and getattr(upline, 'user_role', None) == 'user':
        current_direct = upline.get_team_count()
        # Promotion requires 10 direct referrals; if upline has exactly 10, deleting breaks qualification
        if current_direct == hierarchy_config.PROMOTION_DIRECT_COUNT:
            return jsonify({
                'status': 'error',
                'message': "Deleting this user would affect the sponsor's promotion qualification."
            }), 400
    
    try:
        name = target_user.full_name
        uid = target_user.id
        # Delete related records first (commission, wallet) to avoid FK issues
        Commission.query.filter_by(user_id=uid).delete()
        Wallet.query.filter_by(user_id=uid).delete()
        PromotionHistory.query.filter_by(user_id=uid).delete()
        db.session.delete(target_user)
        db.session.commit()
        log_activity(session['user_id'], f'Deleted user: {name} (id={uid})', 'user', uid)
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return jsonify({'status': 'success', 'message': 'User deleted successfully.'})

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@require_super_admin
def admin_user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_super_admin:
        flash('Cannot delete Super Admin', 'error')
        return redirect(url_for('admin_users'))
    name = user.full_name

    if getattr(user, 'user_role', None) == 'admin':
        # Admin accounts: permanently delete from database
        ActivityLog.query.filter_by(admin_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        log_activity(session['user_id'], f'Deleted Admin account: {name}', 'user', user_id)
        flash(f'Admin {name} has been deleted', 'success')
    else:
        # Sales users: deactivate (keep record for orders/commissions)
        user.user_status = 'inactive'
        user.is_active = False
        db.session.commit()
        log_activity(session['user_id'], f'Deactivated user: {name}', 'user', user_id)
        flash(f'User {name} deactivated', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/commissions')
@app.route('/admin-commissions')
@require_admin
def admin_commissions():
    user = User.query.get(session['user_id'])
    commissions = Commission.query.filter(Commission.status == 'active').order_by(Commission.created_at.desc()).limit(500).all()
    total_comm = sum(c.commission_amount for c in Commission.query.filter_by(status='active').all())
    per_user = {}
    for c in Commission.query.filter_by(status='active').all():
        per_user[c.user_id] = per_user.get(c.user_id, 0) + c.commission_amount
    commission_summary = [(User.query.get(uid), amt) for uid, amt in per_user.items()]
    return render_template('admin/commissions.html', commissions=commissions,
        is_super_admin=user.is_super_admin, total_comm=total_comm, commission_summary=commission_summary)

@app.route('/admin/wallets')
@app.route('/admin-wallets')
@require_super_admin
def admin_wallets():
    wallets = Wallet.query.join(User).order_by(User.full_name).all()
    return render_template('admin/wallets.html', wallets=wallets)

@app.route('/admin/orders')
@app.route('/admin-orders')
@require_admin
def admin_orders():
    status_filter = request.args.get('status', '').lower()
    q = Order.query
    if status_filter == 'pending':
        q = q.filter(Order.status.in_(['Pending', 'Processing']))
    elif status_filter == 'completed':
        q = q.filter(Order.status.in_(['Shipped', 'Delivered']))
    orders = q.order_by(Order.created_at.desc()).limit(200).all()
    return render_template('admin/orders.html', orders=orders, status_filter=status_filter)

@app.route('/admin/order/<int:order_id>/shipping-slip')
@require_admin
def admin_order_shipping_slip(order_id):
    """Printable shipping slip for an order."""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/shipping_slip.html', order=order)

@app.route('/admin/orders/<int:order_id>/mark-shipped', methods=['POST'])
@require_admin
def admin_order_mark_shipped(order_id):
    """Mark order as Shipped, set shipped_at, send email notifications."""
    order = Order.query.get_or_404(order_id)
    order.status = 'Shipped'
    order.shipped_at = datetime.utcnow()
    db.session.commit()
    log_activity(session['user_id'], f'Order #{order_id} marked as Shipped', 'order', order_id)
    send_order_shipped_buyer(order)
    send_order_shipped_admin(order)
    send_push_notification(order.user_id, 'Your Order Has Been Shipped', f'Order #{order.id} is on the way!', f'/orders/{order.id}')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'status': 'success', 'message': 'Order marked as shipped. Notifications sent.'})
    flash('Order marked as shipped. Buyer and admins notified.', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/order/<int:order_id>/status', methods=['POST'])
@require_admin
def admin_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status in ('Pending', 'Processing', 'Shipped', 'Delivered', 'Cancelled'):
        if new_status == 'Cancelled' and order.commission_generated:
            reverse_commission(order)
        order.status = new_status
        if new_status == 'Shipped' and not order.shipped_at:
            order.shipped_at = datetime.utcnow()
            send_order_shipped_buyer(order)
            send_order_shipped_admin(order)
            send_push_notification(order.user_id, 'Your Order Has Been Shipped', f'Order #{order.id} is on the way!', f'/orders/{order.id}')
        db.session.commit()
        log_activity(session['user_id'], f'Order #{order_id} status changed to {new_status}', 'order', order_id)
        flash(f'Order #{order_id} status updated to {new_status}', 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin-products')
@app.route('/admin-categories')
@require_admin
def admin_products():
    products = Product.query.order_by(Product.name).all()
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/products.html', products=products, categories=categories)

@app.route('/admin-products/category/add', methods=['POST'])
@require_admin
def admin_category_add():
    name = request.form.get('name', '').strip()
    if name:
        is_active = request.form.get('is_active') in ('1', 'on', 'true', 'yes')
        cat = Category(name=name, is_active=is_active)
        img = save_category_image(request.files.get('image'))
        if img:
            cat.image_url = img
        db.session.add(cat)
        db.session.commit()
        log_activity(session['user_id'], f'Created category: {name}', 'category', cat.id)
        flash(f'Category "{name}" created', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin-products/category/<int:cat_id>/edit', methods=['POST'])
@require_admin
def admin_category_edit(cat_id):
    cat = Category.query.get_or_404(cat_id)
    name = request.form.get('name', '').strip()
    if name:
        old = cat.name
        cat.name = name
        log_activity(session['user_id'], f'Category renamed: {old} -> {name}', 'category', cat.id)
    cat.is_active = request.form.get('is_active') in ('1', 'on', 'true', 'yes')
    img = save_category_image(request.files.get('image'))
    if img:
        cat.image_url = img
    db.session.commit()
    flash('Category updated', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin-products/category/<int:cat_id>/delete', methods=['POST'])
@require_admin
def admin_category_delete(cat_id):
    cat = Category.query.get_or_404(cat_id)
    name = cat.name
    for p in cat.products:
        p.category_id = None
    db.session.delete(cat)
    db.session.commit()
    log_activity(session['user_id'], f'Deleted category: {name}', 'category', cat_id)  # cat_id preserved before delete
    flash(f'Category "{name}" deleted', 'success')
    return redirect(url_for('admin_products'))

@app.route('/admin-products/product/add', methods=['GET', 'POST'])
@app.route('/admin-add-product', methods=['GET', 'POST'])
@require_admin
def admin_product_add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price = request.form.get('price', type=float)
        category_id = request.form.get('category_id', type=int)
        description = request.form.get('description', '')
        stock_quantity = request.form.get('stock_quantity', type=int)
        sku = request.form.get('sku', '').strip()
        weight = request.form.get('weight', type=float)
        dimensions = request.form.get('dimensions', '')
        if not name or price is None:
            flash('Name and price required', 'error')
            return redirect(url_for('admin_product_add'))
        img_path = None
        if 'image' in request.files and request.files['image'].filename:
            f = request.files['image']
            if f and f.filename:
                fn = secure_filename(f.filename)
                if fn:
                    ext = fn.rsplit('.', 1)[-1].lower() if '.' in fn else 'jpg'
                    fn = f"product_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{ext}"
                    up_dir = app.config['UPLOAD_FOLDER']
                    os.makedirs(up_dir, exist_ok=True)
                    f.save(os.path.join(up_dir, fn))
                    img_path = f'/static/images/{fn}'
        p = Product(name=name, price=price, description=description or None, image_url=img_path,
            category_id=category_id if category_id else None, stock_quantity=stock_quantity if stock_quantity is not None else None,
            sku=sku or generate_product_sku(), weight=weight if weight else None, dimensions=dimensions or None)
        db.session.add(p)
        db.session.commit()
        log_activity(session['user_id'], f'Created product: {name}', 'product', p.id)
        flash(f'Product "{name}" created', 'success')
        return redirect(url_for('admin_products'))
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/product_form.html', product=None, categories=categories)

@app.route('/admin-products/product/<int:prod_id>/edit', methods=['GET', 'POST'])
@require_admin
def admin_product_edit(prod_id):
    p = Product.query.get_or_404(prod_id)
    if request.method == 'POST':
        p.name = request.form.get('name', '').strip() or p.name
        price = request.form.get('price', type=float)
        if price is not None:
            p.price = price
        p.category_id = request.form.get('category_id', type=int) or None
        p.description = request.form.get('description', '') or None
        p.stock_quantity = request.form.get('stock_quantity', type=int) if request.form.get('stock_quantity') != '' else None
        p.sku = request.form.get('sku', '').strip() or generate_product_sku()
        p.weight = request.form.get('weight', type=float) or None
        p.dimensions = request.form.get('dimensions', '') or None
        if 'image' in request.files and request.files['image'].filename:
            f = request.files['image']
            if f and f.filename:
                fn = secure_filename(f.filename)
                if fn:
                    ext = fn.rsplit('.', 1)[-1].lower() if '.' in fn else 'jpg'
                    fn = f"product_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}.{ext}"
                    up_dir = app.config['UPLOAD_FOLDER']
                    os.makedirs(up_dir, exist_ok=True)
                    f.save(os.path.join(up_dir, fn))
                    p.image_url = f'/static/images/{fn}'
        db.session.commit()
        log_activity(session['user_id'], f'Updated product: {p.name}', 'product', p.id)
        flash('Product updated', 'success')
        return redirect(url_for('admin_products'))
    categories = Category.query.order_by(Category.name).all()
    return render_template('admin/product_form.html', product=p, categories=categories)

@app.route('/admin-products/product/<int:prod_id>/delete', methods=['POST'])
@require_admin
def admin_product_delete(prod_id):
    p = Product.query.get_or_404(prod_id)
    name = p.name
    db.session.delete(p)
    db.session.commit()
    log_activity(session['user_id'], f'Deleted product: {name}', 'product', prod_id)
    flash(f'Product "{name}" deleted', 'success')
    return redirect(url_for('admin_products'))

def scan_tree_integrity():
    """Scan all users for tree integrity issues. Returns list of {user_id, problem_type, suggested_fix}."""
    issues = []
    users = User.query.all()
    user_ids = {u.id for u in users}

    for user in users:
        # 1. Orphan: parent_id references non-existing user
        if user.parent_id is not None:
            if user.parent_id not in user_ids:
                issues.append({
                    'user_id': user.id,
                    'user_name': user.full_name,
                    'problem_type': 'Orphan user',
                    'suggested_fix': 'Set parent_id = NULL',
                    'fix_action': 'orphan'
                })
                continue

        # 2. Circular reference: user in own ancestor chain
        if user.parent_id is not None:
            seen = set()
            current = user.parent
            while current:
                if current.id == user.id:
                    issues.append({
                        'user_id': user.id,
                        'user_name': user.full_name,
                        'problem_type': 'Circular reference',
                        'suggested_fix': 'Set parent_id = NULL to break cycle',
                        'fix_action': 'circular'
                    })
                    break
                if current.id in seen:
                    break
                seen.add(current.id)
                current = current.parent

        # 4. Admin in tree: admin/super_admin should not have parent_id
        if getattr(user, 'user_role', None) in ('admin', 'super_admin') and user.parent_id is not None:
            issues.append({
                'user_id': user.id,
                'user_name': user.full_name,
                'problem_type': 'Admin in referral tree',
                'suggested_fix': 'Set parent_id = NULL',
                'fix_action': 'admin_in_tree'
            })

    # 3. Duplicate referral_id
    from collections import defaultdict
    ref_map = defaultdict(list)
    for user in users:
        if user.referral_id:
            ref_map[user.referral_id].append(user)
    for ref_id, ulist in ref_map.items():
        if len(ulist) > 1:
            for u in ulist:
                issues.append({
                    'user_id': u.id,
                    'user_name': u.full_name,
                    'problem_type': 'Duplicate referral ID',
                    'suggested_fix': 'Generate new referral ID',
                    'fix_action': 'duplicate_ref',
                    'extra': ref_id
                })

    return issues

@app.route('/admin/tree-health')
@require_super_admin
def admin_tree_health():
    issues = scan_tree_integrity()
    return render_template('admin/tree_health.html', issues=issues)

@app.route('/admin/tree-health/fix', methods=['POST'])
@require_super_admin
def admin_tree_health_fix():
    """Apply auto-fix for a single issue."""
    data = request.get_json(silent=True) or {}
    user_id = request.form.get('user_id', type=int) or data.get('user_id')
    fix_action = request.form.get('fix_action') or data.get('fix_action', '')

    if not user_id or not fix_action:
        return jsonify({'status': 'error', 'message': 'Missing user_id or fix_action.'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found.'}), 404

    try:
        if fix_action == 'orphan':
            user.parent_id = None
            db.session.commit()
            log_activity(session['user_id'], f'Tree fix: Set orphan user {user.full_name} (id={user_id}) parent_id to NULL', 'user', user_id)
            return jsonify({'status': 'success', 'message': 'Orphan user fixed. parent_id set to NULL.'})

        if fix_action == 'circular':
            user.parent_id = None
            db.session.commit()
            log_activity(session['user_id'], f'Tree fix: Broke circular reference for user {user.full_name} (id={user_id})', 'user', user_id)
            return jsonify({'status': 'success', 'message': 'Circular reference fixed. parent_id set to NULL.'})

        if fix_action == 'admin_in_tree':
            user.parent_id = None
            db.session.commit()
            log_activity(session['user_id'], f'Tree fix: Removed admin {user.full_name} (id={user_id}) from referral tree', 'user', user_id)
            return jsonify({'status': 'success', 'message': 'Admin removed from tree. parent_id set to NULL.'})

        if fix_action == 'duplicate_ref':
            new_ref = generate_referral_id()
            old_ref = user.referral_id
            user.referral_id = new_ref
            db.session.commit()
            log_activity(session['user_id'], f'Tree fix: Regenerated referral_id for {user.full_name} (id={user_id}): {old_ref} -> {new_ref}', 'user', user_id)
            return jsonify({'status': 'success', 'message': f'New referral ID: {new_ref}'})

        return jsonify({'status': 'error', 'message': 'Unknown fix action.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/recalculate-commission', methods=['GET', 'POST'])
@require_super_admin
def admin_recalculate_commission():
    """Commission recalculation tool: recalc by order, user, or date range."""
    if request.method == 'GET':
        return render_template('admin/recalculate_commission.html')

    mode = request.form.get('mode') or (request.get_json(silent=True) or {}).get('mode')
    order_id = request.form.get('order_id', type=int) or (request.get_json(silent=True) or {}).get('order_id')
    user_id = request.form.get('user_id', type=int) or (request.get_json(silent=True) or {}).get('user_id')
    date_from = request.form.get('date_from') or (request.get_json(silent=True) or {}).get('date_from')
    date_to = request.form.get('date_to') or (request.get_json(silent=True) or {}).get('date_to')

    orders = []
    if mode == 'order' and order_id:
        o = Order.query.get(order_id)
        if o:
            orders = [o]
        else:
            return jsonify({'status': 'error', 'message': 'Order not found.'}), 404
    elif mode == 'user' and user_id:
        orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at).all()
    elif mode == 'date_range' and date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            d_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            if d_from > d_to:
                return jsonify({'status': 'error', 'message': 'Date range invalid: from must be before to.'}), 400
            orders = Order.query.filter(
                db.func.date(Order.created_at) >= d_from,
                db.func.date(Order.created_at) <= d_to
            ).order_by(Order.created_at).all()
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Select a mode and provide required inputs.'}), 400

    paid_orders = [o for o in orders if getattr(o, 'payment_status', None) == 'Paid']
    if not paid_orders:
        return jsonify({'status': 'error', 'message': 'No Paid orders found in selection.'}), 400

    try:
        recalculate_commissions_for_orders(paid_orders)
        order_ids = [o.id for o in paid_orders]
        log_activity(
            session['user_id'],
            f'Commission recalculated: {len(paid_orders)} order(s)',
            'order', order_ids[0] if order_ids else None,
            details=f'orders_affected={",".join(map(str, order_ids))}'
        )
        return jsonify({
            'status': 'success',
            'message': f'Commissions recalculated for {len(paid_orders)} order(s).',
            'orders_affected': len(paid_orders)
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/activity-logs')
@app.route('/admin-activity-logs')
@require_super_admin
def admin_activity_logs():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    return render_template('admin/activity_logs.html', logs=logs)

@app.route('/admin-sales-report')
@app.route('/admin-commission-report')
@require_admin
def admin_report_placeholder():
    name = 'Sales Report' if 'sales' in request.path else 'Commission Report'
    flash(f'{name} - Coming soon', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/api/search-users')
@require_admin
def admin_api_search_users():
    """Search sales users by name, email, referral ID, or id for reassignment dropdowns."""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'users': []})
    qry = User.query.filter(User.user_role == 'user')
    if q.isdigit():
        u = User.query.get(int(q))
        if u and u.user_role == 'user':
            return jsonify({'users': [{'id': u.id, 'full_name': u.full_name, 'email': u.email, 'referral_id': u.referral_id or '', 'level': u.level_name}]})
    if len(q) < 2:
        return jsonify({'users': []})
    users = qry.filter(or_(
        User.full_name.ilike(f'%{q}%'),
        User.email.ilike(f'%{q}%'),
        User.username.ilike(f'%{q}%'),
        User.referral_id.ilike(f'%{q}%')
    )).order_by(User.full_name).limit(20).all()
    return jsonify({
        'users': [
            {'id': u.id, 'full_name': u.full_name, 'email': u.email, 'referral_id': u.referral_id or '', 'level': u.level_name}
            for u in users
        ]
    })

@app.route('/admin/reassign-user', methods=['GET', 'POST'])
@require_admin
def admin_reassign_user():
    """Downline reassignment: move a user to a different sponsor."""
    if request.method == 'GET':
        preset_user_id = request.args.get('user_id', type=int)
        return render_template('admin/reassign_user.html', preset_user_id=preset_user_id)

    # POST - perform reassignment (supports form and JSON)
    data = request.get_json(silent=True) or {}
    user_id = request.form.get('user_id', type=int) or data.get('user_id')
    new_parent_id = request.form.get('new_parent_id', type=int) or data.get('new_parent_id')

    if not user_id or not new_parent_id:
        return jsonify({'status': 'error', 'message': 'User and new sponsor are required.'}), 400

    user = User.query.get(user_id)
    new_parent = User.query.get(new_parent_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found.'}), 404
    if not new_parent:
        return jsonify({'status': 'error', 'message': 'New sponsor not found.'}), 404

    # Rule 3: Cannot reassign root user (parent_id is NULL)
    if user.parent_id is None:
        return jsonify({'status': 'error', 'message': 'Root users cannot be reassigned.'}), 400

    # Rule 4: Prevent self-assignment
    if user.id == new_parent.id:
        return jsonify({'status': 'error', 'message': 'Cannot assign a user as their own sponsor.'}), 400

    # Rule 2: New sponsor cannot be admin or super_admin
    if getattr(new_parent, 'user_role', None) in ('admin', 'super_admin'):
        return jsonify({'status': 'error', 'message': 'Admin users cannot be sponsors.'}), 400

    # Rule 1: Cannot move user under their own descendant
    descendants = user.get_all_descendants()
    descendant_ids = [d.id for d in descendants]
    if new_parent.id in descendant_ids:
        return jsonify({'status': 'error', 'message': 'Cannot assign a user under their own downline.'}), 400

    try:
        old_parent_id = user.parent_id
        user.parent_id = new_parent.id
        db.session.commit()
        log_activity(
            session['user_id'],
            f'Reassigned user: {user.full_name} (user_id={user.id}) from parent {old_parent_id} to {new_parent.id}',
            'user', user.id,
            details=f'old_parent_id={old_parent_id}, new_parent_id={new_parent.id}'
        )
        return jsonify({'status': 'success', 'message': 'User successfully reassigned to new sponsor.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

def _get_notification_recipients(audience_type, target_user_id=None, target_level=None):
    """Get (user_ids, emails) for notification based on audience. Only sales users (user_role='user')."""
    base = User.query.filter(User.user_role == 'user')
    if audience_type == 'all':
        users = base.all()
    elif audience_type == 'specific' and target_user_id:
        u = User.query.filter_by(id=target_user_id, user_role='user').first()
        users = [u] if u else []
    elif audience_type == 'with_orders':
        user_ids = db.session.query(Order.user_id).distinct().all()
        user_ids = [r[0] for r in user_ids]
        users = base.filter(User.id.in_(user_ids)).all()
    elif audience_type == 'without_orders':
        user_ids_with_orders = [r[0] for r in db.session.query(Order.user_id).distinct().all()]
        users = base.filter(~User.id.in_(user_ids_with_orders)).all() if user_ids_with_orders else base.all()
    elif audience_type == 'by_level' and target_level is not None:
        users = base.filter(User.user_level == target_level).all()
    else:
        users = []
    user_ids = [u.id for u in users]
    emails = [u.email for u in users if u.email]
    return user_ids, emails

@app.route('/admin/notifications', methods=['GET', 'POST'])
@require_admin
def admin_notifications():
    """Notification Center: send push and/or email to targeted users."""
    if request.method == 'GET':
        return render_template('admin/notifications.html',
            levels=hierarchy_config.LEVELS,
            commission_by_level=hierarchy_config.COMMISSION_BY_LEVEL,
            app_url=app.config.get('APP_URL', 'http://localhost:5001'))

    try:
        return _admin_notifications_post()
    except Exception as e:
        import traceback
        app.logger.exception('Admin notifications POST failed')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(str(e), 'error')
        return redirect(url_for('admin_notifications'))

def _admin_notifications_post():
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = {k: v for k, v in request.form.items()}

    def _int_or_none(v):
        if v is None or v == '': return None
        try: return int(v)
        except (TypeError, ValueError): return None

    title = (data.get('title') or '').strip()[:60]
    message = (data.get('message') or '').strip()[:150]
    audience_type = (data.get('audience') or data.get('audience_type') or 'all').strip()
    target_user_id = _int_or_none(data.get('target_user_id'))
    target_level = _int_or_none(data.get('target_level'))
    def _truthy(v):
        if v is None: return True
        if isinstance(v, bool): return v
        return str(v).lower() in ('true', '1', 'yes', 'on')
    send_push = _truthy(data.get('send_push', True))
    send_email = _truthy(data.get('send_email', True))
    click_action = (data.get('click_action') or '').strip() or None
    if click_action and not click_action.startswith('/'):
        click_action = '/' + click_action

    if not title or not message:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Title and message are required.'}), 400
        flash('Title and message are required.', 'error')
        return redirect(url_for('admin_notifications'))

    if audience_type == 'specific' and not target_user_id:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please select a user.'}), 400
        flash('Please select a user for Specific User audience.', 'error')
        return redirect(url_for('admin_notifications'))

    if audience_type == 'by_level' and target_level is None:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please select a user level.'}), 400
        flash('Please select a user level.', 'error')
        return redirect(url_for('admin_notifications'))

    if not send_push and not send_email:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Select at least one delivery method.'}), 400
        flash('Select at least one delivery method (Push or Email).', 'error')
        return redirect(url_for('admin_notifications'))

    try:
        user_ids, emails = _get_notification_recipients(audience_type, target_user_id, target_level)
    except Exception as e:
        app.logger.exception('Get notification recipients failed')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': str(e)}), 500
        flash(str(e), 'error')
        return redirect(url_for('admin_notifications'))

    recipient_count = len(user_ids)

    delivery_methods = []
    if send_push:
        delivery_methods.append('push')
    if send_email:
        delivery_methods.append('email')

    try:
        if send_push and user_ids:
            send_push_notification(user_ids, title, message, click_action)
        if send_email and emails:
            for email in emails:
                send_notification_email(email, title, message, click_action)
    except Exception as e:
        app.logger.exception('Send notification failed')
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': f'Send failed: {str(e)}'}), 500
        flash(f'Send failed: {str(e)}', 'error')
        return redirect(url_for('admin_notifications'))

    n = Notification(
        title=title,
        message=message,
        audience_type=audience_type,
        target_level=target_level,
        delivery_methods=','.join(delivery_methods),
        recipient_count=recipient_count,
        sent_by_admin_id=session['user_id']
    )
    db.session.add(n)
    db.session.commit()
    log_activity(session['user_id'], f'Sent notification: {title[:50]} to {recipient_count} users', 'notification', n.id)

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'message': 'Notification sent successfully.',
            'recipient_count': recipient_count
        })
    flash(f'Notification sent successfully. Delivered to {recipient_count} users.', 'success')
    return redirect(url_for('admin_notifications'))

@app.route('/admin/search')
@require_admin
def admin_search():
    ref_id = request.args.get('ref', '').strip().upper()
    user = User.query.filter_by(referral_id=ref_id, user_role='user').first()
    return jsonify({'found': user is not None, 'user': {'id': user.id, 'full_name': user.full_name, 'level': user.level_name, 'team_size': len(user.get_all_descendants())} if user else None})

@app.route('/api/team-tree')
def api_team_tree():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    user = User.query.get(session['user_id'])
    if not user or not user.is_sales_user:
        return jsonify({'error': 'Sales users only'}), 403
    
    def build_tree(u):
        sales_children = [c for c in u.children.limit(100) if getattr(c, 'user_role', None) == 'user']
        return {'id': u.id, 'name': u.full_name, 'level': u.level_name, 'ref_id': u.referral_id or '', 'children': [build_tree(c) for c in sales_children]}
    return jsonify(build_tree(user))

# Initialize database when the application is imported
with app.app_context():
    migrate_db()

    # Create sample products if database is empty
    if Product.query.count() == 0:
        sample_products = [
            Product(
                name='Premium Package A',
                description='Complete sales solution package',
                price=299.99
            ),
            Product(
                name='Premium Package B',
                description='Advanced features package',
                price=499.99
            ),
            Product(
                name='Enterprise Package',
                description='Full enterprise solution',
                price=999.99
            ),
        ]

        db.session.add_all(sample_products)
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
