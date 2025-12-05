from datetime import datetime
import json

def generate_report(primers, target_name):
    """Генерация отчёта по результатам анализа праймеров.
    
    Args:
        primers: Список словарей с данными праймеров (максимум 5)
        target_name: Название целевой последовательности
    
    Returns:
        dict: Данные для отчёта
    """
    
    # Статистика по праймерам
    total_primers = len(primers)
    recommended = len([p for p in primers if p.get('status') == 'recommended'])
    acceptable = len([p for p in primers if p.get('status') == 'acceptable'])
    
    # Средние значения
    avg_left_tm = sum(p.get('left_tm', 0) for p in primers) / total_primers if total_primers > 0 else 0
    avg_right_tm = sum(p.get('right_tm', 0) for p in primers) / total_primers if total_primers > 0 else 0
    avg_gc = (sum(p.get('left_gc', 0) for p in primers) + 
              sum(p.get('right_gc', 0) for p in primers)) / (total_primers * 2) if total_primers > 0 else 0
    
    # Формируем HTML отчет
    html_report = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Отчёт: {target_name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .header {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
            .primer-card {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
            .recommended {{ border-left: 5px solid #28a745; }}
            .acceptable {{ border-left: 5px solid #ffc107; }}
            .marginal {{ border-left: 5px solid #fd7e14; }}
            .not-recommended {{ border-left: 5px solid #dc3545; }}
            .sequence {{ font-family: monospace; background: #f8f9fa; padding: 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .score {{ font-size: 24px; font-weight: bold; }}
            .good-score {{ color: #28a745; }}
            .medium-score {{ color: #ffc107; }}
            .bad-score {{ color: #dc3545; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Отчёт по дизайну праймеров</h1>
            <p><strong>Целевая последовательность:</strong> {target_name}</p>
            <p><strong>Дата анализа:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
            <p><strong>Всего проанализировано праймеров:</strong> {total_primers}</p>
            <p><strong>Рекомендовано:</strong> {recommended} | <strong>Приемлемо:</strong> {acceptable}</p>
            <p><strong>Средняя Tm:</strong> {avg_left_tm:.1f}°C (прямой) / {avg_right_tm:.1f}°C (обратный)</p>
            <p><strong>Средний GC:</strong> {avg_gc:.1f}%</p>
        </div>
    """
    
    # Добавляем карточки праймеров
    for i, primer in enumerate(primers, 1):
        status_class = primer.get('status', 'not_recommended')
        status_text = {
            'recommended': '✅ Рекомендуется',
            'acceptable': '⚠️ Приемлемо',
            'marginal': '⚡ Пограничный',
            'not_recommended': '❌ Не рекомендуется'
        }.get(status_class, '❌ Не рекомендуется')
        
        score = primer.get('stability_score', 0)
        score_class = 'good-score' if score >= 80 else 'medium-score' if score >= 60 else 'bad-score'
        
        html_report += f"""
        <div class="primer-card {status_class}">
            <h2>Праймер #{i} <span class="score {score_class}">{score:.1f}/100</span></h2>
            <p><strong>Статус:</strong> {status_text}</p>
            
            <table>
                <tr>
                    <th>Параметр</th>
                    <th>Прямой праймер</th>
                    <th>Обратный праймер</th>
                </tr>
                <tr>
                    <td>Последовательность</td>
                    <td class="sequence">{primer.get('left_seq', '')}</td>
                    <td class="sequence">{primer.get('right_seq', '')}</td>
                </tr>
                <tr>
                    <td>Длина</td>
                    <td>{len(primer.get('left_seq', ''))} нт</td>
                    <td>{len(primer.get('right_seq', ''))} нт</td>
                </tr>
                <tr>
                    <td>Tm (°C)</td>
                    <td>{primer.get('left_tm', 0)}</td>
                    <td>{primer.get('right_tm', 0)}</td>
                </tr>
                <tr>
                    <td>GC (%)</td>
                    <td>{primer.get('left_gc', 0)}</td>
                    <td>{primer.get('right_gc', 0)}</td>
                </tr>
            </table>
            
            <h3>Термодинамические характеристики:</h3>
            <ul>
                <li>Энергия само-связывания (прямой): {primer.get('forward_self_energy', 0):.2f} kcal/mol</li>
                <li>Энергия само-связывания (обратный): {primer.get('reverse_self_energy', 0):.2f} kcal/mol</li>
                <li>Энергия гетеродимера: {primer.get('heterodimer_energy', 0):.2f} kcal/mol</li>
                <li>Размер продукта: {primer.get('product_size', 0)} нт</li>
                <li>Penalty score: {primer.get('pair_penalty', 0):.2f}</li>
            </ul>
        """
        
        # Добавляем предупреждения, если есть
        if primer.get('warnings'):
            html_report += """
            <div style="background: #fff3cd; padding: 10px; border-radius: 3px; margin: 10px 0;">
                <strong>⚠️ Предупреждения:</strong>
                <ul>
            """
            for warning in primer.get('warnings', []):
                html_report += f"<li>{warning}</li>"
            html_report += """
                </ul>
            </div>
            """
        
        html_report += "</div>"
    
    # Закрываем HTML
    html_report += """
    </body>
    </html>
    """
    
    # Формируем текстовую сводку
    text_summary = f"""
Отчёт для {target_name}
================================
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}
Всего праймеров: {total_primers}
Рекомендовано: {recommended}
Приемлемо: {acceptable}

Лучший праймер: {primers[0].get('left_seq', 'N/A')[:20]}... / {primers[0].get('right_seq', 'N/A')[:20]}...
Score: {primers[0].get('stability_score', 0):.1f}/100
    """
    
    return {
        'target_name': target_name,
        'primer_count': total_primers,
        'report_html': html_report,
        'summary': text_summary,
        'generated_at': datetime.now().isoformat(),
        'stats': {
            'recommended': recommended,
            'acceptable': acceptable,
            'avg_tm_forward': round(avg_left_tm, 1),
            'avg_tm_reverse': round(avg_right_tm, 1),
            'avg_gc': round(avg_gc, 1)
        }
    }


def generate_json_report(primers, target_name, filename=None):
    """Генерация отчёта в формате JSON.
    
    Args:
        primers: Список праймеров
        target_name: Название мишени
        filename: Имя файла для сохранения (опционально)
    
    Returns:
        str: JSON строка с отчётом
    """
    report_data = {
        'metadata': {
            'target_name': target_name,
            'generated_at': datetime.now().isoformat(),
            'primer_count': len(primers)
        },
        'primers': primers,
        'summary': {
            'by_status': {
                'recommended': len([p for p in primers if p.get('status') == 'recommended']),
                'acceptable': len([p for p in primers if p.get('status') == 'acceptable']),
                'marginal': len([p for p in primers if p.get('status') == 'marginal']),
                'not_recommended': len([p for p in primers if p.get('status') == 'not_recommended'])
            },
            'average_values': {
                'tm_forward': sum(p.get('left_tm', 0) for p in primers) / len(primers) if primers else 0,
                'tm_reverse': sum(p.get('right_tm', 0) for p in primers) / len(primers) if primers else 0,
                'gc_content': (sum(p.get('left_gc', 0) for p in primers) + 
                              sum(p.get('right_gc', 0) for p in primers)) / (len(primers) * 2) if primers else 0
            }
        }
    }
    
    json_str = json.dumps(report_data, indent=2, ensure_ascii=False)
    
    if filename:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(json_str)
    
    return json_str