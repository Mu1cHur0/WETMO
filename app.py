import os, random
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, make_response
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_gateway_v15'
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
    "https://img.icons8.com/ios-filled/100/53fc18/skull.png"
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    auth_code = db.Column(db.String(10))
    auth_code_expires = db.Column(db.DateTime)
    status_icon = db.Column(db.String(500), default="")
    msg_count = db.Column(db.Integer, default=0)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="wetmo").first():
        db.session.add(User(username="wetmo", password=generate_password_hash("13681368"), is_verified=True, msg_count=1000))
    if not User.query.filter_by(username="wetmo_auth").first():
        db.session.add(User(username="wetmo_auth", password=generate_password_hash("internal_pass"), is_verified=True, msg_count=10000))
    db.session.commit()

def send_system_msg(target_username, text):
    cid = "-".join(sorted(["wetmo_auth", target_username.lower()]))
    msg = Message(chat_id=cid, sender="wetmo_auth", content=text)
    db.session.add(msg)
    db.session.commit()
    socketio.emit('receive_msg', {
        'sender': 'wetmo_auth',
        'message': text,
        'verified': True,
        'badge': ""
    }, room=cid)

# --- БРЕНДИНГ И PWA ---
@app.route('/icon.svg')
def icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" fill="#53fc18" rx="22"/>
        <text x="50" y="72" font-size="55" text-anchor="middle" fill="#000000" font-weight="900" font-family="Arial, sans-serif">W</text>
    </svg>'''
    return make_response(svg, 200, {'Content-Type': 'image/svg+xml'})

@app.route('/manifest.json')
def manifest():
    return {
        "name": "WETMO MESSENGER", "short_name": "WETMO", "start_url": "/", "display": "standalone",
        "background_color": "#050505", "theme_color": "#53fc18",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "maskable"}]
    }

# --- API ---
@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    data = request.json
    target = data.get('username', '').lower()
    service = data.get('service', 'External Service')
    user = User.query.filter_by(username=target).first()
    if not user: return jsonify({"error": "User not found"}), 404
    
    code = f"{random.randint(100,999)}-{random.randint(100,999)}"
    user.auth_code = code
    user.auth_code_expires = datetime.utcnow() + timedelta(minutes=5)
    db.session.commit()
    
    msg = f"🔑 **Код подтверждения {service}**\n\nВаш код: `{code}`\n\n*Срок действия: 5 минут.*"
    send_system_msg(target, msg)
    return jsonify({"status": "sent"}), 200

@app.route('/api/verify_code', methods=['POST'])
def api_verify_code():
    data = request.json
    username = data.get('username', '').lower()
    code = data.get('code', '')
    user = User.query.filter_by(username=username).first()
    
    if user and user.auth_code == code:
        if user.auth_code_expires and user.auth_code_expires > datetime.utcnow():
            user.auth_code = None
            db.session.commit()
            return jsonify({"status": "success"}), 200
    return jsonify({"status": "error", "message": "Invalid or expired code"}), 401

# --- МАРШРУТЫ ---
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    return render_template('index.html', user=u, contacts=contacts, mode='chat', event_badges=EVENT_BADGES)

@app.route('/im/<target>')
def chat(target):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    t = User.query.filter_by(username=target.lower()).first()
    if not t or u.username == t.username: return redirect(url_for('index'))
    cid = "-".join(sorted([u.username, t.username]))
    msgs = Message.query.filter_by(chat_id=cid).order_by(Message.timestamp.asc()).all()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    names.add(t.username)
    contacts = User.query.filter(User.username.in_(list(names))).all()
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, chat_id=cid, mode='chat', event_badges=EVENT_BADGES)

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
            if not u or not check_password_hash(u.password, pw): return "Ошибка", 401
            if u.username == 'wetmo':
                session['user'] = 'wetmo'; return redirect(url_for('index'))
            code = f"{random.randint(100,999)}-{random.randint(100,999)}"
            u.auth_code = code
            u.auth_code_expires = datetime.utcnow() + timedelta(minutes=5)
            db.session.commit()
            send_system_msg(name, f"🛡 **Вход в аккаунт WETMO**\nКод: `{code}`")
            session['temp_user'] = name
            return redirect(url_for('verify'))
    return render_template('index.html', mode='auth', auth_type=t)

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    name = session.get('temp_user')
    if not name: return redirect(url_for('auth'))
    if request.method == 'POST':
        u = User.query.filter_by(username=name).first()
        if request.form.get('code') == u.auth_code and u.auth_code_expires > datetime.utcnow():
            session['user'] = name; session.pop('temp_user')
            return redirect(url_for('index'))
        return "Неверный код", 400
    return render_template('index.html', mode='verify')

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth'))

@socketio.on('join')
def on_join(data): join_room(str(data['chat_id']))

@socketio.on('send_msg')
def handle_msg(data):
    u = User.query.filter_by(username=session.get('user')).first()
    target = data.get('target', '').lower()
    # ИСПРАВЛЕНО: Убрано условие target != "wetmo_auth"
    if u and data.get('message') and target:
        u.msg_count += 1
        cid = "-".join(sorted([u.username, target]))
        db.session.add(Message(chat_id=cid, sender=u.username, content=data['message']))
        db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': data['message'], 'verified': u.is_verified, 'badge': u.status_icon}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
