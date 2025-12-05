from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from celery import Celery
from .config import Config

# Инициализация расширений
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

# Инициализация Celery с минимальными настройками
celery = Celery(
    __name__, 
    broker=Config.broker_url,
    backend=Config.result_backend,
    include=['app.tasks']
)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

        # Добавляем фильтры для Jinja2
    @app.template_filter('format_datetime')
    def format_datetime(value):
        if not value:
            return ''
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.strftime('%d.%m.%Y %H:%M:%S')
        except:
            return value
    
    @app.template_filter('round')
    def round_filter(value, precision=0):
        try:
            return round(float(value), precision)
        except:
            return value
    
    
    # Инициализация расширений с приложением
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Настройка Celery
    celery.conf.update(app.config)
    
    # Явно устанавливаем настройки для Celery 5.x
    celery.conf.update(
        broker_url=Config.broker_url,
        result_backend=Config.result_backend,
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Europe/Moscow',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 минут
        task_soft_time_limit=25 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=100,
    )
    
    # Регистрация маршрутов
    from app import routes
    app.register_blueprint(routes.bp)
    
    return app