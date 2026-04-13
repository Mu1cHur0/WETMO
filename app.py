import os
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_kick_style_v9'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# --- МОДЕЛИ ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False) # Права админа
    is_verified = db.Column(db.Boolean, default=False) # Галочка Kick

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(100), nullable=False)
    sender = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

def get_chat_id(u1, u2):
    return "-".join(sorted([u1.lower(), u2.lower()]))

# --- РОУТЫ ---

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    u = User.query.filter_by(username=session['user']).first()
    return render_template('index.html', user=u, mode='chat')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session: return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        if User.query.filter_by(username=username).first(): error = "Ник занят!"
        else:
            # Если пользователей нет, первый будет админом
            is_first = User.query.count() == 0
            new_user = User(username=username, password=generate_password_hash(password), is_admin=is_first)
            db.session.add(new_user); db.session.commit()
            session['user'] = username
            return redirect(url_for('index'))
    return render_template('index.html', mode='auth', auth_type='register', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session: return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user'] = username
            return redirect(url_for('index'))
        error = "Ошибка входа"
    return render_template('index.html', mode='auth', auth_type='login', error=error)

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect(url_for('login'))
    current_user = User.query.filter_by(username=session['user']).first()
    if not current_user or not current_user.is_admin:
        return "Доступ запрещен", 403
    users = User.query.all()
    return render_template('index.html', mode='admin', all_users=users, user=current_user)

@app.route('/admin/verify/<int:user_id>')
def toggle_verify(user_id):
    if 'user' not in session: return redirect(url_for('login'))
    admin = User.query.filter_by(username=session['user']).first()
    if admin and admin.is_admin:
        target = User.query.get(user_id)
        if target:
            target.is_verified = not target.is_verified
            db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/im/<target_user>')
def direct_chat(target_user):
    if 'user' not in session: return redirect(url_for('login'))
    u = User.query.filter_by(username=session['user']).first()
    target_u = User.query.filter_by(username=target_user.lower()).first()
    if not target_u or u.username == target_u.username: return redirect(url_for('index'))
    
    chat_id = get_chat_id(u.username, target_u.username)
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp.asc()).all()
    
    # Для отображения галочек в чате подтянем инфу о собеседнике
    return render_template('index.html', user=u, target=target_u, messages=messages, chat_id=chat_id, mode='chat')

@app.route('/logout')
def logout():
    session.pop('user', None); return redirect(url_for('login'))

# --- SOCKETS ---
@socketio.on('join')
def on_join(data):
    if 'chat_id' in data: join_room(data['chat_id'])
    if 'user' in session: join_room(f"user_{session['user'].lower()}")

@socketio.on('send_direct')
def handle_direct(data):
    if 'user' not in session: return
    me, target, chat_id = session['user'].lower(), data['target'].lower(), data['chat_id']
    if chat_id != get_chat_id(me, target): return
    content = data.get('message', '').strip()
    if content:
        msg = Message(chat_id=chat_id, sender=session['user'], content=content)
        db.session.add(msg); db.session.commit()
        # Проверяем наличие галочки у отправителя для сокетов
        u = User.query.filter_by(username=session['user']).first()
        emit('receive_direct', {'sender': u.username, 'message': content, 'verified': u.is_verified}, room=chat_id)
        emit('new_chat_notification', {'from': u.username}, room=f"user_{target}")

@socketio.on('delete_chat')
def delete_chat(data):
    if 'user' not in session: return
    cid = data['chat_id']
    if session['user'].lower() in cid.split('-'):
        Message.query.filter_by(chat_id=cid).delete()
        db.session.commit()
        emit('chat_deleted', {'chat_id': cid}, room=cid)

if __name__ == '__main__':
    socketio.run(app, debug=True)