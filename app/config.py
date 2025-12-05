import os

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    
    # База данных
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://primer_user:12345678@localhost/primer_design_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Celery - НОВЫЕ НАЗВАНИЯ ДЛЯ Celery 5.x
    broker_url = 'redis://localhost:6379/0'          # Было: CELERY_BROKER_URL
    result_backend = 'redis://localhost:6379/0'      # Было: CELERY_RESULT_BACKEND
    
    # Загрузка файлов
    UPLOAD_FOLDER = os.path.join(basedir, '..', 'data', 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB
    
    # BLAST базы данных - ОБНОВЛЕННЫЕ ПУТИ
    BLAST_DB_PATHS = {
        'human': '/opt/primer_design/data/blast_db/human_grch38',
        'viruses': '/opt/primer_design/data/blast_db/nt_viruses',  # Исправлен путь
    }
    
    # ViennaRNA
    VIENNARNA_TEMPERATURE = 60.0
    VIENNARNA_SODIUM = 0.05
    VIENNARNA_MAGNESIUM = 0.002
    
    # Параметры пайплайна
    PIPELINE_TOP_FOR_VIENNARNA = 10
    PRIMER3_PRODUCT_SIZE_RANGE = "100-300"
    
    @staticmethod
    def init_app(app):
        """Инициализация приложения с конфигурацией."""
        # Создание папок, если они не существуют
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        # Проверка наличия BLAST баз данных
        for db_name, db_path in Config.BLAST_DB_PATHS.items():
            # Проверяем существование основных файлов базы
            db_exists = (
                os.path.exists(f"{db_path}.nhr") or 
                os.path.exists(f"{db_path}.nin") or 
                os.path.exists(f"{db_path}.nsq") or
                os.path.exists(f"{db_path}.00.nhr")  # Для многотомных баз
            )
            
            if not db_exists:
                print(f"ВНИМАНИЕ: BLAST база '{db_name}' не найдена по пути: {db_path}")
                print(f"  Проверьте символические ссылки: ls -la /opt/primer_design/data/blast_db/")
            else:
                print(f"OK: BLAST база '{db_name}' найдена")
        
        # Создание других необходимых директорий
        data_dir = os.path.join(basedir, '..', 'data')
        blast_db_dir = os.path.join(data_dir, 'blast_db')
        results_dir = os.path.join(data_dir, 'results')
        
        for directory in [data_dir, blast_db_dir, results_dir]:
            os.makedirs(directory, exist_ok=True)
            print(f"Директория создана/проверена: {directory}")