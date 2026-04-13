import os
from flask import Flask, render_template, request, session, redirect, url_for, abort
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_tabs_v1'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def get_chat_id(u1, u2):
    return "-".join(sorted([str(u1).lower(), str(u2).lower()]))

def get_my_contacts(username):
    all_chats = Message.query.filter(Message.chat_id.contains(username.lower())).all()
    contact_names = set()
    for m in all_chats:
        parts = m.chat_id.split('-')
        for p in parts:
            if p != username.lower(): contact_names.add(p)
    return User.query.filter(User.username.in_(list(contact_names))).all()

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    
    u = User.query.filter_by(username=session['user']).first()
    # ЗАПЛАТКА: Если база стерлась, а сессия осталась - выкидываем на логин
    if not u:
        session.pop('user', None)
        return redirect(url_for('auth'))
        
    contacts = get_my_contacts(u.username)
    return render_template('index.html', user=u, contacts=contacts, mode='chat')

@app.route('/im/<target_user>')
def direct_chat(target_user):
    if 'user' not in session: return redirect(url_for('auth'))
    
    me = User.query.filter_by(username=session['user']).first()
    # ЗАПЛАТКА: Если нас нет в базе
    if not me:
        session.pop('user', None)
        return redirect(url_for('auth'))
        
    target = User.query.filter_by(username=target_user.lower()).first()
    if not target or me.username.lower() == target.username.lower(): return redirect(url_for('index'))
    
    cid = get_chat_id(me.username, target.username)
    msgs = Message.query.filter_by(chat_id=cid).order_by(Message.timestamp.asc()).all()
    contacts = get_my_contacts(me.username)
    
    if target.username.lower() not in [c.username.lower() for c in contacts]:
        contacts.append(target)

    return render_template('index.html', user=me, target=target, messages=msgs, contacts=contacts, chat_id=cid, mode='chat')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    auth_type = request.args.get('type', 'login')
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password')
        u = User.query.filter_by(username=username).first()
        if auth_type == 'login':
            if u and check_password_hash(u.password, password):
                session['user'] = username
                return redirect(url_for('index'))
            return "Ошибка логина", 401
        else:
            if u: return "Имя занято", 400
            is_first = User.query.count() == 0
            new_u = User(username=username, password=generate_password_hash(password), is_admin=is_first)
            db.session.add(new_u); db.session.commit()
            session['user'] = username
            return redirect(url_for('index'))
    return render_template('index.html', mode='auth', auth_type=auth_type)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect(url_for('auth'))
    
    u = User.query.filter_by(username=session['user']).first()
    # ЗАПЛАТКА: Для админки тоже
    if not u:
        session.pop('user', None)
        return redirect(url_for('auth'))
        
    if not u.is_admin: abort(403)
    return render_template('index.html', user=u, all_users=User.query.all(), mode='admin')

@app.route('/admin/verify/<int:uid>')
def verify(uid):
    u = User.query.get(uid)
    if u: u.is_verified = not u.is_verified; db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('auth'))

@socketio.on('join')
def on_join(data):
    if 'chat_id' in data: join_room(str(data['chat_id']))

@socketio.on('send_msg')
def handle_msg(data):
    if 'user' not in session: return
    
    u = User.query.filter_by(username=session['user']).first()
    if not u: return # Защита сокетов
    
    target = str(data.get('target', '')).lower()
    content = str(data.get('message', '')).strip()
    if not content or not target: return
    
    cid = get_chat_id(session['user'], target)
    db.session.add(Message(chat_id=cid, sender=session['user'], content=content))
    db.session.commit()
    
    emit('receive_msg', {'sender': u.username, 'message': content, 'verified': u.is_verified}, room=cid)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
