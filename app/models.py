from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    tasks = db.relationship('DesignTask', backref='author', lazy='dynamic')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class DesignTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(128), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    target_name = db.Column(db.String(256))
    target_sequence = db.Column(db.Text)
    status = db.Column(db.String(32), default='pending')
    parameters = db.Column(db.JSON)
    results = db.Column(db.JSON)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    download_token = db.Column(db.String(128), unique=True)
    
    def get_progress(self):
        progress_map = {
            'pending': 0,
            'running': 33,
            'analyzing': 66,
            'completed': 100,
            'failed': 100
        }
        return progress_map.get(self.status, 0)