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
    auth_code_expires = db.Column(db.DateTime) # Срок жизни кода
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
    # Админ
    if not User.query.filter_by(username="wetmo").first():
        db.session.add(User(username="wetmo", password=generate_password_hash("13681368"), is_verified=True, msg_count=1000))
    # Бот авторизации
    if not User.query.filter_by(username="wetmo_auth").first():
        db.session.add(User(username="wetmo_auth", password=generate_password_hash("internal_pass"), is_verified=True, msg_count=10000))
    db.session.commit()

def send_system_msg(target_username, text):
    cid = "-".join(sorted(["wetmo_auth", target_username.lower()]))
    msg = Message(chat_id=cid, sender="wetmo_auth", content=text)
    db.session.add(msg)
    db.session.commit()
    # Отправляем через сокет для мгновенного обновления у пользователя
    socketio.emit('receive_msg', {
        'sender': 'wetmo_auth',
        'message': text,
        'verified': True,
        'badge': ""
    }, room=cid)

# --- PWA ---
@app.route('/manifest.json')
def manifest():
    return {
        "name": "WETMO", "short_name": "WETMO", "start_url": "/", "display": "standalone",
        "background_color": "#050505", "theme_color": "#53fc18",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/5968/5968756.png", "sizes": "512x512", "type": "image/png"}]
    }

@app.route('/sw.js')
def sw():
    response = make_response("self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));")
    response.mimetype = 'application/javascript'
    return response

# --- API ДЛЯ СЕРВИСОВ ---
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
            user.auth_code = None # Одноразовый код
            db.session.commit()
            return jsonify({"status": "success", "message": "Verified"}), 200
        return jsonify({"status": "error", "message": "Code expired"}), 401
    return jsonify({"status": "error", "message": "Invalid code"}), 401

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
            if not u or not check_password_hash(u.password, pw): return "Ошибка данных", 401
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
        return "Неверный или просроченный код", 400
    return render_template('index.html', mode='verify')

@app.route('/admin')
def admin():
    u = User.query.filter_by(username=session.get('user')).first()
    if not u or u.username != 'wetmo': abort(403)
    return render_template('index.html', user=u, all_users=User.query.all(), mode='admin')

@app.route('/admin/verify/<int:uid>')
def admin_v(uid):
    u = User.query.filter_by(username=session.get('user')).first()
    if u and u.username == 'wetmo':
        t = User.query.get(uid); t.is_verified = not t.is_verified; db.session.commit()
    return redirect(url_for('admin'))

@app.route('/set_badge', methods=['POST'])
def set_badge():
    u = User.query.filter_by(username=session.get('user')).first()
    if u and u.msg_count >= 1000:
        u.status_icon = request.json.get('badge_url'); db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 403

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth'))

# --- SOCKETS ---
@socketio.on('join')
def on_join(data): join_room(str(data['chat_id']))

@socketio.on('send_msg')
def handle_msg(data):
    u = User.query.filter_by(username=session.get('user')).first()
    target = data.get('target', '').lower()
    if u and data.get('message') and target: # Исправлено: можно писать боту
        u.msg_count += 1; cid = "-".join(sorted([u.username, target]))
        db.session.add(Message(chat_id=cid, sender=u.username, content=data['message']))
        db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': data['message'], 'verified': u.is_verified, 'badge': u.status_icon}, room=cid)

@socketio.on('typing_start')
def typing_start(data):
    u = session.get('user')
    target = data.get('target', '').lower()
    if u and target:
        cid = "-".join(sorted([u, target]))
        emit('is_typing', {'from': u}, room=cid)

@socketio.on('typing_stop')
def typing_stop(data):
    u = session.get('user')
    target = data.get('target', '').lower()
    if u and target:
        cid = "-".join(sorted([u, target]))
        emit('stop_typing', room=cid)

@socketio.on('mark_read')
def mark_read(data):
    chat_id = data.get('chat_id'); sender = data.get('sender'); u = session.get('user')
    if u and sender and u.lower() != sender.lower():
        Message.query.filter_by(chat_id=chat_id, sender=sender, read=False).update({'read': True})
        db.session.commit()
        emit('read_receipt', {'chat_id': chat_id, 'sender': sender}, room=chat_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
