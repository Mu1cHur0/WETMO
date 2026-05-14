import os, random, hashlib, logging, secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
from flask_cors import CORS
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import pyotp

logging.basicConfig(level=logging.INFO)

os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data: https:; connect-src 'self'"
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "mx1chxr0.team@internet.ru")
SMTP_PASSWORD = "Wc5AZWicRpdwWcP4a2K3"

def send_verification_email(to_email, code):
    try:
        msg = MIMEMultipart()
        msg['From'] = f"WETMO <{SMTP_EMAIL}>"
        msg['To'] = to_email
        msg['Subject'] = "WETMO — Код подтверждения"
        html = f"""
        <div style="background:#17212b;padding:30px;font-family:Arial,sans-serif;">
            <div style="max-width:400px;margin:0 auto;background:#242f3d;border-radius:12px;padding:30px;text-align:center;">
                <h1 style="color:#53fc18;margin-bottom:20px;">WETMO</h1>
                <p style="color:#fff;font-size:16px;">Ваш код подтверждения:</p>
                <div style="background:#1b2836;border-radius:8px;padding:20px;margin:20px 0;">
                    <span style="font-size:32px;font-weight:bold;color:#53fc18;letter-spacing:6px;">{code}</span>
                </div>
                <p style="color:#708499;font-size:12px;">Код действителен 10 минут</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"[EMAIL] Код {code} отправлен на {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

def generate_encryption_key(password: str, salt: bytes = None) -> bytes:
    if salt is None:
        salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

VERIFICATION_TYPES = [
    {"id": 0, "name": "Нет", "icon": "", "color": "transparent", "desc": "Обычный"},
    {"id": 1, "name": "Подтверждён", "icon": "✓", "color": "#e0e0e0", "desc": "Базовый"},
    {"id": 2, "name": "Модератор", "icon": "🛡", "color": "#53fc18", "desc": "Модер"},
    {"id": 3, "name": "Админ", "icon": "⚡", "color": "#ffd700", "desc": "Админ"},
    {"id": 4, "name": "Разработчик", "icon": "💻", "color": "#00d4ff", "desc": "Dev"},
    {"id": 5, "name": "Премиум", "icon": "💎", "color": "#ff00ff", "desc": "Premium"},
    {"id": 6, "name": "Партнёр", "icon": "🤝", "color": "#ff8c00", "desc": "Партнёр"},
    {"id": 7, "name": "Основатель", "icon": "👑", "color": "#ff0000", "desc": "Основатель"},
    {"id": 8, "name": "Легенда", "icon": "⭐", "color": "#ffffff", "desc": "Легенда"}
]

USER_BADGES = [
    {"name": "Основатель", "url": "https://img.icons8.com/ios-filled/50/ffffff/crown.png", "color": "#ffffff"},
    {"name": "Ветеран", "url": "https://img.icons8.com/ios-filled/50/ffffff/shield.png", "color": "#ffffff"},
    {"name": "Блогер", "url": "https://img.icons8.com/ios-filled/50/ffffff/star.png", "color": "#ffffff"},
    {"name": "Модератор", "url": "https://img.icons8.com/ios-filled/50/ffffff/security-checked.png", "color": "#ffffff"},
    {"name": "Разработчик", "url": "https://img.icons8.com/ios-filled/50/ffffff/code.png", "color": "#ffffff"},
    {"name": "Дизайнер", "url": "https://img.icons8.com/ios-filled/50/ffffff/design.png", "color": "#ffffff"},
    {"name": "Тестер", "url": "https://img.icons8.com/ios-filled/50/ffffff/bug.png", "color": "#ffffff"},
    {"name": "Спонсор", "url": "https://img.icons8.com/ios-filled/50/ffffff/diamond.png", "color": "#ffffff"},
    {"name": "Партнёр", "url": "https://img.icons8.com/ios-filled/50/ffffff/handshake.png", "color": "#ffffff"},
    {"name": "Меценат", "url": "https://img.icons8.com/ios-filled/50/ffffff/heart.png", "color": "#ffffff"},
    {"name": "Креатив", "url": "https://img.icons8.com/ios-filled/50/ffffff/idea.png", "color": "#ffffff"},
    {"name": "Гуру", "url": "https://img.icons8.com/ios-filled/50/ffffff/wizard.png", "color": "#ffffff"},
    {"name": "Легенда", "url": "https://img.icons8.com/ios-filled/50/ffffff/trophy.png", "color": "#ffffff"},
    {"name": "Стример", "url": "https://img.icons8.com/ios-filled/50/ffffff/video-call.png", "color": "#ffffff"},
    {"name": "Музыкант", "url": "https://img.icons8.com/ios-filled/50/ffffff/musical-notes.png", "color": "#ffffff"},
    {"name": "Художник", "url": "https://img.icons8.com/ios-filled/50/ffffff/paint-palette.png", "color": "#ffffff"},
    {"name": "Писатель", "url": "https://img.icons8.com/ios-filled/50/ffffff/book.png", "color": "#ffffff"},
    {"name": "Фотограф", "url": "https://img.icons8.com/ios-filled/50/ffffff/camera.png", "color": "#ffffff"},
    {"name": "Путешественник", "url": "https://img.icons8.com/ios-filled/50/ffffff/globe.png", "color": "#ffffff"},
    {"name": "Коллекционер", "url": "https://img.icons8.com/ios-filled/50/ffffff/treasure-chest.png", "color": "#ffffff"}
]

CHANNEL_BADGES = [
    {"name": "Официальный", "url": "https://img.icons8.com/ios-filled/50/ffffff/verified-account.png", "color": "#ffffff"},
    {"name": "Популярный", "url": "https://img.icons8.com/ios-filled/50/ffffff/fire-element.png", "color": "#ffffff"}
]

PREMIUM_COLORS = [
    {"name": "Белый", "colors": ["#ffffff", "#cccccc", "#ffffff", "#cccccc"]},
    {"name": "Неон", "colors": ["#ff00ff", "#00ffff", "#ff00ff", "#00ffff"]},
    {"name": "Зелёный", "colors": ["#53fc18", "#00ff88", "#53fc18", "#00ff88"]},
    {"name": "Огненный", "colors": ["#ff4444", "#ff8800", "#ff4444", "#ff8800"]},
    {"name": "Фиолетовый", "colors": ["#7c3aed", "#3b82f6", "#7c3aed", "#3b82f6"]},
    {"name": "Розовый", "colors": ["#ec4899", "#fbbf24", "#ec4899", "#fbbf24"]},
    {"name": "Морской", "colors": ["#06b6d4", "#10b981", "#06b6d4", "#10b981"]},
    {"name": "Радужный", "colors": ["#ffd700", "#ff00ff", "#00ffff", "#ffd700"]},
    {"name": "Серебро", "colors": ["#c0c0c0", "#e0e0e0", "#c0c0c0", "#e0e0e0"]},
    {"name": "Золотой", "colors": ["#ffd700", "#ff8c00", "#ffd700", "#ff8c00"]}
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_type = db.Column(db.Integer, default=0)
    auth_code = db.Column(db.String(10))
    msg_count = db.Column(db.Integer, default=0)
    referral_code = db.Column(db.String(20), unique=True)
    user_badge = db.Column(db.String(500), default="")
    avatar_data = db.Column(db.Text, default=None)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(200), default="")
    banned_until = db.Column(db.DateTime, nullable=True)
    is_muted = db.Column(db.Boolean, default=False)
    muted_until = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    admin_level = db.Column(db.Integer, default=0)
    moderator_title = db.Column(db.String(100), default="")
    is_anonymous_mod = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    public_key = db.Column(db.Text, nullable=True)
    encryption_salt = db.Column(db.LargeBinary, nullable=True)
    can_delete_messages = db.Column(db.Boolean, default=False)
    can_ban_users = db.Column(db.Boolean, default=False)
    can_mute_users = db.Column(db.Boolean, default=False)
    can_pin_messages = db.Column(db.Boolean, default=False)
    can_change_info = db.Column(db.Boolean, default=False)
    can_add_moderators = db.Column(db.Boolean, default=False)
    can_announce = db.Column(db.Boolean, default=False)
    panic_phrase = db.Column(db.String(100), nullable=True)
    auto_delete_days = db.Column(db.Integer, default=0)
    badge_reason = db.Column(db.String(200), default="")
    custom_color1 = db.Column(db.String(7), default="#ffffff")
    custom_color2 = db.Column(db.String(7), default="#cccccc")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.String(50), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), default="")
    created_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)

class ChannelMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_pinned = db.Column(db.Boolean, default=False)
    pinned_by = db.Column(db.String(50), nullable=True)
    deleted_by = db.Column(db.String(50), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('channel_message.id'), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('channel_message.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    reaction_type = db.Column(db.String(10), nullable=False)

class PremiumUser(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    animation_type = db.Column(db.Integer, default=1)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChannelGiveaway(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    creator = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    winners_count = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)

class GiveawayParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    giveaway_id = db.Column(db.Integer, db.ForeignKey('channel_giveaway.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)

class OAuthApp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    client_id = db.Column(db.String(50), unique=True, nullable=False)
    client_secret = db.Column(db.String(100), nullable=False)
    redirect_uri = db.Column(db.String(500), nullable=False)
    owner = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, default="")
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WetmoBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    owner = db.Column(db.String(50), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OAuthToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(50), nullable=False)
    user = db.Column(db.String(50), nullable=False)
    access_token = db.Column(db.String(200), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PassportData(db.Model):
    __tablename__ = "passport_data"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    first_name = db.Column(db.String(100), default="")
    last_name = db.Column(db.String(100), default="")
    display_name = db.Column(db.String(100), default="")
    bio = db.Column(db.Text, default="")
    birthday = db.Column(db.String(20), default="")
    gender = db.Column(db.String(20), default="")
    language = db.Column(db.String(10), default="ru")
    country = db.Column(db.String(100), default="")
    city = db.Column(db.String(100), default="")
    timezone = db.Column(db.String(20), default="UTC+3")
    workplace = db.Column(db.String(200), default="")
    position = db.Column(db.String(200), default="")
    website = db.Column(db.String(500), default="")
    social_telegram = db.Column(db.String(200), default="")
    social_discord = db.Column(db.String(200), default="")
    social_github = db.Column(db.String(200), default="")
    social_youtube = db.Column(db.String(200), default="")
    social_twitter = db.Column(db.String(200), default="")
    social_instagram = db.Column(db.String(200), default="")
    social_tiktok = db.Column(db.String(200), default="")
    social_twitch = db.Column(db.String(200), default="")
    social_spotify = db.Column(db.String(200), default="")
    social_steam = db.Column(db.String(200), default="")
    accent_color = db.Column(db.String(7), default="#53fc18")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class AdminAction(db.Model):
    __tablename__ = "admin_actions"
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String)
    target_username = db.Column(db.String)
    action_type = db.Column(db.String)
    details = db.Column(db.Text, default="")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SystemAnnouncement(db.Model):
    __tablename__ = "system_announcements"
    id = db.Column(db.Integer, primary_key=True)
    admin_username = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

def generate_referral_code(username):
    hash_str = hashlib.md5((username + str(random.randint(1000, 9999))).encode()).hexdigest()[:8].upper()
    return f"{username.upper()[:4]}{hash_str}"

with app.app_context():
    db_path = 'database.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(user)")
            columns = [col[1] for col in cursor.fetchall()]
            required_columns = ['totp_secret', 'totp_enabled', 'public_key', 'encryption_salt', 'panic_phrase', 'auto_delete_days']
            if not all(col in columns for col in required_columns):
                os.remove(db_path)
                print("🔄 Старая БД удалена, создаю новую...")
        except:
            conn.close()
            os.remove(db_path)
            print("🔄 Старая БД удалена, создаю новую...")
    
    db.create_all()
    
    if not User.query.filter_by(username="wetmo").first():
        wetmo = User(
            username="wetmo", 
            password=generate_password_hash("13681368"), 
            is_verified=True, 
            verification_type=7, 
            is_admin=True, 
            admin_level=3,
            msg_count=1000, 
            referral_code=generate_referral_code("wetmo"),
            created_at=datetime.utcnow(),
            can_delete_messages=True,
            can_ban_users=True,
            can_mute_users=True,
            can_pin_messages=True,
            can_change_info=True,
            can_add_moderators=True,
            can_announce=True,
            moderator_title="Основатель"
        )
        db.session.add(wetmo)
    if not User.query.filter_by(username="world").first():
        db.session.add(User(username="world", password=generate_password_hash("internal_pass"), is_verified=True, verification_type=2, referral_code=generate_referral_code("world")))
    if not Channel.query.filter_by(name="новости").first():
        ch = Channel(name="новости", description="Официальные новости WETMO", created_by="wetmo")
        db.session.add(ch)
        db.session.commit()
        db.session.add(ChannelSubscriber(channel_id=ch.id, username="wetmo"))
    db.session.commit()

def send_system_msg(target_username, text):
    cid = "-".join(sorted(["world", target_username.lower()]))
    db.session.add(Message(chat_id=cid, sender="world", content=text))
    db.session.commit()

def check_admin(username, level=1):
    u = User.query.filter_by(username=username).first()
    return u and u.is_admin and u.admin_level >= level

def check_permission(username, permission):
    u = User.query.filter_by(username=username).first()
    if not u or not u.is_admin: return False
    if u.admin_level >= 3: return True
    return getattr(u, permission, False)

def check_banned_or_muted(username):
    u = User.query.filter_by(username=username).first()
    if not u: return {"banned": False, "muted": False}
    now = datetime.utcnow()
    if u.is_banned:
        if u.banned_until and u.banned_until < now:
            u.is_banned = False; u.ban_reason = ""; u.banned_until = None
            db.session.commit()
        else:
            return {"banned": True, "muted": False, "reason": u.ban_reason}
    if u.is_muted:
        if u.muted_until and u.muted_until < now:
            u.is_muted = False; u.muted_until = None
            db.session.commit()
        else:
            return {"banned": False, "muted": True}
    return {"banned": False, "muted": False}

def broadcast_announcement(text, admin_username):
    db.session.add(SystemAnnouncement(admin_username=admin_username, content=text))
    db.session.commit()
    for user in User.query.filter(~User.username.in_(['world', admin_username])).all():
        send_system_msg(user.username, f"📢 **ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ** 📢\n\n{text}")
    return {"status": "ok"}

def log_action(admin_username, target_username, action_type, details=""):
    db.session.add(AdminAction(admin_username=admin_username, target_username=target_username, action_type=action_type, details=details))
    db.session.commit()

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/api/search_all')
def search_all():
    if 'user' not in session: return jsonify({"users": [], "channels": []})
    query = request.args.get('q', '').strip().lower()
    if len(query) < 1: return jsonify({"users": [], "channels": []})
    current_user = session['user']
    users = User.query.filter(User.username.contains(query), User.username != current_user, ~User.username.in_(['world'])).limit(5).all()
    channels = Channel.query.filter(Channel.name.contains(query)).limit(5).all()
    return jsonify({'users': [{'username': u.username, 'avatar_data': u.avatar_data} for u in users], 'channels': [{'name': c.name} for c in channels]})

@app.route('/api/messages/send', methods=['POST'])
def send_message_api():
    if 'user' not in session: return jsonify({"success": False, "error": "Вы не авторизованы"})
    username = session['user']
    data = request.json
    text = data.get('text', '').strip()
    channel = data.get('channel', 'general')
    if not text: return jsonify({"success": False, "error": "Пустое сообщение"})
    
    encrypted = data.get('encrypted', False)
    if encrypted:
        user = User.query.filter_by(username=username).first()
        if user and user.encryption_salt:
            key = generate_encryption_key(user.password, user.encryption_salt)
            f = Fernet(key)
            text = f.encrypt(text.encode()).decode()
    
    msg = Message(chat_id="-".join(sorted([username, channel])), sender=username, content=text, is_encrypted=encrypted)
    db.session.add(msg); db.session.commit()
    return jsonify({"success": True, "message": {"id": msg.id, "text": text, "timestamp": msg.timestamp.strftime("%H:%M")}})

@app.route('/api/2fa/setup', methods=['POST'])
def setup_2fa():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(username=session['user']).first()
    if not user: return jsonify({"error": "Not found"}), 404
    user.totp_secret = pyotp.random_base32()
    user.totp_enabled = True
    db.session.commit()
    return jsonify({"secret": user.totp_secret, "qr": pyotp.totp.TOTP(user.totp_secret).provisioning_uri(name=session['user'], issuer_name="WETMO")})

@app.route('/api/panic', methods=['POST'])
def panic_button():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(username=session['user']).first()
    if not user: return jsonify({"error": "Not found"}), 404
    Message.query.filter(Message.chat_id.contains(session['user'])).delete()
    ChannelMessage.query.filter_by(sender=session['user']).delete()
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return jsonify({"status": "ok", "message": "Аккаунт полностью удалён"})

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channels = Channel.query.filter(Channel.id.in_([s.channel_id for s in subs])).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    return render_template('index.html', user=u, contacts=contacts, channels=channels, premium=premium, mode='chat', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/im/<target>')
def chat(target):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    t = User.query.filter_by(username=target.lower()).first()
    if not t or u.username == t.username: return redirect(url_for('index'))
    cid = "-".join(sorted([u.username, t.username]))
    msgs = Message.query.filter_by(chat_id=cid).order_by(Message.timestamp.asc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username} | {t.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channels = Channel.query.filter(Channel.id.in_([s.channel_id for s in subs])).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, channels=channels, premium=premium, chat_id=cid, mode='chat', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/profile')
def profile():
    if 'user' not in session: return redirect(url_for('auth'))
    return redirect(url_for('passport', username=session['user']))

@app.route('/profile/<username>')
def user_profile(username):
    if 'user' not in session: return redirect(url_for('auth'))
    return redirect(url_for('passport', username=username.lower()))

@app.route('/passport')
def passport_self():
    if 'user' not in session: return redirect(url_for('auth'))
    return redirect(url_for('passport', username=session['user']))

@app.route('/passport/<username>')
def passport(username):
    if 'user' not in session: return redirect(url_for('auth'))
    viewer = User.query.filter_by(username=session['user']).first()
    profile_user = User.query.filter_by(username=username.lower()).first()
    if not profile_user: return redirect(url_for('index'))
    passport_data = PassportData.query.filter_by(username=username.lower()).first()
    if not passport_data:
        passport_data = PassportData(username=username.lower())
        db.session.add(passport_data); db.session.commit()
    premium = PremiumUser.query.filter_by(username=profile_user.username).first()
    channels_count = ChannelSubscriber.query.filter_by(username=profile_user.username).count()
    all_m = Message.query.filter(Message.chat_id.contains(profile_user.username)).all()
    friends_count = len({p for m in all_m for p in m.chat_id.split('-') if p != profile_user.username})
    developer_apps = OAuthApp.query.filter_by(owner=username.lower()).all()
    developer_bots = WetmoBot.query.filter_by(owner=username.lower()).all()
    return render_template('passport.html', user=viewer, profile_user=profile_user, passport_data=passport_data, premium=premium, channels_count=channels_count, friends_count=friends_count, is_owner=(viewer.username == profile_user.username), VERIFICATION_TYPES=VERIFICATION_TYPES, developer_apps=developer_apps, developer_bots=developer_bots, developer_apps_count=len(developer_apps), developer_bots_count=len(developer_bots))

@app.route('/channel/<string:channel_name>')
def channel_view(channel_name):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    channel = Channel.query.filter_by(name=channel_name.lower()).first_or_404()
    msgs = ChannelMessage.query.filter_by(channel_id=channel.id).order_by(ChannelMessage.timestamp.desc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    contacts = User.query.filter(User.username.in_({p for m in all_m for p in m.chat_id.split('-') if p != u.username})).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channels = Channel.query.filter(Channel.id.in_([s.channel_id for s in subs])).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    posts_with_reactions = [{'msg': msg, 'sender': User.query.filter_by(username=msg.sender).first(), 'likes': Reaction.query.filter_by(post_id=msg.id, reaction_type='like').count(), 'dislikes': Reaction.query.filter_by(post_id=msg.id, reaction_type='dislike').count(), 'user_reaction': (r.reaction_type if (r:=Reaction.query.filter_by(post_id=msg.id, username=u.username).first()) else None), 'sender_premium': PremiumUser.query.filter_by(username=msg.sender).first()} for msg in msgs]
    return render_template('index.html', user=u, channel=channel, posts_with_reactions=posts_with_reactions, contacts=contacts, channels=channels, premium=premium, mode='channel', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/developers')
def developers_portal():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    return render_template('portal.html', user=u, apps=OAuthApp.query.filter_by(owner=u.username).all(), bots=WetmoBot.query.filter_by(owner=u.username).all())

@app.route('/auth')
def auth():
    if 'user' in session: return redirect(url_for('index'))
    return render_template('index.html', auth_type=request.args.get('type', 'login'), mode='auth')

@app.route('/auth', methods=['POST'])
def handle_auth():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    email = request.form.get('email', '').strip().lower()
    auth_type = request.args.get('type', 'login')
    if not username or not password: return render_template('index.html', auth_type=auth_type, mode='auth', error='Заполните все поля')
    if auth_type == 'register':
        if not email or '@' not in email: return render_template('index.html', auth_type='register', mode='auth', error='Некорректный email')
        if User.query.filter_by(username=username).first(): return render_template('index.html', auth_type='register', mode='auth', error='Пользователь уже существует')
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user = User(username=username, password=generate_password_hash(password), referral_code=generate_referral_code(username), auth_code=code)
        db.session.add(user); db.session.commit()
        if send_verification_email(email, code):
            session['pending_user'] = username
            return render_template('index.html', auth_type='verify', mode='verify', message=f'Код отправлен на {email}')
        else: db.session.delete(user); db.session.commit(); return render_template('index.html', auth_type='register', mode='auth', error='Ошибка отправки')
    else:
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if check_banned_or_muted(username)["banned"]: return render_template('index.html', auth_type='login', mode='auth', error='Вы забанены')
            session['user'] = username
            return redirect(url_for('index'))
        return render_template('index.html', auth_type='login', mode='auth', error='Неверный логин или пароль')

@app.route('/verify', methods=['POST'])
def handle_verify():
    if 'pending_user' not in session: return redirect(url_for('auth'))
    user = User.query.filter_by(username=session['pending_user']).first()
    if not user: session.pop('pending_user', None); return redirect(url_for('auth'))
    if user.auth_code == request.form.get('code', '').strip():
        user.is_verified = True; user.auth_code = None; db.session.commit()
        session['user'] = session.pop('pending_user')
        return redirect(url_for('index'))
    return render_template('index.html', auth_type='verify', mode='verify', error='Неверный код')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth'))

@app.route('/admin')
def admin_panel():
    if not check_admin(session.get('user', ''), 1): return redirect(url_for('index'))
    tab = request.args.get('tab', 'moderators')
    return render_template('index.html', mode='admin', tab=tab, all_users=User.query.filter(~User.username.in_(['world'])).all(), all_channels=Channel.query.all(), premium_users=PremiumUser.query.all(), announcements=SystemAnnouncement.query.order_by(SystemAnnouncement.timestamp.desc()).limit(10).all(), moderators=User.query.filter_by(is_admin=True).all(), user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES)

@app.route('/moderator')
def moderator_panel():
    if 'user' not in session: return redirect(url_for('auth'))
    if not check_permission(session['user'], 'can_delete_messages') and not check_permission(session['user'], 'can_ban_users'): return redirect(url_for('index'))
    return render_template('index.html', user=User.query.filter_by(username=session['user']).first(), all_users=User.query.filter(~User.username.in_(['world', session['user']])).all(), mode='moderator', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=2500)
