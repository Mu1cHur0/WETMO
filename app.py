import os, random, base64
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, make_response
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_ultra_core_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- КОНФИГУРАЦИЯ ЭМБЛЕМ (50 ШТУК) ---
ALL_BADGES = [
    {"id": "novice", "name": "НОВИЧОК", "req": 1, "icon": "shield"},
    {"id": "talker", "name": "ГОВОРУН", "req": 20, "icon": "chat"},
    {"id": "speaker", "name": "ОРАТОР", "req": 50, "icon": "mic"},
    {"id": "writer", "name": "ПИСАТЕЛЬ", "req": 100, "icon": "pen"},
    {"id": "master", "name": "МАСТЕР", "req": 250, "icon": "star"},
    {"id": "expert", "name": "ЭКСПЕРТ", "req": 500, "icon": "expert"},
    {"id": "elite", "name": "ЭЛИТА", "req": 750, "icon": "diamond"},
    {"id": "king", "name": "КОРОЛЬ", "req": 1000, "icon": "crown"},
    {"id": "legend", "name": "ЛЕГЕНДА", "req": 2500, "icon": "legend"},
    {"id": "god", "name": "БОЖЕСТВО", "req": 5000, "icon": "god"},
] + [{"id": f"lvl{i}", "name": f"LVL {i}", "req": i*150, "icon": "star"} for i in range(11, 51)]

# --- МОДЕЛИ ДАННЫХ ---
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
        db.session.add(User(username="wetmo", password=generate_password_hash("13681368"), is_verified=True))
    if not User.query.filter_by(username="wetmo_auth").first():
        db.session.add(User(username="wetmo_auth", password=generate_password_hash("auth_pass"), is_verified=True))
    db.session.commit()

# --- Badge Engine ---
def get_svg_path(icon_type):
    icons = {
        'shield': 'M50,15 L85,30 L85,65 L50,85 L15,65 L15,30 Z',
        'chat': 'M25,40 Q25,25 50,25 Q75,25 75,40 L75,65 Q75,80 50,80 Q25,80 25,65 Z',
        'star': 'M50,15 L58,40 L85,40 L63,55 L72,80 L50,65 L28,80 L37,55 L15,40 L42,40 Z',
        'crown': 'M20,70 L25,35 L40,50 L50,30 L60,50 L75,35 L80,70 Z',
        'diamond': 'M50,15 L80,50 L50,85 L20,50 Z',
        'legend': 'M50,10 L60,40 L90,40 L65,55 L75,85 L50,70 L25,85 L35,55 L10,40 L40,40 Z',
        'expert': 'M50,20 L65,35 L80,20 L70,40 L85,55 L65,50 L50,65 L35,50 L15,55 L30,40 L20,20 L35,35 Z',
        'mic': 'M50,20 L50,55 M40,55 Q50,70 60,55 M50,15 A10,10 0 1,1 50,35 Z',
        'pen': 'M70,20 L80,30 L40,70 L30,70 L30,60 Z'
    }
    return icons.get(icon_type, icons['star'])

