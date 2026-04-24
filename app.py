import os, random, hashlib, logging
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3

logging.basicConfig(level=logging.INFO)

os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_gateway_v14'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

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

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

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

def generate_referral_code(username):
    hash_str = hashlib.md5((username + str(random.randint(1000, 9999))).encode()).hexdigest()[:8].upper()
    return f"{username.upper()[:4]}{hash_str}"

with app.app_context():
    db_path = 'database.db'
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()
        
        required_columns = ['referrer', 'referral_code', 'verification_type', 'pinned_channel', 'badge_reason', 'custom_color1', 'custom_color2', 'user_badge', 'avatar_data']
        if not all(col in columns for col in required_columns):
            os.remove(db_path)
            print("🔄 Старая БД удалена, создаю новую...")
    
    db.create_all()
    
    if not User.query.filter_by(username="wetmo").first():
        wetmo = User(username="wetmo", password=generate_password_hash("13681368"), 
                     is_verified=True, verification_type=2,
                     msg_count=1000, referral_code=generate_referral_code("wetmo"))
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
    if channel.created_by != session['user'] and session['user'] != 'wetmo':
        return jsonify({"error": "Forbidden"}), 403
    ChannelMessage.query.filter_by(channel_id=channel_id).delete()
    ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
    db.session.delete(channel)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/post/<int:post_id>/delete', methods=['DELETE'])
def delete_post(post_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    post = ChannelMessage.query.get_or_404(post_id)
    channel = Channel.query.get(post.channel_id)
    if post.sender != session['user'] and session['user'] != 'wetmo' and channel.created_by != session['user']:
        return jsonify({"error": "Forbidden"}), 403
    Comment.query.filter_by(post_id=post_id).delete()
    Reaction.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/post/<int:post_id>/comments')
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp.asc()).all()
    return jsonify([{'sender': c.sender, 'content': c.content, 'timestamp': c.timestamp.strftime('%H:%M')} for c in comments])

@app.route('/api/post/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    content = data.get('content', '').strip()
    if not content: return jsonify({"error": "Empty comment"}), 400
    comment = Comment(post_id=post_id, sender=session['user'], content=content)
    db.session.add(comment)
    db.session.commit()
    socketio.emit('new_comment', {'post_id': post_id, 'sender': session['user'], 'content': content, 'timestamp': comment.timestamp.strftime('%H:%M')}, room=f"post_{post_id}")
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
    user_reaction = Reaction.query.filter_by(post_id=post_id, username=username).first()
    
    socketio.emit('reaction_update', {'post_id': post_id, 'likes': likes, 'dislikes': dislikes, 'user_reaction': user_reaction.reaction_type if user_reaction else None}, room=f"post_{post_id}")
    return jsonify({"likes": likes, "dislikes": dislikes})

@app.route('/api/chat/delete/<target>', methods=['DELETE'])
def delete_chat(target):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    cid = "-".join(sorted([session['user'], target.lower()]))
    Message.query.filter_by(chat_id=cid).delete()
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/premium/status/<username>')
def get_premium_status(username):
    premium = PremiumUser.query.filter_by(username=username).first()
    if premium:
        return jsonify({"active": True, "animation": premium.animation_type})
    return jsonify({"active": False})

@app.route('/api/premium/animation/<int:anim_type>', methods=['POST'])
def set_premium_animation(anim_type):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    if anim_type < 1 or anim_type > 11: return jsonify({"error": "Invalid animation type"}), 400
    premium = PremiumUser.query.filter_by(username=session['user']).first()
    if not premium: return jsonify({"error": "Premium not active"}), 403
    premium.animation_type = anim_type
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/premium/custom_color', methods=['POST'])
def set_custom_color():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    color1 = data.get('color1', '#ffffff')
    color2 = data.get('color2', '#cccccc')
    premium = PremiumUser.query.filter_by(username=session['user']).first()
    if not premium: return jsonify({"error": "Premium not active"}), 403
    user = User.query.filter_by(username=session['user']).first()
    user.custom_color1 = color1
    user.custom_color2 = color2
    premium.animation_type = 11
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

@app.route('/api/channel/<int:channel_id>/giveaway/create', methods=['POST'])
def create_channel_giveaway(channel_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    channel = Channel.query.get_or_404(channel_id)
    if channel.created_by != session['user'] and session['user'] != 'wetmo':
        return jsonify({"error": "Forbidden"}), 403
    data = request.json
    winners = data.get('winners', 1)
    ends_at = datetime.fromisoformat(data.get('ends_at'))
    giveaway = ChannelGiveaway(channel_id=channel_id, creator=session['user'], ends_at=ends_at, winners_count=winners)
    db.session.add(giveaway)
    db.session.commit()
    msg = ChannelMessage(channel_id=channel_id, sender="WETMO",
        content=f"🎉 **РОЗЫГРЫШ WETMO PREMIUM!** 🎉\n\nОрганизатор: @{session['user']}\nРазыгрывается {winners} Premium-подписок!\nУспей участвовать до {ends_at.strftime('%d.%m.%Y %H:%M')}!")
    db.session.add(msg)
    db.session.commit()
    socketio.emit('receive_channel_msg', {
        'id': msg.id, 'channel_id': channel_id, 'sender': 'WETMO', 
        'message': msg.content, 'verified': True, 'badge': None, 
        'timestamp': msg.timestamp.strftime('%H:%M'), 'giveaway_id': giveaway.id
    }, room=str(channel_id))
    return jsonify({"status": "ok"})

@app.route('/api/giveaway/<int:giveaway_id>/join', methods=['POST'])
def join_giveaway(giveaway_id):
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    giveaway = ChannelGiveaway.query.get_or_404(giveaway_id)
    if not giveaway.is_active: return jsonify({"error": "Giveaway ended"}), 400
    if datetime.utcnow() > giveaway.ends_at:
        giveaway.is_active = False; db.session.commit()
        return jsonify({"error": "Giveaway ended"}), 400
    existing = GiveawayParticipant.query.filter_by(giveaway_id=giveaway_id, username=session['user']).first()
    if existing: return jsonify({"error": "Already joined"}), 400
    db.session.add(GiveawayParticipant(giveaway_id=giveaway_id, username=session['user']))
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/referral/<code>')
def referral_link(code):
    session['ref_code'] = code
    return redirect(url_for('auth', type='register'))

@app.route('/admin/give_premium/<username>', methods=['POST'])
def admin_give_premium(username):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"error": "User not found"}), 404
    existing = PremiumUser.query.filter_by(username=username).first()
    if not existing:
        db.session.add(PremiumUser(username=username, animation_type=1))
    user.verification_type = 3; user.is_verified = True
    db.session.commit()
    send_system_msg(username, "🎁 **Поздравляем!** Администратор выдал вам WETMO Premium!")
    return jsonify({"status": "ok"})

