import subprocess
import tempfile
import os
from app import Config

def check_specificity(primer_pair, parameters, timeout_seconds=30):
    """Проверка специфичности пары праймеров с BLAST.
    
    Args:
        primer_pair: Словарь с информацией о паре праймеров
        parameters: Параметры проверки
        timeout_seconds: Таймаут выполнения BLAST в секундах
    
    Returns:
        tuple: (bool is_specific, str error_message)
    """
    
    # Проверяем оба праймера
    primers_to_check = ['left_seq', 'right_seq']
    
    for primer_key in primers_to_check:
        if primer_key not in primer_pair:
            continue
            
        primer_seq = primer_pair[primer_key]
        if not primer_seq:
            continue
        
        # Создаём временный файл с последовательностью праймера
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fasta', delete=False) as f:
            f.write(f">primer_{primer_key}\n{primer_seq}")
            temp_file = f.name
        
        try:
            # Запускаем BLAST против всех баз
            for db_name, db_path in Config.BLAST_DB_PATHS.items():
                try:
                    # Проверяем существование базы данных BLAST
                    if not os.path.exists(db_path + ".nhr"):
                        print(f"Предупреждение: BLAST база {db_path} не найдена")
                        continue
                    
                    cmd = [
                        'blastn',
                        '-query', temp_file,
                        '-db', db_path,
                        '-outfmt', '6',
                        '-evalue', '0.001',
                        '-word_size', '7',
                        '-num_alignments', '10',
                        '-max_target_seqs', '10',
                        '-dust', 'no'  # Отключаем фильтрацию низкой сложности
                    ]
                    
                    # Выполняем команду с таймаутом
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds
                    )
                    
                    # Обработка ошибок BLAST
                    if result.returncode != 0:
                        error_msg = f"Ошибка BLAST для праймера {primer_key} в базе {db_name}: {result.stderr[:200]}"
                        print(f"    {error_msg}")
                        # Продолжаем проверку других баз
                        continue
                    
                    # Если есть значимые совпадения, праймер не специфичен
                    if result.stdout.strip():
                        lines = result.stdout.strip().split('\n')
                        print(f"    Найдено {len(lines)} совпадений для {primer_key} в базе {db_name}")
                        return False, f"Найдены совпадения для {primer_key} в базе {db_name}"
                        
                except subprocess.TimeoutExpired:
                    error_msg = f"Таймаут ({timeout_seconds} сек) при проверке праймера {primer_key} в базе {db_name}"
                    print(f"    {error_msg}")
                    return False, error_msg
                    
                except FileNotFoundError:
                    error_msg = f"Команда blastn не найдена. Убедитесь, что BLAST+ установлен."
                    print(f"    {error_msg}")
                    return False, error_msg
                    
                except Exception as e:
                    error_msg = f"Неожиданная ошибка при проверке праймера {primer_key}: {str(e)}"
                    print(f"    {error_msg}")
                    return False, error_msg
                
        finally:
            # Удаляем временный файл
            try:
                os.unlink(temp_file)
            except Exception as e:
                print(f"    Ошибка при удалении временного файла: {str(e)}")
    
    # Если прошли все проверки без нахождения совпадений
    return True, "Оба праймера специфичны"