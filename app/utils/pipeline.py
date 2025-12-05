import primer3
from app.utils.blast_wrapper import check_specificity
from app.utils.viennarna_analyzer import ViennaRNAAnalyzer
from app.utils.reporters import generate_report
from datetime import datetime

def run_full_pipeline(target_sequence, target_name, parameters):
    """Основной пайплайн дизайна праймеров."""
    
    print(f"[+] Запуск пайплайна для мишени: {target_name}")
    print(f"[+] Длина мишени: {len(target_sequence)} нуклеотидов")
    
    # 1. Дизайн с Primer3
    primer3_params = {
        'SEQUENCE_TEMPLATE': target_sequence,
        'SEQUENCE_ID': target_name,
        'PRIMER_OPT_SIZE': parameters.get('primer_size', 20),
        'PRIMER_MIN_SIZE': parameters.get('min_size', 18),
        'PRIMER_MAX_SIZE': parameters.get('max_size', 25),
        'PRIMER_OPT_TM': parameters.get('tm', 60.0),
        'PRIMER_MIN_TM': parameters.get('min_tm', 58.0),
        'PRIMER_MAX_TM': parameters.get('max_tm', 62.0),
        'PRIMER_PRODUCT_SIZE_RANGE': parameters.get('product_range', "100-300"),
        'PRIMER_NUM_RETURN': 50,
    }
    
    # Глобальные параметры Primer3
    global_args = {
        'PRIMER_TASK': 'generic',
        'PRIMER_PICK_LEFT_PRIMER': 1,
        'PRIMER_PICK_RIGHT_PRIMER': 1,
        'PRIMER_PICK_INTERNAL_OLIGO': 0,
        'PRIMER_EXPLAIN_FLAG': 1,
    }
    
    print(f"[+] Этап 1: Дизайн праймеров с Primer3...")
    
    # Пробуем новый синтаксис primer3-py >= 2.0
    try:
        primer3_result = primer3.designPrimers(primer3_params, global_args)
    except TypeError:
        # Если не поддерживается 2 аргумента, пробуем старый синтаксис
        all_params = {**primer3_params, **global_args}
        primer3_result = primer3.designPrimers(all_params)
    
    # Извлекаем результаты Primer3
    primers = []
    total_designed = primer3_result.get('PRIMER_PAIR_NUM_RETURNED', 0)
    
    print(f"[+] Создано пар праймеров: {total_designed}")
    
    if total_designed == 0:
        raise ValueError("Primer3 не смог создать праймеры для данной мишени")
    
    for i in range(total_designed):
        primer_pair = {
            'id': f"P{i+1:03d}",
            'left_seq': primer3_result.get(f'PRIMER_LEFT_{i}_SEQUENCE', ''),
            'right_seq': primer3_result.get(f'PRIMER_RIGHT_{i}_SEQUENCE', ''),
            'left_tm': round(primer3_result.get(f'PRIMER_LEFT_{i}_TM', 0), 2),
            'right_tm': round(primer3_result.get(f'PRIMER_RIGHT_{i}_TM', 0), 2),
            'product_size': primer3_result.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', 0),
            'pair_penalty': round(primer3_result.get(f'PRIMER_PAIR_{i}_PENALTY', 0), 2),
            'left_gc': round(primer3_result.get(f'PRIMER_LEFT_{i}_GC_PERCENT', 0), 1),
            'right_gc': round(primer3_result.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', 0), 1),
        }
        primers.append(primer_pair)
    
    # 2. Проверка специфичности BLAST
    print(f"[+] Этап 2: Проверка специфичности с BLAST...")
    specific_primers = []
    
    for primer in primers[:20]:  # Проверяем только 20 лучших
        is_specific, _ = check_specificity(primer, parameters)
        if is_specific:
            specific_primers.append(primer)
    
    print(f"[+] Прошло проверку BLAST: {len(specific_primers)} из {len(primers[:20])}")
    
    if not specific_primers:
        raise ValueError("Не найдено специфичных праймеров")
    
    # 3. Анализ ViennaRNA
    print(f"[+] Этап 3: Термодинамический анализ (ViennaRNA)...")
    analyzer = ViennaRNAAnalyzer(
        temperature=parameters.get('temperature', 60.0),
        sodium=parameters.get('na_conc', 0.05),
        magnesium=parameters.get('mg_conc', 0.002)
    )
    
    analyzed_primers = []
    
    for primer in specific_primers[:10]:  # Анализируем только 10 лучших
        viennarna_results = analyzer.analyze_primer_pair(
            forward_seq=primer['left_seq'],
            reverse_seq=primer['right_seq'],
            target_seq=target_sequence
        )
        primer.update(viennarna_results)
        analyzed_primers.append(primer)
    
    print(f"[+] Проанализировано ViennaRNA: {len(analyzed_primers)} праймеров")
    
    # 4. Ранжирование
    ranked_primers = sorted(analyzed_primers, 
                          key=lambda x: x.get('stability_score', 0), 
                          reverse=True)
    
    for primer in analyzed_primers:
        raw_score = primer.get('stability_score', 0)

        if raw_score > 100:
            primer['stability_score'] = 100

    # 5. Классификация праймеров
    for primer in ranked_primers[:5]:
        score = primer.get('stability_score', 0)
        if score >= 80:
            primer['status'] = 'recommended'
        elif score >= 60:
            primer['status'] = 'acceptable'
        elif score >= 40:
            primer['status'] = 'marginal'
        else:
            primer['status'] = 'not_recommended'
    
    # 6. Генерация отчёта (ИСПРАВЛЕННЫЙ ВЫЗОВ - только 2 аргумента)
    print(f"[+] Генерация отчёта...")
    report_data = generate_report(ranked_primers[:5], target_name)
    
    return {
        'target_name': target_name,
        'target_sequence_preview': target_sequence[:100] + "..." if len(target_sequence) > 100 else target_sequence,
        'target_length': len(target_sequence),
        'primers': ranked_primers[:5],
        'summary': {
            'total_designed': total_designed,
            'passed_blast': len(specific_primers),
            'fully_analyzed': len(analyzed_primers),
            'recommended': len([p for p in ranked_primers[:5] if p.get('status') == 'recommended'])
        },
        'parameters_used': parameters,
        'report': report_data,
        'timestamp': datetime.utcnow().isoformat()
    }