@app.route('/admin/remove_premium/<username>', methods=['DELETE'])
def admin_remove_premium(username):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    PremiumUser.query.filter_by(username=username).delete()
    user = User.query.filter_by(username=username).first()
    if user: user.verification_type = 0; user.is_verified = False
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/admin/give_badge/<username>', methods=['POST'])
def admin_give_badge(username):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    data = request.json
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"error": "User not found"}), 404
    user.verification_type = data.get('vtype', 0)
    user.is_verified = (user.verification_type > 0)
    user.badge_reason = data.get('reason', '')
    db.session.commit()
    send_system_msg(username, f"🏅 Администратор выдал вам галочку! Причина: {data.get('reason', '')}")
    return jsonify({"status": "ok"})

@app.route('/admin/give_user_badge/<username>', methods=['POST'])
def admin_give_user_badge(username):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    data = request.json
    user = User.query.filter_by(username=username).first()
    if not user: return jsonify({"error": "User not found"}), 404
    user.user_badge = data.get('badge_url', '')
    db.session.commit()
    send_system_msg(username, "🎖️ Администратор выдал вам эмблему!")
    return jsonify({"status": "ok"})

@app.route('/api/user/pin_channel', methods=['POST'])
def pin_channel():
    if 'user' not in session: return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    user = User.query.filter_by(username=session['user']).first()
    user.pinned_channel = data.get('channel', '') or None
    db.session.commit()
    return jsonify({"status": "ok"})

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
    return render_template('index.html', user=u, contacts=contacts, channels=channels, 
                          premium=premium, mode='chat', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES,
                          premium_colors=PREMIUM_COLORS)

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
    channel_ids = [s.channel_id for s in subs]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, channels=channels, 
                          premium=premium, chat_id=cid, mode='chat', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES,
                          premium_colors=PREMIUM_COLORS)

