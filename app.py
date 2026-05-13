import os, random, hashlib, logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import sqlite3
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)

os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = 'wetmo_gateway_v16'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

SMTP_SERVER = "smtp.mail.ru"
SMTP_PORT = 587
SMTP_EMAIL = "mx1chxr0.team@internet.ru"
SMTP_PASSWORD = "GhEe1rmPLrUIVV8L9alg"

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

# ============ МОДЕЛИ ============
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    verification_type = db.Column(db.Integer, default=0)
    auth_code = db.Column(db.String(10))
    status_icon = db.Column(db.String(500), default="")
    msg_count = db.Column(db.Integer, default=0)
    referrer = db.Column(db.String(50), default=None)
    referral_code = db.Column(db.String(20), unique=True)
    pinned_channel = db.Column(db.String(50), default=None)
    badge_reason = db.Column(db.String(200), default="")
    custom_color1 = db.Column(db.String(7), default="#ffffff")
    custom_color2 = db.Column(db.String(7), default="#cccccc")
    user_badge = db.Column(db.String(500), default="")
    avatar_data = db.Column(db.Text, default=None)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(200), default="")
    banned_until = db.Column(db.DateTime, nullable=True)
    is_muted = db.Column(db.Boolean, default=False)
    muted_until = db.Column(db.DateTime, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    admin_level = db.Column(db.Integer, default=0)
    moderator_title = db.Column(db.String(100), default="")  # Кастомный титул модератора
    is_anonymous_mod = db.Column(db.Boolean, default=False)  # Анонимный режим
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Права модератора (устанавливаются админом)
    can_delete_messages = db.Column(db.Boolean, default=False)
    can_ban_users = db.Column(db.Boolean, default=False)
    can_mute_users = db.Column(db.Boolean, default=False)
    can_pin_messages = db.Column(db.Boolean, default=False)
    can_change_info = db.Column(db.Boolean, default=False)
    can_add_moderators = db.Column(db.Boolean, default=False)
    can_announce = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime, nullable=True)
    reply_to = db.Column(db.Integer, nullable=True)
    deleted_by = db.Column(db.String(50), nullable=True)  # Кто удалил (модератор)
    deleted_at = db.Column(db.DateTime, nullable=True)

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), default="")
    created_by = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    verification_type = db.Column(db.Integer, default=0)
    badge = db.Column(db.String(500), default="")

