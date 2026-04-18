import os, random
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

os.makedirs('templates', exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_gateway_v14'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

EVENT_BADGES = [
    "https://img.icons8.com/ios-filled/100/53fc18/crown.png",
    "https://img.icons8.com/ios-filled/100/53fc18/shield.png",
    "https://img.icons8.com/ios-filled/100/53fc18/sword.png",
    "https://img.icons8.com/ios-filled/100/53fc18/diamond.png",
    "https://img.icons8.com/ios-filled/100/53fc18/christmas-star.png",
    "https://img.icons8.com/ios-filled/100/53fc18/skull.png",
    "https://img.icons8.com/ios-filled/100/53fc18/fire-element.png",
    "https://img.icons8.com/ios-filled/100/53fc18/water-element.png",
    "https://img.icons8.com/ios-filled/100/53fc18/lightning-bolt.png",
    "https://img.icons8.com/ios-filled/100/53fc18/eye.png",
    "https://img.icons8.com/ios-filled/100/53fc18/dragon.png",
    "https://img.icons8.com/ios-filled/100/53fc18/wizard.png",
    "https://img.icons8.com/ios-filled/100/53fc18/knight-shield.png",
    "https://img.icons8.com/ios-filled/100/53fc18/potion.png",
    "https://img.icons8.com/ios-filled/100/53fc18/book.png",
    "https://img.icons8.com/ios-filled/100/53fc18/key.png",
    "https://img.icons8.com/ios-filled/100/53fc18/lock.png",
    "https://img.icons8.com/ios-filled/100/53fc18/globe.png",
    "https://img.icons8.com/ios-filled/100/53fc18/ghost.png",
    "https://img.icons8.com/ios-filled/100/53fc18/robot.png"
]

CHANNEL_BADGES = [
    {"name": "corona", "url": "https://img.icons8.com/ios-filled/50/ffd700/crown.png", "color": "#ffd700"},
    {"name": "star", "url": "https://img.icons8.com/ios-filled/50/53fc18/star.png", "color": "#53fc18"},
    {"name": "fire", "url": "https://img.icons8.com/ios-filled/50/ff4500/fire-element.png", "color": "#ff4500"},
    {"name": "diamond", "url": "https://img.icons8.com/ios-filled/50/00ffff/diamond.png", "color": "#00ffff"}
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    auth_code = db.Column(db.String(10))
    status_icon = db.Column(db.String(500), default="")
    msg_count = db.Column(db.Integer, default=0)

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

with app.app_context():
    db_path = 'database.db'
    if os.path.exists(db_path):
        try:
            Channel.query.first()
        except:
            os.remove(db_path)
            print("🔄 Старая БД удалена, создаю новую...")
    
    db.create_all()
    
    if not User.query.filter_by(username="wetmo").first():
        db.session.add(User(username="wetmo", password=generate_password_hash("13681368"), is_verified=True, msg_count=1000))
    if not User.query.filter_by(username="wetmo_auth").first():
        db.session.add(User(username="wetmo_auth", password=generate_password_hash("internal_pass"), is_verified=True))
    if not Channel.query.filter_by(name="новости").first():
        ch = Channel(name="новости", description="Официальные новости WETMO", created_by="wetmo", is_public=True, is_verified=True)
        db.session.add(ch)
        db.session.commit()
        db.session.add(ChannelSubscriber(channel_id=ch.id, username="wetmo"))
    db.session.commit()

def send_system_msg(target_username, text):
    cid = "-".join(sorted(["wetmo_auth", target_username.lower()]))
    db.session.add(Message(chat_id=cid, sender="wetmo_auth", content=text))
    db.session.commit()

# --- API ---
@app.route('/api/search_users')
def search_users():
    if 'user' not in session: return jsonify([])
    query = request.args.get('q', '').strip().lower()
    if len(query) < 1: return jsonify([])
    current_user = session['user']
    users = User.query.filter(User.username.contains(query), User.username != current_user, ~User.username.in_(['wetmo_auth'])).limit(10).all()
    return jsonify([{'username': u.username, 'is_verified': u.is_verified} for u in users])

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

# --- ОСНОВНЫЕ МАРШРУТЫ ---
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
    
    return render_template('index.html', user=u, contacts=contacts, channels=channels, mode='chat', event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

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
    
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, channels=channels, chat_id=cid, mode='chat', event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

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
    
    posts_with_reactions = []
    for msg in msgs:
        likes = Reaction.query.filter_by(post_id=msg.id, reaction_type='like').count()
        dislikes = Reaction.query.filter_by(post_id=msg.id, reaction_type='dislike').count()
        user_reaction = Reaction.query.filter_by(post_id=msg.id, username=u.username).first()
        posts_with_reactions.append({
            'msg': msg,
            'likes': likes,
            'dislikes': dislikes,
            'user_reaction': user_reaction.reaction_type if user_reaction else None
        })
    
    return render_template('index.html', user=u, channel=channel, posts_with_reactions=posts_with_reactions, 
                          contacts=contacts, channels=channels, mode='channel', event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

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
    
    return render_template('index.html', user=u, post=post, channel=channel, comments=comments, 
                          likes=likes, dislikes=dislikes, user_reaction=user_reaction,
                          contacts=contacts, channels=channels, mode='post', event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    t = request.args.get('type', 'login')
    if request.method == 'POST':
        name = request.form.get('username', '').strip().lower()
        pw = request.form.get('password')
        u = User.query.filter_by(username=name).first()
        if t == 'register':
            if u: return "Ник занят", 400
            new_u = User(username=name, password=generate_password_hash(pw))
            db.session.add(new_u); db.session.commit()
            session['user'] = name
            return redirect(url_for('index'))
        else:
            if not u or not check_password_hash(u.password, pw): return "Ошибка данных", 401
            if u.username == 'wetmo': session['user'] = 'wetmo'; return redirect(url_for('index'))
            code = f"{random.randint(100,999)}-{random.randint(100,999)}"
            u.auth_code = code; db.session.commit()
            send_system_msg(name, f"🛡 **Вход в аккаунт WETMO**\nКод: `{code}`")
            session['temp_user'] = name
            return redirect(url_for('verify'))
    return render_template('index.html', mode='auth', auth_type=t, user=None, event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    name = session.get('temp_user')
    if not name: return redirect(url_for('auth'))
    if request.method == 'POST':
        u = User.query.filter_by(username=name).first()
        if request.form.get('code') == u.auth_code:
            session['user'] = name; session.pop('temp_user')
            return redirect(url_for('index'))
        return "Неверный код", 400
    return render_template('index.html', mode='verify', user=None, event_badges=EVENT_BADGES, channel_badges=CHANNEL_BADGES)

@app.route('/admin')
def admin():
    u = User.query.filter_by(username=session.get('user')).first()
    if not u or u.username != 'wetmo': abort(403)
    tab = request.args.get('tab', 'users')
    users = User.query.all()
    channels = Channel.query.all()
    return render_template('index.html', user=u, all_users=users, all_channels=channels, tab=tab, mode='admin', channel_badges=CHANNEL_BADGES, event_badges=EVENT_BADGES)

@app.route('/admin/verify/<int:uid>')
def admin_v(uid):
    if session.get('user') == 'wetmo':
        t = db.session.get(User, uid)
        if t: t.is_verified = not t.is_verified; db.session.commit()
    return redirect(url_for('admin', tab='users'))

@app.route('/admin/delete/<int:uid>')
def admin_delete(uid):
    if session.get('user') == 'wetmo':
        t = db.session.get(User, uid)
        if t and t.username not in ['wetmo', 'wetmo_auth']:
            Message.query.filter((Message.sender == t.username) | (Message.chat_id.contains(t.username))).delete()
            db.session.delete(t); db.session.commit()
    return redirect(url_for('admin', tab='users'))

@app.route('/admin/channel/verify/<int:channel_id>')
def admin_channel_verify(channel_id):
    if session.get('user') == 'wetmo':
        channel = db.session.get(Channel, channel_id)
        if channel:
            channel.is_verified = not channel.is_verified
            db.session.commit()
    return redirect(url_for('admin', tab='channels'))

@app.route('/admin/channel/badge/<int:channel_id>', methods=['POST'])
def admin_channel_badge(channel_id):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    data = request.json
    badge = data.get('badge', '')
    channel = db.session.get(Channel, channel_id)
    if channel:
        channel.badge = badge
        db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/admin/channel/delete/<int:channel_id>', methods=['DELETE'])
def admin_delete_channel(channel_id):
    if session.get('user') != 'wetmo': return jsonify({"error": "Forbidden"}), 403
    channel = db.session.get(Channel, channel_id)
    if channel:
        ChannelMessage.query.filter_by(channel_id=channel_id).delete()
        ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
        db.session.delete(channel)
        db.session.commit()
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
                'message': message, 'verified': u.is_verified, 'badge': u.status_icon, 
                'timestamp': msg.timestamp.strftime('%H:%M')
            }, room=str(channel_id))
    elif target and target != "wetmo_auth":
        u.msg_count += 1
        cid = "-".join(sorted([u.username, target]))
        msg = Message(chat_id=cid, sender=u.username, content=message)
        db.session.add(msg); db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': message, 'verified': u.is_verified, 'badge': u.status_icon}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
