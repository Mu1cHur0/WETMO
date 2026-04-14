import os, random, base64
from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, make_response
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_fix_v1'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- КОНФИГУРАЦИЯ ЭМБЛЕМ ---
ALL_BADGES = [
    {"id": "novice", "name": "НОВИЧОК", "req": 1, "icon": "shield"},
    {"id": "talker", "name": "ГОВОРУН", "req": 20, "icon": "chat"},
    {"id": "speaker", "name": "ОРАТОР", "req": 50, "icon": "mic"},
    {"id": "writer", "name": "ПИСАТЕЛЬ", "req": 100, "icon": "pen"},
    {"id": "master", "name": "МАСТЕР", "req": 250, "icon": "star"},
    {"id": "king", "name": "КОРОЛЬ", "req": 1000, "icon": "crown"},
] + [{"id": f"lvl{i}", "name": f"LVL {i}", "req": i*150, "icon": "star"} for i in range(7, 51)]

# --- СПИСОК КВЕСТОВ ---
def get_user_quests(msg_count):
    return [
        {"name": "Первое слово", "progress": min(msg_count, 1), "target": 1, "reward": "Эмблема Новичок"},
        {"name": "Активный собеседник", "progress": min(msg_count, 100), "target": 100, "reward": "Эмблема Писатель"},
        {"name": "Король чата", "progress": min(msg_count, 1000), "target": 1000, "reward": "Статус Короля"},
    ]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    status_icon = db.Column(db.String(500), default="")
    msg_count = db.Column(db.Integer, default=0)
    auth_code = db.Column(db.String(10))
    auth_code_expires = db.Column(db.DateTime)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="wetmo").first():
        db.session.add(User(username="wetmo", password=generate_password_hash("13681368"), is_verified=True))
    db.session.commit()

# --- SVG ENGINE ---
@app.route('/badge/<badge_id>.svg')
def generate_badge(badge_id):
    badge = next((b for b in ALL_BADGES if b['id'] == badge_id), ALL_BADGES[0])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" rx="20" fill="#53fc18"/>
        <circle cx="50" cy="50" r="30" fill="#000"/>
        <text x="50" y="92" font-size="10" text-anchor="middle" fill="#000" font-weight="900" font-family="Arial">{badge['name']}</text>
    </svg>'''
    return make_response(svg, 200, {'Content-Type': 'image/svg+xml'})

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    contacts = User.query.filter(User.username != u.username).all() # Для теста показываем всех
    return render_template('index.html', user=u, contacts=contacts, quests=get_user_quests(u.msg_count), all_badges=ALL_BADGES, mode='chat')

@app.route('/im/<target>')
def chat(target):
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    t = User.query.filter_by(username=target.lower()).first()
    if not t: return redirect(url_for('index'))
    cid = "-".join(sorted([u.username, t.username]))
    msgs = Message.query.filter_by(chat_id=cid).order_by(Message.timestamp.asc()).all()
    contacts = User.query.all()
    return render_template('index.html', user=u, target=t, messages=msgs, contacts=contacts, chat_id=cid, quests=get_user_quests(u.msg_count), all_badges=ALL_BADGES, mode='chat')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        name = request.form.get('username').lower()
        u = User.query.filter_by(username=name).first()
        if not u:
            u = User(username=name, password=generate_password_hash("123"))
            db.session.add(u); db.session.commit()
        session['user'] = name
        return redirect(url_for('index'))
    return render_template('index.html', mode='auth')

@app.route('/set_badge', methods=['POST'])
def set_badge():
    u = User.query.filter_by(username=session.get('user')).first()
    badge_url = request.json.get('badge_url')
    u.status_icon = badge_url; db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('auth'))

@socketio.on('join')
def on_join(data): join_room(str(data['chat_id']))

@socketio.on('send_msg')
def handle_msg(data):
    u = User.query.filter_by(username=session.get('user')).first()
    target = data.get('target', '').lower()
    if u and target:
        u.msg_count += 1
        cid = "-".join(sorted([u.username, target]))
        db.session.add(Message(chat_id=cid, sender=u.username, content=data['message']))
        db.session.commit()
        emit('receive_msg', {'sender': u.username, 'message': data['message'], 'verified': u.is_verified, 'badge': u.status_icon}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