@app.route('/profile/<username>')
def user_profile(username):
    if 'user' not in session: return redirect(url_for('auth'))
    viewer = User.query.filter_by(username=session['user']).first()
    if not viewer: session.clear(); return redirect(url_for('auth'))
    u = User.query.filter_by(username=username.lower()).first()
    if not u: return redirect(url_for('profile'))
    premium = PremiumUser.query.filter_by(username=u.username).first()
    return render_template('index.html', user=viewer, profile_user=u, premium=premium, mode='user_profile',
                          user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/channel/<string:channel_name>')
def channel_view(channel_name):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    channel = Channel.query.filter_by(name=channel_name.lower()).first_or_404()
    if not channel.is_public and u.username != 'wetmo': abort(403)
    msgs = ChannelMessage.query.filter_by(channel_id=channel.id).order_by(ChannelMessage.timestamp.desc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channel_ids = [s.channel_id for s in subs]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    posts_with_reactions = []
    for msg in msgs:
        likes = Reaction.query.filter_by(post_id=msg.id, reaction_type='like').count()
        dislikes = Reaction.query.filter_by(post_id=msg.id, reaction_type='dislike').count()
        user_reaction = Reaction.query.filter_by(post_id=msg.id, username=u.username).first()
        msg_sender = User.query.filter_by(username=msg.sender).first()
        sender_premium = PremiumUser.query.filter_by(username=msg.sender).first()
        posts_with_reactions.append({
            'msg': msg, 'sender': msg_sender, 'sender_premium': sender_premium,
            'likes': likes, 'dislikes': dislikes,
            'user_reaction': user_reaction.reaction_type if user_reaction else None
        })
    return render_template('index.html', user=u, channel=channel, posts_with_reactions=posts_with_reactions, 
                          contacts=contacts, channels=channels, premium=premium, mode='channel', 
                          user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/post/<int:post_id>')
def post_view(post_id):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    post = ChannelMessage.query.get_or_404(post_id)
    channel = Channel.query.get(post.channel_id)
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.timestamp.asc()).all()
    likes = Reaction.query.filter_by(post_id=post_id, reaction_type='like').count()
    dislikes = Reaction.query.filter_by(post_id=post_id, reaction_type='dislike').count()
    user_reaction = Reaction.query.filter_by(post_id=post_id, username=u.username).first()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channel_ids = [s.channel_id for s in subs]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    premium = PremiumUser.query.filter_by(username=u.username).first()
    post_sender = User.query.filter_by(username=post.sender).first()
    sender_premium = PremiumUser.query.filter_by(username=post.sender).first()
    return render_template('index.html', user=u, post=post, post_sender=post_sender, sender_premium=sender_premium,
                          channel=channel, comments=comments, likes=likes, dislikes=dislikes, user_reaction=user_reaction,
                          contacts=contacts, channels=channels, premium=premium, mode='post', 
                          user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS)

@app.route('/profile')
def profile_page():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    premium = PremiumUser.query.filter_by(username=u.username).first()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    subs = ChannelSubscriber.query.filter_by(username=u.username).all()
    channel_ids = [s.channel_id for s in subs]
    channels = Channel.query.filter(Channel.id.in_(channel_ids)).all()
    pinned_channel = Channel.query.filter_by(name=u.pinned_channel).first() if u.pinned_channel else None
    referral_link = f"{request.host_url}api/referral/{u.referral_code}"
    show_ads = not premium
    return render_template('index.html', user=u, premium=premium, contacts=contacts, channels=channels, 
                          pinned_channel=pinned_channel, referral_link=referral_link, mode='profile',
                          user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES, premium_colors=PREMIUM_COLORS,
                          show_ads=show_ads)

@app.route('/premium.html')
def premium_html():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u: session.clear(); return redirect(url_for('auth'))
    premium = PremiumUser.query.filter_by(username=u.username).first()
    referral_link = f"{request.host_url}api/referral/{u.referral_code}"
    show_ads = not premium
    return render_template('premium.html', user=u, premium=premium, referral_link=referral_link,
                          show_ads=show_ads, premium_colors=PREMIUM_COLORS)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    t = request.args.get('type', 'login')
    ref_code = session.get('ref_code', '')
    if request.method == 'POST':
        name = request.form.get('username', '').strip().lower()
        pw = request.form.get('password', '')
        if not name or not pw: return "Заполните все поля", 400
        if not all(c.isalnum() or c == '_' for c in name): return "Ник может содержать только латиницу, цифры и _", 400
        if len(name) < 3 or len(name) > 20: return "Ник должен быть от 3 до 20 символов", 400
        u = User.query.filter_by(username=name).first()
        if t == 'register':
            if u: return "Ник занят", 400
            new_u = User(username=name, password=generate_password_hash(pw), referral_code=generate_referral_code(name))
            if ref_code:
                referrer = User.query.filter_by(referral_code=ref_code).first()
                if referrer and referrer.username != name:
                    new_u.referrer = referrer.username
                    send_system_msg(referrer.username, f"🎉 По вашей реферальной ссылке зарегистрировался @{name}!")
            db.session.add(new_u); db.session.commit()
            session['user'] = name; session.pop('ref_code', None)
            return redirect(url_for('index'))
        else:
            if not u or not check_password_hash(u.password, pw): return "Неверный ник или пароль", 401
            if u.username == 'wetmo': session['user'] = 'wetmo'; return redirect(url_for('index'))
            code = f"{random.randint(100,999)}-{random.randint(100,999)}"
            u.auth_code = code; db.session.commit()
            send_system_msg(name, f"🛡 **Вход в аккаунт WETMO**\nКод: `{code}`")
            session['temp_user'] = name
            return redirect(url_for('verify'))
    return render_template('index.html', mode='auth', auth_type=t, user=None)

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    name = session.get('temp_user')
    if not name: return redirect(url_for('auth'))
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        u = User.query.filter_by(username=name).first()
        if u and code == u.auth_code:
            session['user'] = name; session.pop('temp_user', None)
            return redirect(url_for('index'))
        return "Неверный код", 400
    return render_template('index.html', mode='verify', user=None)

@app.route('/admin')
def admin():
    u = User.query.filter_by(username=session.get('user')).first()
    if not u or u.username != 'wetmo': abort(403)
    tab = request.args.get('tab', 'users')
    users = User.query.all()
    channels = Channel.query.all()
    premium_users = PremiumUser.query.all()
    return render_template('index.html', user=u, all_users=users, all_channels=channels, premium_users=premium_users, 
                          tab=tab, mode='admin', user_badges=USER_BADGES, channel_badges=CHANNEL_BADGES)

@app.route('/admin/verify/<int:uid>/<int:vtype>')
def admin_v(uid, vtype):
    if session.get('user') == 'wetmo':
        t = db.session.get(User, uid)
        if t: t.verification_type = vtype; t.is_verified = (vtype > 0); db.session.commit()
    return redirect(url_for('admin', tab='users'))

@app.route('/admin/delete/<int:uid>')
def admin_delete(uid):
    if session.get('user') == 'wetmo':
        t = db.session.get(User, uid)
        if t and t.username not in ['wetmo', 'world']:
            Message.query.filter((Message.sender == t.username) | (Message.chat_id.contains(t.username))).delete()
            db.session.delete(t); db.session.commit()
    return redirect(url_for('admin', tab='users'))

@app.route('/admin/channel/verify/<int:channel_id>')
def admin_channel_verify(channel_id):
    if session.get('user') == 'wetmo':
        channel = db.session.get(Channel, channel_id)
        if channel: channel.verification_type = 4 if channel.verification_type == 0 else 0; channel.is_verified = (channel.verification_type > 0); db.session.commit()
    return redirect(url_for('admin', tab='channels'))

@app.route('/admin/channel/badge/<int:channel_id>', methods=['POST'])
def admin_channel_badge(channel_id):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    data = request.json
    channel = db.session.get(Channel, channel_id)
    if channel: channel.badge = data.get('badge', ''); db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/admin/channel/delete/<int:channel_id>', methods=['DELETE'])
def admin_delete_channel(channel_id):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    channel = db.session.get(Channel, channel_id)
    if channel:
        ChannelMessage.query.filter_by(channel_id=channel_id).delete()
        ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
        db.session.delete(channel); db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/set_badge', methods=['POST'])
def set_badge():
    u = User.query.filter_by(username=session.get('user')).first()
    if u and u.msg_count >= 1000:
        u.status_icon = request.json.get('badge_url'); db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 403

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth'))

@socketio.on('join')
def on_join(data): 
    room = str(data.get('chat_id') or data.get('channel_id') or f"post_{data.get('post_id')}")
    join_room(room)

@socketio.on('send_msg')
def handle_msg(data):
    u = User.query.filter_by(username=session.get('user')).first()
    if not u: return
    target = data.get('target', '').lower()
    channel_id = data.get('channel_id')
    message = data.get('message', '').strip()
    if not message: return
    if channel_id:
        channel = db.session.get(Channel, channel_id)
        if channel and (channel.created_by == u.username or u.username == 'wetmo'):
            msg = ChannelMessage(channel_id=channel_id, sender=u.username, content=message)
            db.session.add(msg); db.session.commit()
            emit('receive_channel_msg', {
                'id': msg.id, 'channel_id': channel_id, 'sender': u.username, 
                'message': message, 'verified': u.is_verified, 'verification_type': u.verification_type, 
                'user_badge': u.user_badge, 'avatar_data': u.avatar_data, 'badge': u.status_icon, 
                'timestamp': msg.timestamp.strftime('%H:%M')
            }, room=str(channel_id))
    elif target and target != "world":
        u.msg_count += 1
        cid = "-".join(sorted([u.username, target]))
        msg = Message(chat_id=cid, sender=u.username, content=message)
        db.session.add(msg); db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': message, 'verified': u.is_verified, 
                            'verification_type': u.verification_type, 'user_badge': u.user_badge, 
                            'avatar_data': u.avatar_data, 'badge': u.status_icon}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=2500, debug=True)
