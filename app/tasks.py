from app import create_app, db, celery  # Импортируем create_app!
from app.models import DesignTask
from app.utils.pipeline import run_full_pipeline
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@celery.task(bind=True)
def run_primer_design(self, task_id):
    """Фоновая задача для дизайна праймеров."""
    
    # СОЗДАЁМ КОНТЕКСТ ПРИЛОЖЕНИЯ
    app = create_app()  # Создаём экземпляр Flask приложения
    
    with app.app_context():  # Активируем контекст приложения
        try:
            # Теперь все операции с БД будут работать
            task = DesignTask.query.filter_by(task_id=task_id).first()
            
            if not task:
                logger.error(f"Задача {task_id} не найдена")
                return {'status': 'error', 'message': 'Задача не найдена'}
            
            task.status = 'running'
            db.session.commit()
            
            # Запускаем основной пайплайн
            results = run_full_pipeline(
                target_sequence=task.target_sequence,
                target_name=task.target_name,
                parameters=task.parameters or {}
            )
            
            # Сохраняем результаты
            task.status = 'completed'
            task.results = results
            db.session.commit()
            
            logger.info(f"Задача {task_id} успешно завершена")
            return {'status': 'success', 'results': results}
            
        except Exception as e:
            logger.error(f"Ошибка в задаче {task_id}: {str(e)}")
            
            # Важно: обработка ошибок тоже должна быть внутри контекста!
            if 'task' in locals() and task:
                task.status = 'failed'
                task.error_message = str(e)
                db.session.commit()
            
            return {'status': 'error', 'message': str(e)}