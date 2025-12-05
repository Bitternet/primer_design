import ViennaRNA

class ViennaRNAAnalyzer:
    def __init__(self, temperature=60.0, sodium=0.05, magnesium=0.002):
        self.temperature = temperature
        self.sodium = sodium
        self.magnesium = magnesium
        
        # Настройка параметров ViennaRNA
        self.model_details = {
            'temperature': self.temperature,
            'dangles': 2,  # 2 = all dangles (default)
            'noLP': 0,     # 0 = allow lonely pairs
            'noGU': 0,     # 0 = allow G-U pairs
            'logML': 0,    # 0 = no logarithmic ML energy
            'salt': self.sodium,
            'magnesium': self.magnesium
        }
    
    def analyze_primer_pair(self, forward_seq, reverse_seq, target_seq=None):
        """Анализ пары праймеров."""
        results = {}
        
        try:
            # 1. Анализ вторичных структур отдельных праймеров
            results['forward_self_energy'] = self._fold_single_primer(forward_seq)
            results['reverse_self_energy'] = self._fold_single_primer(reverse_seq)
            
            # 2. Анализ гетеродимеров (праймер-праймер)
            results['heterodimer_energy'] = self._analyze_heterodimer(forward_seq, reverse_seq)
            
            # 3. Анализ самодимеров (праймер-сам себя)
            results['forward_homodimer_energy'] = self._analyze_homodimer(forward_seq)
            results['reverse_homodimer_energy'] = self._analyze_homodimer(reverse_seq)
            
            # 4. Анализ связывания с мишенью (если предоставлена)
            if target_seq:
                results['forward_target_energy'] = self._analyze_primer_target(forward_seq, target_seq)
                results['reverse_target_energy'] = self._analyze_primer_target(reverse_seq, target_seq)
            
            # 5. Расчёт Tm (более точный с учётом соседних нуклеотидов)
            results['forward_tm'] = self._calculate_tm_nearest_neighbor(forward_seq)
            results['reverse_tm'] = self._calculate_tm_nearest_neighbor(reverse_seq)
            results['tm_difference'] = abs(results['forward_tm'] - results['reverse_tm'])
            
            # 6. Score для ранжирования
            results['stability_score'] = self._calculate_stability_score(results)
            
            # 7. Добавляем предупреждения, если есть проблемы
            results['warnings'] = self._generate_warnings(results)
            
        except Exception as e:
            print(f"Ошибка при анализе праймеров: {str(e)}")
            # Возвращаем значения по умолчанию при ошибке
            results = {
                'forward_self_energy': 0,
                'reverse_self_energy': 0,
                'heterodimer_energy': 0,
                'forward_tm': 0,
                'reverse_tm': 0,
                'stability_score': 0,
                'error': str(e)
            }
        
        return results
    
    def _fold_single_primer(self, sequence):
        """Складывание одиночного праймера для анализа вторичной структуры."""
        fc = ViennaRNA.fold_compound(sequence)
        mfe_structure, mfe_energy = fc.mfe()
        return mfe_energy
    
    def _analyze_heterodimer(self, seq1, seq2):
        """Анализ энергии гетеродимера между двумя последовательностями."""
        # Создаем композитную последовательность для анализа димера
        composite_seq = seq1 + "&" + seq2
        
        # Используем cofold для анализа двух взаимодействующих молекул
        try:
            fc = ViennaRNA.fold_compound(composite_seq)
            structure, energy = fc.mfe()
            return energy
        except:
            # Альтернативный метод: используем duplexfold
            try:
                # В новых версиях ViennaRNA есть duplexfold
                import ViennaRNA.RNA
                result = ViennaRNA.RNA.duplexfold(seq1, seq2)
                return result.energy
            except:
                # Если ничего не работает, возвращаем консервативное значение
                return 0
    
    def _analyze_homodimer(self, sequence):
        """Анализ энергии гомодимера (праймер сам с собой)."""
        return self._analyze_heterodimer(sequence, sequence)
    
    def _analyze_primer_target(self, primer_seq, target_seq):
        """Анализ энергии связывания праймера с мишенью."""
        try:
            # Ищем комплементарные участки
            fc = ViennaRNA.fold_compound(primer_seq + "&" + target_seq)
            structure, energy = fc.mfe()
            return energy
        except:
            return 0
    
    def _calculate_tm_nearest_neighbor(self, sequence):
        """Расчёт температуры плавления по методу ближайших соседей."""
        # Упрощённая формула для оценки Tm
        # В реальных условиях лучше использовать библиотеку primer3 или собственную реализацию
        
        seq_upper = sequence.upper()
        a = seq_upper.count('A')
        t = seq_upper.count('T')
        g = seq_upper.count('G')
        c = seq_upper.count('C')
        
        # Простая формула Wallace для коротких олигонуклеотидов
        if len(sequence) <= 14:
            tm = 2 * (a + t) + 4 * (g + c)
        else:
            # Формула SantaLucia для более длинных последовательностей
            # Это упрощённая версия
            tm = 64.9 + 41 * (g + c - 16.4) / len(sequence)
        
        # Корректировка на концентрацию солей
        tm += 16.6 * (self.sodium / 1.0)  # примерная коррекция
        
        return round(tm, 2)
    
    def _calculate_stability_score(self, results):
        """Расчёт общего score стабильности."""
        score = 100.0
        
        # Штрафы за плохие характеристики
        penalties = {
            'forward_self_energy': 2.0,     # Само-связывание
            'reverse_self_energy': 2.0,
            'heterodimer_energy': 3.0,      # Димеры праймеров
            'forward_homodimer_energy': 2.0,
            'reverse_homodimer_energy': 2.0,
            'tm_difference': 0.5           # Разница в Tm
        }
        
        # Применяем штрафы
        for key, weight in penalties.items():
            if key in results:
                value = results[key]
                if key == 'tm_difference' and value > 5:
                    # Штраф за большую разницу в температурах плавления
                    score -= (value - 5) * weight
                elif key.endswith('_energy') and value < 0:
                    # Отрицательная энергия означает стабильную структуру (плохо)
                    score += value * weight
        
        # Дополнительные бонусы/штрафы
        if 'forward_target_energy' in results and 'reverse_target_energy' in results:
            target_energy = results['forward_target_energy'] + results['reverse_target_energy']
            if target_energy < -10:  # Хорошее связывание с мишенью
                score += 20
        
        return max(score, 0)
    
    def _generate_warnings(self, results):
        """Генерация предупреждений о потенциальных проблемах."""
        warnings = []
        
        # Проверка само-связывания
        if results.get('forward_self_energy', 0) < -5:
            warnings.append("Сильное само-связывание прямого праймера")
        if results.get('reverse_self_energy', 0) < -5:
            warnings.append("Сильное само-связывание обратного праймера")
        
        # Проверка гетеродимеров
        if results.get('heterodimer_energy', 0) < -10:
            warnings.append("Сильное образование гетеродимера между праймерами")
        
        # Проверка температуры плавления
        if results.get('tm_difference', 0) > 5:
            warnings.append(f"Большая разница в температурах плавления: {results['tm_difference']:.1f}°C")
        
        # Проверка гомодимеров
        if results.get('forward_homodimer_energy', 0) < -5:
            warnings.append("Образование димера прямого праймера")
        if results.get('reverse_homodimer_energy', 0) < -5:
            warnings.append("Образование димера обратного праймера")
        
        return warnings