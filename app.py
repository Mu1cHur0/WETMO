import os
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wetmo_ultra_key_777'
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
    # Создаем админа, если пусто
    if not User.query.filter_by(username='admin').first():
        adm = User(username='admin', password=generate_password_hash('1234'), is_admin=True, is_verified=True)
        db.session.add(adm)
        db.session.commit()

def get_chat_id(u1, u2):
    return "-".join(sorted([u1.lower(), u2.lower()]))

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    return render_template('index.html', user=u, mode='chat')

@app.route('/im/<target_user>')
def direct_chat(target_user):
    if 'user' not in session: return redirect(url_for('auth'))
    
    me = User.query.filter_by(username=session['user']).first()
    target = User.query.filter_by(username=target_user.lower()).first()
    
    # Если юзера нет, мы его не выкидываем, а просто показываем пустой чат с этим именем
    # Но для работы сокетов лучше, чтобы юзер существовал.
    chat_id = get_chat_id(me.username, target_user)
    messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp.asc()).all()
    
    return render_template('index.html', user=me, target=target, target_name=target_user, messages=messages, chat_id=chat_id, mode='chat')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password')
        u = User.query.filter_by(username=username).first()
        if u and check_password_hash(u.password, password):
            session['user'] = username
            return redirect(url_for('index'))
        elif not u:
            new_u = User(username=username, password=generate_password_hash(password))
            db.session.add(new_u); db.session.commit()
            session['user'] = username
            return redirect(url_for('index'))
    return render_template('index.html', mode='auth')

@app.route('/admin')
def admin_panel():
    if 'user' not in session: return redirect(url_for('auth'))
    u = User.query.filter_by(username=session['user']).first()
    if not u or not u.is_admin: return "403", 403
    users = User.query.all()
    return render_template('index.html', user=u, all_users=users, mode='admin')

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
    if 'chat_id' in data: join_room(data['chat_id'])
    if 'user' in session: join_room(f"user_{session['user']}")

@socketio.on('send_direct')
def handle_msg(data):
    if 'user' not in session: return
    user = User.query.filter_by(username=session['user']).first()
    msg = Message(chat_id=data['chat_id'], sender=user.username, content=data['message'])
    db.session.add(msg); db.session.commit()
    
    emit('receive_direct', {
        'chat_id': data['chat_id'],
        'sender': user.username,
        'message': data['message'],
        'verified': user.is_verified
    }, room=data['chat_id'])
    
    emit('new_chat_notification', {'from': user.username}, room=f"user_{data['target'].lower()}")

if __name__ == '__main__':
    socketio.run(app)