@app.route('/badge/<string:badge_id>.svg')
def generate_badge(badge_id):
    badge = next((b for b in ALL_BADGES if b['id'] == badge_id), ALL_BADGES[0])
    path = get_svg_path(badge['icon'])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" rx="20" fill="#53fc18"/>
        <circle cx="50" cy="50" r="35" fill="#050505"/>
        <path d="{path}" fill="#53fc18" stroke="#53fc18" stroke-width="2"/>
        <text x="50" y="90" font-size="8" text-anchor="middle" fill="#000" font-weight="900" font-family="Arial">{badge['name']}</text>
    </svg>'''
    return make_response(svg, 200, {'Content-Type': 'image/svg+xml', 'Cache-Control': 'public, max-age=86400'})

# --- BRANDING ---
@app.route('/icon.svg')
def icon():
    return make_response('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#53fc18"/><text x="50" y="72" font-size="55" text-anchor="middle" fill="#000" font-weight="900">W</text></svg>', 200, {'Content-Type': 'image/svg+xml'})

@app.route('/manifest.json')
def manifest():
    return {"name": "WETMO", "short_name": "WETMO", "start_url": "/", "display": "standalone", "background_color": "#050505", "theme_color": "#53fc18", "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}]}

@app.route('/sw.js')
def sw():
    res = make_response("self.addEventListener('fetch', e => e.respondWith(fetch(e.request)));")
    res.mimetype = 'application/javascript'
    return res

# --- CORE LOGIC ---
def send_system_msg(target, text):
    cid = "-".join(sorted(["wetmo_auth", target.lower()]))
    db.session.add(Message(chat_id=cid, sender="wetmo_auth", content=text))
    db.session.commit()
    socketio.emit('receive_msg', {'sender': 'wetmo_auth', 'message': text, 'verified': True, 'badge': ""}, room=cid)

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    all_m = Message.query.filter(Message.chat_id.contains(u.username)).all()
    names = {p for m in all_m for p in m.chat_id.split('-') if p != u.username}
    contacts = User.query.filter(User.username.in_(list(names))).all()
    return render_template('index.html', user=u, contacts=contacts, all_badges=ALL_BADGES, mode='chat')

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
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, chat_id=cid, all_badges=ALL_BADGES, mode='chat')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    t = request.args.get('type', 'login')
    if request.method == 'POST':
        name, pw = request.form.get('username', '').strip().lower(), request.form.get('password')
        u = User.query.filter_by(username=name).first()
        if t == 'register':
            if u: return "Ник занят", 400
            db.session.add(User(username=name, password=generate_password_hash(pw)))
            db.session.commit(); session['user'] = name
            return redirect(url_for('index'))
        if not u or not check_password_hash(u.password, pw): return "Ошибка", 401
        if name == 'wetmo': session['user'] = 'wetmo'; return redirect(url_for('index'))
        code = f"{random.randint(100,999)}-{random.randint(100,999)}"
        u.auth_code, u.auth_code_expires = code, datetime.utcnow() + timedelta(minutes=5)
        db.session.commit()
        send_system_msg(name, f"🛡 **Вход**\nКод: `{code}`")
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
    return render_template('index.html', mode='verify')

@app.route('/admin')
def admin():
    u = User.query.filter_by(username=session.get('user')).first()
    if not u or u.username != 'wetmo': abort(403)
    return render_template('index.html', user=u, all_users=User.query.all(), mode='admin')

@app.route('/admin/verify/<int:uid>')
def admin_v(uid):
    if session.get('user') == 'wetmo':
        t = User.query.get(uid); t.is_verified = not t.is_verified; db.session.commit()
    return redirect(url_for('admin'))

@app.route('/set_badge', methods=['POST'])
def set_badge():
    u = User.query.filter_by(username=session.get('user')).first()
    badge_url = request.json.get('badge_url')
    # Ищем требование для этого badge_id
    badge_id = badge_url.split('/')[-1].replace('.svg', '')
    badge_data = next((b for b in ALL_BADGES if b['id'] == badge_id), None)
    if u and badge_data and u.msg_count >= badge_data['req']:
        u.status_icon = badge_url; db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"error": "Denied"}), 403

@app.route('/api/send_code', methods=['POST'])
def api_send_code():
    data = request.json
    target, service = data.get('username', '').lower(), data.get('service', 'Service')
    u = User.query.filter_by(username=target).first()
    if not u: return jsonify({"error": "User not found"}), 404
    code = f"{random.randint(100,999)}-{random.randint(100,999)}"
    u.auth_code, u.auth_code_expires = code, datetime.utcnow() + timedelta(minutes=5)
    db.session.commit()
    send_system_msg(target, f"🔑 **Код подтверждения {service}**\n\nВаш код: `{code}`")
    return jsonify({"status": "sent"})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth'))

# --- SOCKETS ---
@socketio.on('join')
def on_join(data): join_room(str(data['chat_id']))

@socketio.on('send_msg')
def handle_msg(data):
    u = User.query.filter_by(username=session.get('user')).first()
    target = data.get('target', '').lower()
    if u and data.get('message') and target:
        u.msg_count += 1
        cid = "-".join(sorted([u.username, target]))
        db.session.add(Message(chat_id=cid, sender=u.username, content=data['message']))
        db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': data['message'], 'verified': u.is_verified, 'badge': u.status_icon}, room=cid)

@socketio.on('typing_start')
def t_start(data):
    u, target = session.get('user'), data.get('target', '').lower()
    if u and target: emit('is_typing', {'from': u}, room="-".join(sorted([u, target])))

@socketio.on('typing_stop')
def t_stop(data):
    u, target = session.get('user'), data.get('target', '').lower()
    if u and target: emit('stop_typing', room="-".join(sorted([u, target])))

@socketio.on('mark_read')
def m_read(data):
    cid, sender, u = data.get('chat_id'), data.get('sender'), session.get('user')
    if u and sender and u.lower() != sender.lower():
        Message.query.filter_by(chat_id=cid, sender=sender, read=False).update({'read': True})
        db.session.commit(); emit('read_receipt', {'chat_id': cid, 'sender': sender}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