class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    expires_at = db.Column(db.DateTime, nullable=True)

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
    website = db.Column(db.String(500), default="")
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WetmoBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    owner = db.Column(db.String(50), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    avatar_url = db.Column(db.String(500), default="")
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

# ============ ИНИЦИАЛИЗАЦИЯ БД ============
with app.app_context():
    db_path = 'database.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(user)")
            columns = [col[1] for col in cursor.fetchall()]
            required_columns = ['moderator_title', 'is_anonymous_mod', 'can_delete_messages', 'can_ban_users', 'can_mute_users', 'can_pin_messages', 'can_change_info', 'can_add_moderators', 'can_announce']
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
        db.session.add(User(username="world", password=generate_password_hash("internal_pass"), 
                           is_verified=True, verification_type=2, referral_code=generate_referral_code("world")))
    if not Channel.query.filter_by(name="новости").first():
        ch = Channel(name="новости", description="Официальные новости WETMO", 
                     created_by="wetmo", is_public=True, is_verified=True, verification_type=4)
        db.session.add(ch)
        db.session.commit()
        db.session.add(ChannelSubscriber(channel_id=ch.id, username="wetmo"))
    db.session.commit()

def send_system_msg(target_username, text):
    cid = "-".join(sorted(["world", target_username.lower()]))
    db.session.add(Message(chat_id=cid, sender="world", content=text))
    db.session.commit()

# ============ ПРОВЕРКА ПРАВ ============
def check_admin(username, level=1):
    u = User.query.filter_by(username=username).first()
    return u and u.is_admin and u.admin_level >= level

def check_permission(username, permission):
    """Проверка конкретного права модератора"""
    u = User.query.filter_by(username=username).first()
    if not u or not u.is_admin:
        return False
    if u.admin_level >= 3:  # Основатель — все права
        return True
    return getattr(u, permission, False)

def check_banned_or_muted(username):
    u = User.query.filter_by(username=username).first()
    if not u:
        return {"banned": False, "muted": False}
    now = datetime.utcnow()
    if u.is_banned:
        if u.banned_until and u.banned_until < now:
            u.is_banned = False
            u.ban_reason = ""
            u.banned_until = None
            db.session.commit()
        else:
            return {"banned": True, "muted": False, "reason": u.ban_reason}
    if u.is_muted:
        if u.muted_until and u.muted_until < now:
            u.is_muted = False
            u.muted_until = None
            db.session.commit()
        else:
            return {"banned": False, "muted": True}
    return {"banned": False, "muted": False}

def broadcast_announcement(announcement_text, admin_username):
    announcement = SystemAnnouncement(
        admin_username=admin_username,
        content=announcement_text
    )
    db.session.add(announcement)
    db.session.commit()
    
    socketio.emit('system_announcement', {
        'content': announcement_text,
        'admin': admin_username,
        'timestamp': announcement.timestamp.strftime('%H:%M')
    })
    
    users = User.query.filter(~User.username.in_(['world', admin_username])).all()
    for user in users:
        send_system_msg(user.username, f"📢 **ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ** 📢\n\n{announcement_text}")
    
    return {"status": "ok", "recipients": len(users)}

def log_action(admin_username, target_username, action_type, details=""):
    log = AdminAction(
        admin_username=admin_username,
        target_username=target_username,
        action_type=action_type,
        details=details
    )
    db.session.add(log)
    db.session.commit()

# ============ СТАТИКА ============
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

# ============ API ============
@app.route('/api/search_all')
def search_all():
    if 'user' not in session: return jsonify({"users": [], "channels": []})
    query = request.args.get('q', '').strip().lower()
    if len(query) < 1: return jsonify({"users": [], "channels": []})
    current_user = session['user']
    users = User.query.filter(User.username.contains(query), User.username != current_user, ~User.username.in_(['world'])).limit(5).all()
    channels = Channel.query.filter(Channel.name.contains(query), Channel.is_public == True).limit(5).all()
    return jsonify({
        'users': [{'username': u.username, 'is_verified': u.is_verified, 'verification_type': u.verification_type, 'user_badge': u.user_badge, 'avatar_data': u.avatar_data} for u in users],
        'channels': [{'name': c.name, 'description': c.description, 'is_verified': c.is_verified, 'verification_type': c.verification_type, 'badge': c.badge} for c in channels]
    })

@app.route('/api/channel/create', methods=['POST'])
def user_create_channel():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    u = User.query.filter_by(username=session['user']).first()
    if not u: return jsonify({"error": "User not found"}), 404
    data = request.json
    name = data.get('name', '').strip().lower()
    description = data.get('description', '')
    if not name or Channel.query.filter_by(name=name).first(): return jsonify({"error": "Название занято"}), 400
    channel = Channel(name=name, description=description, created_by=u.username, is_public=True)
    db.session.add(channel)
    db.session.commit()
    db.session.add(ChannelSubscriber(channel_id=channel.id, username=u.username))
    db.session.commit()
    return jsonify({"status": "ok", "name": channel.name})

@app.route('/api/channel/<int:channel_id>/subscribe', methods=['POST'])
def subscribe_channel(channel_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    username = session['user']
    sub = ChannelSubscriber.query.filter_by(channel_id=channel_id, username=username).first()
    if sub:
        db.session.delete(sub)
        subscribed = False
    else:
        db.session.add(ChannelSubscriber(channel_id=channel_id, username=username))
        subscribed = True
    db.session.commit()
    return jsonify({"subscribed": subscribed, "count": ChannelSubscriber.query.filter_by(channel_id=channel_id).count()})

@app.route('/api/channel/<int:channel_id>/subscribers')
def get_subscribers(channel_id):
    count = ChannelSubscriber.query.filter_by(channel_id=channel_id).count()
    is_subscribed = False
    if 'user' in session:
        is_subscribed = ChannelSubscriber.query.filter_by(channel_id=channel_id, username=session['user']).first() is not None
    return jsonify({"count": count, "is_subscribed": is_subscribed})

@app.route('/api/channel/<int:channel_id>/unsubscribe', methods=['POST'])
def unsubscribe_channel(channel_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    ChannelSubscriber.query.filter_by(channel_id=channel_id, username=session['user']).delete()
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/channel/<int:channel_id>/delete', methods=['DELETE'])
def delete_own_channel(channel_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    channel = Channel.query.get_or_404(channel_id)
    if channel.created_by != session['user'] and not check_permission(session['user'], 'can_delete_messages'):
        return jsonify({"error": "Forbidden"}), 403
    ChannelMessage.query.filter_by(channel_id=channel_id).delete()
    ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
    db.session.delete(channel)
    db.session.commit()
    log_action(session['user'], channel.name, "delete_channel", f"Канал удалён")
    return jsonify({"status": "ok"})

# ============ РЕДАКТИРОВАНИЕ, УДАЛЕНИЕ, ПЕРЕСЫЛКА, ЗАКРЕПЛЕНИЕ ============

@app.route('/api/message/<int:msg_id>/edit', methods=['POST'])
def edit_message(msg_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    new_content = data.get('content', '').strip()
    
    if not new_content:
        return jsonify({"error": "Сообщение не может быть пустым"}), 400
    
    msg = Message.query.get(msg_id)
    if msg and msg.sender == session['user']:
        msg.content = new_content
        msg.is_edited = True
        msg.edited_at = datetime.utcnow()
        db.session.commit()
        socketio.emit('message_edited', {
            'id': msg.id,
            'content': new_content,
            'chat_id': msg.chat_id,
            'edited_at': msg.edited_at.strftime('%H:%M')
        }, room=msg.chat_id)
        return jsonify({"status": "ok"})
    
    channel_msg = ChannelMessage.query.get(msg_id)
    if channel_msg and channel_msg.sender == session['user']:
        channel_msg.content = new_content
        channel_msg.is_edited = True
        channel_msg.edited_at = datetime.utcnow()
        db.session.commit()
        socketio.emit('channel_message_edited', {
            'id': channel_msg.id,
            'content': new_content,
            'channel_id': channel_msg.channel_id,
            'edited_at': channel_msg.edited_at.strftime('%H:%M')
        }, room=str(channel_msg.channel_id))
        return jsonify({"status": "ok"})
    
    return jsonify({"error": "Сообщение не найдено или нет прав"}), 404

@app.route('/api/message/<int:msg_id>/delete', methods=['DELETE'])
def delete_message(msg_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    username = session['user']
    
    # Проверяем в личных сообщениях
    msg = Message.query.get(msg_id)
    if msg:
        # Может удалить: отправитель ИЛИ модератор с правом can_delete_messages
        if msg.sender == username or check_permission(username, 'can_delete_messages'):
            chat_id = msg.chat_id
            msg.deleted_by = username
            msg.deleted_at = datetime.utcnow()
            db.session.commit()
            socketio.emit('message_deleted', {
                'id': msg_id, 
                'chat_id': chat_id,
                'deleted_by': username if check_permission(username, 'can_delete_messages') and msg.sender != username else None
            }, room=chat_id)
            log_action(username, msg.sender, "delete_message", f"ID: {msg_id}")
            return jsonify({"status": "ok"})
        return jsonify({"error": "Нет прав"}), 403
    
    # Проверяем в канальных сообщениях
    channel_msg = ChannelMessage.query.get(msg_id)
    if channel_msg:
        channel = Channel.query.get(channel_msg.channel_id)
        # Может удалить: отправитель ИЛИ владелец канала ИЛИ модератор с правом
        if channel_msg.sender == username or channel.created_by == username or check_permission(username, 'can_delete_messages'):
            channel_id = channel_msg.channel_id
            channel_msg.deleted_by = username
            channel_msg.deleted_at = datetime.utcnow()
            Comment.query.filter_by(post_id=msg_id).delete()
            Reaction.query.filter_by(post_id=msg_id).delete()
            db.session.commit()
            socketio.emit('channel_message_deleted', {
                'id': msg_id, 
                'channel_id': channel_id,
                'deleted_by': username if username != channel_msg.sender else None
            }, room=str(channel_id))
            log_action(username, channel_msg.sender, "delete_channel_message", f"ID: {msg_id}")
            return jsonify({"status": "ok"})
        return jsonify({"error": "Нет прав"}), 403
    
    return jsonify({"error": "Сообщение не найдено"}), 404

@app.route('/api/message/<int:msg_id>/forward', methods=['POST'])
def forward_message(msg_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    target = data.get('target', '').strip().lower()
    
    if not target:
        return jsonify({"error": "Укажите получателя"}), 400
    
    original = Message.query.get(msg_id) or ChannelMessage.query.get(msg_id)
    if not original:
        return jsonify({"error": "Сообщение не найдено"}), 404
    
    forwarded_content = f"🔄 **Переслано от @{original.sender}**\n\n{original.content}"
    
    if target.startswith('@'):
        channel_name = target[1:]
        channel = Channel.query.filter_by(name=channel_name).first()
        if channel:
            msg = ChannelMessage(
                channel_id=channel.id,
                sender=session['user'],
                content=forwarded_content
            )
            db.session.add(msg)
            db.session.commit()
            socketio.emit('receive_channel_msg', {
                'id': msg.id,
                'channel_id': channel.id,
                'sender': session['user'],
                'message': forwarded_content,
                'timestamp': msg.timestamp.strftime('%H:%M'),
                'is_forwarded': True
            }, room=str(channel.id))
        else:
            return jsonify({"error": "Канал не найден"}), 404
    else:
        target_user = User.query.filter_by(username=target).first()
        if target_user:
            chat_id = "-".join(sorted([session['user'], target]))
            msg = Message(
                chat_id=chat_id,
                sender=session['user'],
                content=forwarded_content
            )
            db.session.add(msg)
            db.session.commit()
            socketio.emit('receive_msg', {
                'sender': session['user'],
                'message': forwarded_content,
                'chat_id': chat_id,
                'is_forwarded': True
            }, room=chat_id)
        else:
            return jsonify({"error": "Пользователь не найден"}), 404
    
    return jsonify({"status": "ok"})

# ============ ЗАКРЕПЛЕНИЕ СООБЩЕНИЙ ============

@app.route('/api/message/<int:msg_id>/pin', methods=['POST'])
def pin_message(msg_id):
    """Закрепить/открепить сообщение в канале"""
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    if not check_permission(session['user'], 'can_pin_messages'):
        return jsonify({"error": "Нет прав на закрепление"}), 403
    
    channel_msg = ChannelMessage.query.get(msg_id)
    if not channel_msg:
        return jsonify({"error": "Сообщение не найдено"}), 404
    
    channel = Channel.query.get(channel_msg.channel_id)
    if not channel:
        return jsonify({"error": "Канал не найден"}), 404
    
    # Проверяем: владелец канала или модератор
    if channel.created_by != session['user'] and not check_permission(session['user'], 'can_pin_messages'):
        return jsonify({"error": "Нет прав"}), 403
    
    # Снимаем все закрепления в этом канале
    if not channel_msg.is_pinned:
        ChannelMessage.query.filter_by(channel_id=channel_msg.channel_id, is_pinned=True).update(
            {"is_pinned": False, "pinned_by": None}
        )
        channel_msg.is_pinned = True
        channel_msg.pinned_by = session['user']
        action = "pin"
    else:
        channel_msg.is_pinned = False
        channel_msg.pinned_by = None
        action = "unpin"
    
    db.session.commit()
    
    socketio.emit('message_pinned', {
        'id': msg_id,
        'channel_id': channel_msg.channel_id,
        'is_pinned': channel_msg.is_pinned,
        'pinned_by': session['user'] if channel_msg.is_pinned else None,
        'content': channel_msg.content if channel_msg.is_pinned else None
    }, room=str(channel_msg.channel_id))
    
    log_action(session['user'], channel.name, f"{action}_message", f"ID: {msg_id}")
    
    return jsonify({"status": "ok", "is_pinned": channel_msg.is_pinned})

# ============ АДМИН: УПРАВЛЕНИЕ МОДЕРАТОРАМИ ============

@app.route('/api/admin/moderator/add', methods=['POST'])
def add_moderator():
    """Назначить пользователя модератором"""
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_add_moderators'):
        return jsonify({"error": "Нет прав на назначение модераторов"}), 403
    
    data = request.json
    target = data.get('username', '').strip().lower()
    
    user = User.query.filter_by(username=target).first()
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404
    
    if user.is_admin and user.admin_level >= session.get('admin_level', 0):
        return jsonify({"error": "Нельзя изменить пользователя с более высоким уровнем"}), 403
    
    # Назначаем модератором с выбранными правами
    user.is_admin = True
    user.admin_level = data.get('admin_level', 1)  # 1 = модер, 2 = админ
    user.moderator_title = data.get('moderator_title', 'Модератор')
    user.is_anonymous_mod = data.get('is_anonymous', False)
    
    # Права
    user.can_delete_messages = data.get('can_delete_messages', True)
    user.can_ban_users = data.get('can_ban_users', True)
    user.can_mute_users = data.get('can_mute_users', True)
    user.can_pin_messages = data.get('can_pin_messages', False)
    user.can_change_info = data.get('can_change_info', False)
    user.can_add_moderators = data.get('can_add_moderators', False)
    user.can_announce = data.get('can_announce', False)
    
    user.verification_type = 2  # Галочка модератора
    
    db.session.commit()
    
    send_system_msg(target, f"🛡 **Вы назначены модератором WETMO!**\n\nТитул: {user.moderator_title}\nУровень: {user.admin_level}")
    log_action(session['user'], target, "add_moderator", f"Уровень: {user.admin_level}, Титул: {user.moderator_title}")
    
    return jsonify({"status": "ok", "message": f"Модератор {target} назначен"})

@app.route('/api/admin/moderator/remove', methods=['POST'])
def remove_moderator():
    """Снять модератора"""
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_add_moderators'):
        return jsonify({"error": "Нет прав"}), 403
    
    data = request.json
    target = data.get('username', '').strip().lower()
    
    if target == session['user']:
        return jsonify({"error": "Нельзя снять самого себя"}), 400
    
    user = User.query.filter_by(username=target).first()
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404
    
    if user.admin_level >= session.get('admin_level', 0) and session['user'] != 'wetmo':
        return jsonify({"error": "Нельзя снять пользователя с более высоким уровнем"}), 403
    
    user.is_admin = False
    user.admin_level = 0
    user.moderator_title = ""
    user.is_anonymous_mod = False
    user.can_delete_messages = False
    user.can_ban_users = False
    user.can_mute_users = False
    user.can_pin_messages = False
    user.can_change_info = False
    user.can_add_moderators = False
    user.can_announce = False
    user.verification_type = 0
    
    db.session.commit()
    
    send_system_msg(target, "С вас сняты права модератора.")
    log_action(session['user'], target, "remove_moderator")
    
    return jsonify({"status": "ok", "message": f"Модератор {target} снят"})

@app.route('/api/admin/moderator/permissions', methods=['POST'])
def update_moderator_permissions():
    """Обновить права модератора"""
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_add_moderators'):
        return jsonify({"error": "Нет прав"}), 403
    
    data = request.json
    target = data.get('username', '').strip().lower()
    
    user = User.query.filter_by(username=target).first()
    if not user or not user.is_admin:
        return jsonify({"error": "Не найден или не модератор"}), 404
    
    # Обновляем права
    user.can_delete_messages = data.get('can_delete_messages', user.can_delete_messages)
    user.can_ban_users = data.get('can_ban_users', user.can_ban_users)
    user.can_mute_users = data.get('can_mute_users', user.can_mute_users)
    user.can_pin_messages = data.get('can_pin_messages', user.can_pin_messages)
    user.can_change_info = data.get('can_change_info', user.can_change_info)
    user.can_add_moderators = data.get('can_add_moderators', user.can_add_moderators)
    user.can_announce = data.get('can_announce', user.can_announce)
    user.is_anonymous_mod = data.get('is_anonymous', user.is_anonymous_mod)
    user.moderator_title = data.get('moderator_title', user.moderator_title)
    
    db.session.commit()
    log_action(session['user'], target, "update_permissions")
    
    return jsonify({"status": "ok"})

@app.route('/api/admin/moderators')
def list_moderators():
    """Список всех модераторов"""
    if 'user' not in session or not check_admin(session['user'], 1):
        return jsonify({"error": "Forbidden"}), 403
    
    mods = User.query.filter_by(is_admin=True).all()
    return jsonify({"moderators": [{
        "username": m.username,
        "admin_level": m.admin_level,
        "moderator_title": m.moderator_title,
        "is_anonymous": m.is_anonymous_mod,
        "can_delete_messages": m.can_delete_messages,
        "can_ban_users": m.can_ban_users,
        "can_mute_users": m.can_mute_users,
        "can_pin_messages": m.can_pin_messages,
        "can_change_info": m.can_change_info,
        "can_add_moderators": m.can_add_moderators,
        "can_announce": m.can_announce,
        "verification_type": m.verification_type,
        "msg_count": m.msg_count
    } for m in mods]})

# ============ АДМИН: ОБЪЯВЛЕНИЯ ============

@app.route('/api/admin/announce', methods=['POST'])
def admin_announce():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_announce'):
        return jsonify({"error": "Нет прав на объявления"}), 403
    
    data = request.json
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({"error": "Текст объявления не может быть пустым"}), 400
    
    result = broadcast_announcement(text, session['user'])
    log_action(session['user'], "ALL", "announce", text[:200])
    
    return jsonify(result)

# ============ АДМИН: БАН/МУТ (с проверкой прав) ============

@app.route('/admin/ban', methods=['POST'])
def admin_ban():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_ban_users'):
        return jsonify({"error": "Нет прав на бан"}), 403
    
    data = request.json
    target = data.get('target')
    reason = data.get('reason', 'Нарушение правил')
    hours = data.get('hours', 0)
    
    # Нельзя банить равных или выше
    target_user = User.query.filter_by(username=target).first()
    if target_user and target_user.is_admin and target_user.admin_level >= session.get('admin_level', 0) and session['user'] != 'wetmo':
        return jsonify({"error": "Нельзя забанить этого пользователя"}), 403
    
    u = User.query.filter_by(username=target).first()
    if u:
        u.is_banned = True
        u.ban_reason = reason
        u.banned_until = datetime.utcnow() + timedelta(hours=hours) if hours > 0 else None
        db.session.commit()
        send_system_msg(target, f"🚫 **Вы забанены.**\nПричина: {reason}\n{'Срок: ' + str(hours) + 'ч' if hours > 0 else 'Навсегда'}")
        log_action(session['user'], target, "ban", f"Причина: {reason}, Часов: {hours}")
    return jsonify({"status": "ok"})

@app.route('/admin/unban', methods=['POST'])
def admin_unban():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_ban_users'):
        return jsonify({"error": "Нет прав на разбан"}), 403
    
    target = request.json.get('target')
    u = User.query.filter_by(username=target).first()
    if u:
        u.is_banned = False
        u.ban_reason = ""
        u.banned_until = None
        db.session.commit()
        send_system_msg(target, "✅ **Вы разбанены.** Добро пожаловать обратно!")
        log_action(session['user'], target, "unban")
    return jsonify({"status": "ok"})

@app.route('/admin/mute', methods=['POST'])
def admin_mute():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_mute_users'):
        return jsonify({"error": "Нет прав на мут"}), 403
    
    data = request.json
    target = data.get('target')
    hours = data.get('hours', 24)
    
    u = User.query.filter_by(username=target).first()
    if u:
        u.is_muted = True
        u.muted_until = datetime.utcnow() + timedelta(hours=hours)
        db.session.commit()
        send_system_msg(target, f"🔇 **Вы получили мут на {hours}ч.**")
        log_action(session['user'], target, "mute", f"Часов: {hours}")
    return jsonify({"status": "ok"})

@app.route('/admin/unmute', methods=['POST'])
def admin_unmute():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if not check_permission(session['user'], 'can_mute_users'):
        return jsonify({"error": "Нет прав на размут"}), 403
    
    target = request.json.get('target')
    u = User.query.filter_by(username=target).first()
    if u:
        u.is_muted = False
        u.muted_until = None
        db.session.commit()
        send_system_msg(target, "🔊 **Мут снят.** Вы снова можете писать.")
        log_action(session['user'], target, "unmute")
    return jsonify({"status": "ok"})

# ============ ОСТАЛЬНЫЕ API (сокращённо, без изменений) ============

@app.route('/api/post/<int:post_id>/delete', methods=['DELETE'])
def delete_post(post_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    post = ChannelMessage.query.get_or_404(post_id)
    channel = Channel.query.get(post.channel_id)
    if post.sender != session['user'] and channel.created_by != session['user'] and not check_permission(session['user'], 'can_delete_messages'):
        return jsonify({"error": "Forbidden"}), 403
    Comment.query.filter_by(post_id=post_id).delete()
    Reaction.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    log_action(session['user'], post.sender, "delete_post", f"ID: {post_id}")
    return jsonify({"status": "ok"})

@app.route('/api/post/<int:post_id>/react', methods=['POST'])
def react_post(post_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    reaction_type = data.get('type')
    username = session['user']
    
    existing = Reaction.query.filter_by(post_id=post_id, username=username).first()
    if existing:
        if existing.reaction_type == reaction_type:
            db.session.delete(existing)
        else:
            existing.reaction_type = reaction_type
    else:
        db.session.add(Reaction(post_id=post_id, username=username, reaction_type=reaction_type))
    db.session.commit()
    
    likes = Reaction.query.filter_by(post_id=post_id, reaction_type='like').count()
    dislikes = Reaction.query.filter_by(post_id=post_id, reaction_type='dislike').count()
    
    socketio.emit('reaction_update', {'post_id': post_id, 'likes': likes, 'dislikes': dislikes}, room=f"post_{post_id}")
    return jsonify({"likes": likes, "dislikes": dislikes})

@app.route('/api/chat/delete/<target>', methods=['DELETE'])
def delete_chat(target):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    cid = "-".join(sorted([session['user'], target.lower()]))
    Message.query.filter_by(chat_id=cid).delete()
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/premium/animation/<int:anim_type>', methods=['POST'])
def set_premium_animation(anim_type):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    premium = PremiumUser.query.filter_by(username=session['user']).first()
    if not premium: return jsonify({"error": "Premium not active"}), 403
    premium.animation_type = anim_type
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/user/avatar', methods=['POST'])
def save_avatar():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    avatar = data.get('avatar', '')
    user = User.query.filter_by(username=session['user']).first()
    user.avatar_data = avatar[:500000] if avatar else None
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/user/pin_channel', methods=['POST'])
def pin_channel():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    user.pinned_channel = data.get('channel', '') or None
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/passport/save', methods=['POST'])
def save_passport():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    username = session['user']
    data = request.json
    
    passport = PassportData.query.filter_by(username=username).first()
    if not passport:
        passport = PassportData(username=username)
        db.session.add(passport)
    
    passport.first_name = data.get('first_name', '')[:100]
    passport.last_name = data.get('last_name', '')[:100]
    passport.display_name = data.get('display_name', '')[:100]
    passport.bio = data.get('bio', '')[:500]
    passport.birthday = data.get('birthday', '')[:20]
    passport.gender = data.get('gender', '')[:20]
    passport.language = data.get('language', 'ru')[:10]
    passport.country = data.get('country', '')[:100]
    passport.city = data.get('city', '')[:100]
    passport.timezone = data.get('timezone', 'UTC+3')[:20]
    passport.workplace = data.get('workplace', '')[:200]
    passport.position = data.get('position', '')[:200]
    passport.website = data.get('website', '')[:500]
    passport.social_telegram = data.get('social_telegram', '')[:200]
    passport.social_discord = data.get('social_discord', '')[:200]
    passport.social_github = data.get('social_github', '')[:200]
    passport.social_youtube = data.get('social_youtube', '')[:200]
    passport.social_twitter = data.get('social_twitter', '')[:200]
    passport.social_instagram = data.get('social_instagram', '')[:200]
    passport.social_tiktok = data.get('social_tiktok', '')[:200]
    passport.social_twitch = data.get('social_twitch', '')[:200]
    passport.social_spotify = data.get('social_spotify', '')[:200]
    passport.social_steam = data.get('social_steam', '')[:200]
    passport.accent_color = data.get('accent_color', '#53fc18')[:7]
    passport.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/developers/app/create', methods=['POST'])
def create_oauth_app():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    name = data.get('name')
    redirect_uri = data.get('redirect_uri')
    if not name or not redirect_uri: return jsonify({"error": "Name and redirect_uri required"}), 400
    import secrets
    client_id = secrets.token_hex(16)
    client_secret = secrets.token_hex(32)
    app_oauth = OAuthApp(name=name, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, owner=session['user'], description=data.get('description', ''))
    db.session.add(app_oauth)
    db.session.commit()
    return jsonify({"status": "ok", "client_id": client_id, "client_secret": client_secret})

@app.route('/api/developers/bot/create', methods=['POST'])
def create_bot():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    username = data.get('username', '').strip().lower()
    if not username: return jsonify({"error": "Username required"}), 400
    if User.query.filter_by(username=username).first() or WetmoBot.query.filter_by(username=username).first():
        return jsonify({"error": "Username taken"}), 400
    import secrets
    token = secrets.token_hex(32)
    
    bot_user = User(username=username, password=generate_password_hash(token), is_verified=True, verification_type=2, referral_code=generate_referral_code(username))
    db.session.add(bot_user)
    
    bot = WetmoBot(username=username, owner=session['user'], token=token, description=data.get('description', ''), is_public=data.get('is_public', False))
    db.session.add(bot)
    db.session.commit()
    return jsonify({"status": "ok", "username": username, "token": token})

# ============ ОСНОВНЫЕ МАРШРУТЫ (без изменений) ============

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channel_ids = [s.channel_id for s in subs]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    return render_template('index.html', user=u, contacts=contacts, channels=channels, premium=premium, mode='chat', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/im/<target>')
def chat(target):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    t = User.query.filter_by(username=target.lower()).first()
    if not t or u.username == t.username: return redirect(url_for('index'))
    cid = "-".join(sorted([u.username, t.username]))
    msgs = Message.query.filter_by(chat_id=cid).order_by(Message.timestamp.asc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    names.add(t.username)
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channels = Channel.query.filter(Channel.id.in_(sub.channel_id for sub in subs)).all()
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
    if not viewer: session.clear(); return redirect(url_for('auth'))
    profile_user = User.query.filter_by(username=username.lower()).first()
    if not profile_user: return redirect(url_for('index'))
    passport_data = PassportData.query.filter_by(username=username.lower()).first()
    if not passport_data:
        passport_data = PassportData(username=username.lower())
        db.session.add(passport_data)
        db.session.commit()
    premium = PremiumUser.query.filter_by(username=profile_user.username).first()
    channels_count = ChannelSubscriber.query.filter_by(username=profile_user.username).count()
    all_m = Message.query.filter(Message.chat_id.contains(profile_user.username)).all()
    friends_count = len({p for m in all_m for p in m.chat_id.split('-') if p != profile_user.username})
    developer_apps = OAuthApp.query.filter_by(owner=username.lower()).all()
    developer_bots = WetmoBot.query.filter_by(owner=username.lower()).all()
    developer_apps_count = len(developer_apps)
    developer_bots_count = len(developer_bots)
    return render_template('passport.html', user=viewer, profile_user=profile_user, passport_data=passport_data, premium=premium, is_online=True, last_seen=profile_user.created_at.strftime('%H:%M') if profile_user.created_at else 'давно', channels_count=channels_count, friends_count=friends_count, is_owner=(viewer.username == profile_user.username), VERIFICATION_TYPES=VERIFICATION_TYPES, developer_apps=developer_apps, developer_bots=developer_bots, developer_apps_count=developer_apps_count, developer_bots_count=developer_bots_count)

@app.route('/channel/<string:channel_name>')
def channel_view(channel_name):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    channel = Channel.query.filter_by(name=channel_name.lower()).first_or_404()
    msgs = ChannelMessage.query.filter_by(channel_id=channel.id).order_by(ChannelMessage.timestamp.desc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channels = Channel.query.filter(Channel.id.in_(sub.channel_id for sub in subs)).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    posts_with_reactions = []
    for msg in msgs:
        sender = User.query.filter_by(username=msg.sender).first()
        likes = Reaction.query.filter_by(post_id=msg.id, reaction_type='like').count()
        dislikes = Reaction.query.filter_by(post_id=msg.id, reaction_type='dislike').count()
        user_reaction = Reaction.query.filter_by(post_id=msg.id, username=u.username).first()
        sender_premium = PremiumUser.query.filter_by(username=msg.sender).first()
        posts_with_reactions.append({'msg': msg, 'sender': sender, 'likes': likes, 'dislikes': dislikes, 'user_reaction': user_reaction.reaction_type if user_reaction else None, 'sender_premium': sender_premium})
    return render_template('index.html', user=u, channel=channel, posts_with_reactions=posts_with_reactions, contacts=contacts, channels=channels, premium=premium, mode='channel', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/developers')
def developers_portal():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    apps = OAuthApp.query.filter_by(owner=u.username).all()
    bots = WetmoBot.query.filter_by(owner=u.username).all()
    return render_template('portal.html', user=u, apps=apps, bots=bots)

@app.route('/auth')
def auth():
    auth_type = request.args.get('type', 'login')
    if 'user' in session: return redirect(url_for('index'))
    return render_template('index.html', auth_type=auth_type, mode='auth')

@app.route('/auth', methods=['POST'])
def handle_auth():
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    email = request.form.get('email', '').strip().lower()
    auth_type = request.args.get('type', 'login')
    
    if not username or not password:
        return render_template('index.html', auth_type=auth_type, mode='auth', error='Заполните все поля')
    
    if auth_type == 'register':
        if not email or '@' not in email:
            return render_template('index.html', auth_type='register', mode='auth', error='Некорректный email')
        if User.query.filter_by(username=username).first():
            return render_template('index.html', auth_type='register', mode='auth', error='Пользователь уже существует')
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        user = User(username=username, password=generate_password_hash(password), referral_code=generate_referral_code(username), auth_code=code)
        ref_code = session.get('ref_code')
        if ref_code:
            referrer = User.query.filter_by(referral_code=ref_code).first()
            if referrer and referrer.username != username:
                user.referrer = referrer.username
        db.session.add(user)
        db.session.commit()
        if send_verification_email(email, code):
            session['pending_user'] = username
            return render_template('index.html', auth_type='verify', mode='verify', message=f'Код отправлен на {email}')
        else:
            db.session.delete(user)
            db.session.commit()
            return render_template('index.html', auth_type='register', mode='auth', error='Ошибка отправки письма')
    else:
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            check = check_banned_or_muted(username)
            if check["banned"]:
                return render_template('index.html', auth_type='login', mode='auth', error=f'Вы забанены: {check.get("reason", "")}')
            session['user'] = username
            return redirect(url_for('index'))
        return render_template('index.html', auth_type='login', mode='auth', error='Неверный логин или пароль')

@app.route('/verify', methods=['POST'])
def handle_verify():
    if 'pending_user' not in session: return redirect(url_for('auth'))
    code = request.form.get('code', '').strip()
    username = session['pending_user']
    user = User.query.filter_by(username=username).first()
    if not user: session.pop('pending_user', None); return redirect(url_for('auth'))
    if user.auth_code == code:
        user.is_verified = True
        user.auth_code = None
        db.session.commit()
        session['user'] = username
        session.pop('pending_user', None)
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
    all_users = User.query.filter(~User.username.in_(['world'])).all()
    all_channels = Channel.query.all()
    premium_users = PremiumUser.query.all()
    announcements = SystemAnnouncement.query.order_by(SystemAnnouncement.timestamp.desc()).limit(10).all()
    moderators = User.query.filter_by(is_admin=True).all()
    return render_template('index.html', mode='admin', tab=tab, all_users=all_users, all_channels=all_channels, premium_users=premium_users, announcements=announcements, moderators=moderators, user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES)

# ============ SOCKET.IO ============
@socketio.on('join')
def on_join(data):
    if 'chat_id' in data: join_room(data['chat_id'])
    if 'channel_id' in data: join_room(str(data['channel_id']))
    if 'post_id' in data: join_room(f"post_{data['post_id']}")

@socketio.on('send_msg')
def handle_message(data):
    sender_username = session.get('user')
    if not sender_username: return
    sender = User.query.filter_by(username=sender_username).first()
    if not sender: return
    
    check = check_banned_or_muted(sender_username)
    if check["muted"]: return
    
    if 'channel_id' in data:
        channel_id = data['channel_id']
        channel = Channel.query.get(channel_id)
        if not channel: return
        if channel.created_by != sender_username and sender_username != 'wetmo' and not check_permission(sender_username, 'can_change_info'):
            return
        msg = ChannelMessage(channel_id=channel_id, sender=sender_username, content=data['message'])
        db.session.add(msg)
        db.session.commit()
        emit('receive_channel_msg', {'id': msg.id, 'channel_id': channel_id, 'sender': sender_username, 'message': data['message'], 'timestamp': msg.timestamp.strftime('%H:%M'), 'avatar_data': sender.avatar_data, 'user_badge': sender.user_badge, 'verification_type': sender.verification_type}, room=str(channel_id))
    elif 'target' in data:
        target = data['target'].lower()
        target_user = User.query.filter_by(username=target).first()
        if not target_user: return
        chat_id = "-".join(sorted([sender_username, target]))
        msg = Message(chat_id=chat_id, sender=sender_username, content=data['message'])
        db.session.add(msg)
        sender.msg_count += 1
        db.session.commit()
        emit('receive_msg', {'id': msg.id, 'sender': sender_username, 'message': data['message'], 'avatar_data': sender.avatar_data, 'user_badge': sender.user_badge, 'verification_type': sender.verification_type}, room=chat_id)

# ============ ЗАПУСК ============
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=2500, debug=True)
