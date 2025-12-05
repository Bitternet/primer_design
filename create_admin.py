from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('✓ Администратор создан')
    else:
        print('✓ Администратор уже существует')