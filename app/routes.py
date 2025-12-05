from flask import render_template, request, jsonify, Blueprint
from app import db
from app.models import DesignTask, User
from flask_login import login_required, current_user
import uuid
from app.tasks import run_primer_design

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/api/design', methods=['POST'])
def design_primers():
    """API endpoint для запуска дизайна праймеров."""
    data = request.json
    
    # Определяем user_id
    user_id = None
    
    if current_user.is_authenticated:
        # Если пользователь залогинен, используем его ID
        user_id = current_user.id
    else:
        # Иначе используем тестового пользователя
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(username='test', email='test@example.com')
            test_user.set_password('test123')
            db.session.add(test_user)
            db.session.commit()
        user_id = test_user.id
    
    # Создаем задачу в базе данных
    task = DesignTask(
        task_id=str(uuid.uuid4()),
        user_id=user_id,
        target_name=data.get('target_name', 'Unknown'),
        target_sequence=data.get('target_sequence', ''),
        parameters=data.get('parameters', {}),
        status='pending'
    )
    db.session.add(task)
    db.session.commit()
    
    # Запускаем фоновую задачу Celery
    run_primer_design.delay(task.task_id)
    
    return jsonify({
        'success': True,
        'task_id': task.task_id,
        'message': 'Задача запущена'
    })

@bp.route('/api/task/<task_id>')
def get_task_status(task_id):
    """Получение статуса задачи."""
    task = DesignTask.query.filter_by(task_id=task_id).first_or_404()
    
    # Проверяем права доступа (если пользователь залогинен)
    if current_user.is_authenticated and task.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'status': task.status,
        'progress': task.get_progress(),
        'results': task.results if task.status == 'completed' else None,
        'error': task.error_message if task.status == 'failed' else None
    })

@bp.route('/api/download/<task_id>')
# @login_required
def download_results(task_id):
    """Скачивание результатов в формате JSON."""
    task = DesignTask.query.filter_by(task_id=task_id).first_or_404()
    
    if task.status != 'completed':
        return jsonify({'error': 'Задача еще не завершена'}), 400
    
    return jsonify(task.results)

@bp.route('/api/my-tasks')
# @login_required
def get_my_tasks():
    """Получение списка задач пользователя."""
    tasks = DesignTask.query.order_by(DesignTask.created_at.desc())\
                           .limit(50).all()
    
    return jsonify([{
        'task_id': task.task_id,
        'target_name': task.target_name,
        'status': task.status,
        'created_at': task.created_at.isoformat(),
        'completed_at': task.completed_at.isoformat() if task.completed_at else None
    } for task in tasks])

@bp.route('/results/<task_id>')
# @login_required
def view_results(task_id):
    """HTML страница с результатами."""
    task = DesignTask.query.filter_by(task_id=task_id).first_or_404()
    
    if task.status != 'completed':
        return render_template('task_in_progress.html', 
                             task_id=task_id,
                             progress=task.get_progress(),
                             status=task.status,
                             task=task)
    
    return render_template('results.html', 
                         results=task.results,
                         task_id=task_id)