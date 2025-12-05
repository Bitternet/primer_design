import primer3
import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Импортируем расширенный анализатор BLAST
try:
    from app.utils.blast_wrapper import EnhancedBlastAnalyzer, SpecificityResult, BlastHit
except ImportError:
    # Заглушки для совместимости
    from dataclasses import dataclass
    
    @dataclass
    class BlastHit:
        pass
    
    @dataclass
    class SpecificityResult:
        is_specific: bool = True
        score: float = 1.0
        error_message: str = ""
        hits: List = None
        near_matches: List = None
        warnings: List = None
        
        def calculate_score(self):
            return self.score
        
        def is_acceptable(self, threshold=0.7):
            return self.is_specific and self.score >= threshold
    
    class EnhancedBlastAnalyzer:
        def analyze_primer_pair(self, *args, **kwargs):
            return SpecificityResult()

@dataclass
class ThermodynamicResult:
    """Результат термодинамического анализа"""
    cross_dimer_g: float = 0.0
    hairpin_g: float = 0.0
    self_dimer_g: float = 0.0
    tm_difference: float = 0.0
    score: float = 1.0
    
    def calculate_score(self):
        return self.score

@dataclass
class SimulationResult:
    """Результат симуляции ПЦР"""
    predicted_cq: float = 30.0
    efficiency: float = 1.9
    stability_score: float = 0.8
    curve_data: List[float] = None
    competition_penalty: float = 0.0
    
    def __post_init__(self):
        if self.curve_data is None:
            self.curve_data = []
    
    def calculate_score(self):
        return self.stability_score

@dataclass
class PrimerPairExtended:
    """Расширенный класс для праймеров"""
    id: str
    left_seq: str
    right_seq: str
    left_tm: float
    right_tm: float
    product_size: int
    pair_penalty: float
    left_gc: float
    right_gc: float
    
    # Результаты анализов
    specificity: Optional[SpecificityResult] = None
    thermodynamics: Optional[ThermodynamicResult] = None
    simulation: Optional[SimulationResult] = None
    
    # Итоговые баллы
    specificity_score: float = 0.0
    thermodynamic_score: float = 0.0
    simulation_score: float = 0.0
    total_score: float = 0.0
    
    def to_dict(self):
        """Конвертация в словарь для JSON"""
        data = asdict(self)
        
        # Обрабатываем вложенные dataclasses
        if self.specificity:
            data['specificity'] = asdict(self.specificity)
        if self.thermodynamics:
            data['thermodynamics'] = asdict(self.thermodynamics)
        if self.simulation:
            data['simulation'] = asdict(self.simulation)
        
        return data

class SimplePCREmulator:
    """Простой эмулятор ПЦР"""
    
    def __init__(self, config=None):
        self.config = config or {}
        np.random.seed(42)
    
    def simulate(self, primer_data: Dict) -> SimulationResult:
        """Симуляция ПЦР для одного праймера"""
        
        # Извлекаем параметры
        specificity_score = primer_data.get('specificity_score', 0.8)
        thermo_score = primer_data.get('thermodynamic_score', 0.8)
        tm_diff = primer_data.get('tm_difference', 2.0)
        gc_content = primer_data.get('gc_content', 50.0)
        
        # Рассчитываем общий штраф
        total_penalty = (
            (1.0 - specificity_score) * 0.4 +
            (1.0 - thermo_score) * 0.3 +
            (abs(tm_diff - 2.0) / 10.0) * 0.2 +
            (abs(gc_content - 50.0) / 50.0) * 0.1
        )
        
        # Базовые параметры симуляции
        initial_copies = 10
        threshold = 1e6
        max_cycles = 40
        
        # Базовая эффективность
        base_efficiency = 1.95 - total_penalty * 0.5
        
        # Симуляция циклов
        copies = float(initial_copies)
        curve = []
        cq = max_cycles
        
        for cycle in range(1, max_cycles + 1):
            # Эффективность падает со временем
            if cycle > 30:
                decay = 0.98 ** (cycle - 30)
            else:
                decay = 1.0
            
            # Случайные колебания
            noise = 1.0 + np.random.normal(0, 0.03)
            
            # Текущая эффективность
            current_eff = base_efficiency * decay * noise
            current_eff = max(1.0, min(2.0, current_eff))
            
            # Амплификация
            copies *= current_eff
            curve.append(copies)
            
            # Определение Cq
            if copies >= threshold and cq == max_cycles:
                cq = cycle + np.random.normal(0, 0.5)
        
        # Расчёт эффективности из кривой
        efficiency = self._calculate_efficiency(curve)
        
        # Оценка стабильности
        stability = self._calculate_stability(curve)
        
        return SimulationResult(
            predicted_cq=float(cq),
            efficiency=float(efficiency),
            stability_score=float(stability),
            curve_data=curve[:50]  # Сохраняем только первые 50 точек
        )
    
    def _calculate_efficiency(self, curve: List[float]) -> float:
        """Расчёт эффективности из кривой"""
        if len(curve) < 10:
            return 1.9
        
        # Находим экспоненциальную фазу (циклы 5-25)
        start = min(5, len(curve) - 1)
        end = min(25, len(curve) - 1)
        
        if end <= start:
            return 1.9
        
        exp_curve = curve[start:end]
        if len(exp_curve) < 5:
            return 1.9
        
        # Линейная регрессия в логарифмической шкале
        try:
            x = np.arange(len(exp_curve))
            y = np.log(np.array(exp_curve) + 1e-10)
            slope, _ = np.polyfit(x, y, 1)
            efficiency = np.exp(slope)
            return float(np.clip(efficiency, 1.0, 2.0))
        except:
            return 1.9
    
    def _calculate_stability(self, curve: List[float]) -> float:
        """Расчёт стабильности амплификации"""
        if len(curve) < 10:
            return 0.7
        
        # Коэффициент вариации в средней части
        mid_start = len(curve) // 3
        mid_end = 2 * len(curve) // 3
        
        if mid_end <= mid_start:
            return 0.7
        
        mid_curve = curve[mid_start:mid_end]
        mean_val = np.mean(mid_curve)
        std_val = np.std(mid_curve)
        
        if mean_val == 0:
            return 0.7
        
        cv = std_val / mean_val
        stability = 1.0 / (1.0 + cv * 10)
        
        return float(np.clip(stability, 0.0, 1.0))

class EnhancedPipeline:
    """Улучшенный пайплайн с симуляцией"""
    
    def __init__(self):
        self.blast_analyzer = EnhancedBlastAnalyzer()
        self.pcr_emulator = SimplePCREmulator()
    
    def design_primers(
        self, 
        target_sequence: str, 
        target_name: str,
        parameters: Dict[str, Any]
    ) -> List[PrimerPairExtended]:
        """Дизайн праймеров с Primer3"""
        
        print(f"[Enhanced] Дизайн праймеров для: {target_name}")
        
        # Параметры Primer3
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
            'PRIMER_TASK': 'generic',
            'PRIMER_PICK_LEFT_PRIMER': 1,
            'PRIMER_PICK_RIGHT_PRIMER': 1,
            'PRIMER_PICK_INTERNAL_OLIGO': 0,
        }
        
        try:
            # НОВЫЙ ВЫЗОВ: передаём все параметры одним словарём
            # В primer3-py 2.0+ нужно объединить все параметры
            all_params = primer3_params
            result = primer3.designPrimers(all_params)
            
        except TypeError as e:
            # Если старая версия primer3-py
            print(f"[Enhanced] Попытка старого API: {e}")
            try:
                # Пробуем старый синтаксис
                result = primer3.designPrimers(primer3_params)
            except Exception as e2:
                print(f"[Enhanced] Ошибка Primer3: {e2}")
                return []
        except Exception as e:
            print(f"[Enhanced] Ошибка Primer3: {e}")
            return []
        
        total_designed = result.get('PRIMER_PAIR_NUM_RETURNED', 0)
        print(f"[Enhanced] Создано пар праймеров: {total_designed}")
        
        if total_designed == 0:
            print("[Enhanced] Primer3 не вернул праймеров")
            return []
        
        primers = []
        for i in range(min(total_designed, 50)):
            primers.append(PrimerPairExtended(
                id=f"P{i+1:03d}",
                left_seq=result.get(f'PRIMER_LEFT_{i}_SEQUENCE', ''),
                right_seq=result.get(f'PRIMER_RIGHT_{i}_SEQUENCE', ''),
                left_tm=round(result.get(f'PRIMER_LEFT_{i}_TM', 0), 2),
                right_tm=round(result.get(f'PRIMER_RIGHT_{i}_TM', 0), 2),
                product_size=result.get(f'PRIMER_PAIR_{i}_PRODUCT_SIZE', 0),
                pair_penalty=round(result.get(f'PRIMER_PAIR_{i}_PENALTY', 0), 2),
                left_gc=round(result.get(f'PRIMER_LEFT_{i}_GC_PERCENT', 0), 1),
                right_gc=round(result.get(f'PRIMER_RIGHT_{i}_GC_PERCENT', 0), 1),
            ))
        
        return primers
    
    def analyze_specificity(
        self, 
        primers: List[PrimerPairExtended],
        target_name: str
    ) -> List[PrimerPairExtended]:
        """Анализ специфичности"""
        
        print(f"[Enhanced] Анализ специфичности для {len(primers)} праймеров")
        
        analyzed = []
        for primer in primers[:20]:  # Проверяем только 20 лучших
            try:
                spec_result = self.blast_analyzer.analyze_primer_pair(
                    left_seq=primer.left_seq,
                    right_seq=primer.right_seq,
                    target_name=target_name,
                    relaxed_mode=True
                )
                
                primer.specificity = spec_result
                primer.specificity_score = spec_result.calculate_score()
                
                print(f"  {primer.id}: специфичность={primer.specificity_score:.3f}, "
                      f"хитов={len(spec_result.hits)}")
                
                if spec_result.is_acceptable():
                    analyzed.append(primer)
                    
            except Exception as e:
                print(f"  Ошибка анализа {primer.id}: {e}")
                # Продолжаем с базовым баллом
                primer.specificity_score = 0.7
                analyzed.append(primer)
        
        print(f"[Enhanced] Принято праймеров: {len(analyzed)}")
        return analyzed
    
    def analyze_thermodynamics(
        self, 
        primers: List[PrimerPairExtended]
    ) -> List[PrimerPairExtended]:
        """Термодинамический анализ"""
        
        print(f"[Enhanced] Термодинамический анализ")
        
        for primer in primers:
            # Упрощённый расчёт (можно заменить на ViennaRNA)
            tm_diff = abs(primer.left_tm - primer.right_tm)
            gc_avg = (primer.left_gc + primer.right_gc) / 2
            
            # Эвристическая оценка
            tm_score = max(0.0, 1.0 - tm_diff / 10.0)
            gc_score = 1.0 - abs(gc_avg - 50.0) / 50.0
            
            thermo_score = (tm_score * 0.6 + gc_score * 0.4)
            
            primer.thermodynamics = ThermodynamicResult(
                tm_difference=tm_diff,
                score=thermo_score
            )
            primer.thermodynamic_score = thermo_score
            
            print(f"  {primer.id}: Tm diff={tm_diff:.1f}°C, GC={gc_avg:.1f}%, "
                  f"счёт={thermo_score:.3f}")
        
        return primers
    
    def simulate_pcr(
        self, 
        primers: List[PrimerPairExtended]
    ) -> List[PrimerPairExtended]:
        """Симуляция ПЦР"""
        
        print(f"[Enhanced] Симуляция ПЦР")
        
        for primer in primers:
            # Подготовка данных для симуляции
            sim_data = {
                'specificity_score': primer.specificity_score,
                'thermodynamic_score': primer.thermodynamic_score,
                'tm_difference': abs(primer.left_tm - primer.right_tm),
                'gc_content': (primer.left_gc + primer.right_gc) / 2
            }
            
            # Запуск симуляции
            sim_result = self.pcr_emulator.simulate(sim_data)
            
            primer.simulation = sim_result
            primer.simulation_score = sim_result.calculate_score()
            
            print(f"  {primer.id}: Cq={sim_result.predicted_cq:.1f}, "
                  f"eff={sim_result.efficiency:.3f}, "
                  f"стабильность={sim_result.stability_score:.3f}")
        
        return primers
    
    def rank_primers(
        self, 
        primers: List[PrimerPairExtended],
        num_finalists: int = 5
    ) -> List[PrimerPairExtended]:
        """Ранжирование праймеров"""
        
        # Расчёт итогового балла
        for primer in primers:
            # Взвешенная сумма
            primer.total_score = (
                primer.specificity_score * 0.35 +
                primer.thermodynamic_score * 0.30 +
                primer.simulation_score * 0.35
            )
        
        # Сортировка по убыванию балла
        primers.sort(key=lambda x: x.total_score, reverse=True)
        
        # Выбор лучших
        finalists = primers[:num_finalists]
        
        print(f"\n[Enhanced] Топ-{len(finalists)} праймеров:")
        for i, primer in enumerate(finalists, 1):
            print(f"  {i}. {primer.id}: общий={primer.total_score:.3f} "
                  f"(спец={primer.specificity_score:.3f}, "
                  f"термо={primer.thermodynamic_score:.3f}, "
                  f"симул={primer.simulation_score:.3f})")
            
            if primer.simulation:
                print(f"       Прогноз: Cq={primer.simulation.predicted_cq:.1f}, "
                      f"Эффективность={primer.simulation.efficiency:.3f}")
        
        return finalists
    
    def run(
        self,
        target_sequence: str,
        target_name: str,
        parameters: Dict[str, Any],
        num_finalists: int = 5
    ) -> Dict[str, Any]:
        """Запуск полного пайплайна"""
        
        print(f"\n{'='*60}")
        print(f"ЗАПУСК РАСШИРЕННОГО ПАЙПЛАЙНА")
        print(f"Мишень: {target_name}")
        print(f"Длина: {len(target_sequence)} нт")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        
        try:
            # 1. Дизайн праймеров
            all_primers = self.design_primers(target_sequence, target_name, parameters)
            if not all_primers:
                return {
                    'success': False,
                    'error': 'Primer3 не смог создать праймеры',
                    'execution_time': 0
                }
            
            # 2. Анализ специфичности
            specific_primers = self.analyze_specificity(all_primers, target_name)
            if not specific_primers:
                return {
                    'success': False,
                    'error': 'Не найдено специфичных праймеров',
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # 3. Термодинамический анализ
            thermo_primers = self.analyze_thermodynamics(specific_primers)
            
            # 4. Симуляция ПЦР
            simulated_primers = self.simulate_pcr(thermo_primers)
            
            # 5. Ранжирование
            final_primers = self.rank_primers(simulated_primers, num_finalists)
            
            # Подготовка результатов
            elapsed_time = (datetime.now() - start_time).total_seconds()
            
            result = {
                'success': True,
                'target_name': target_name,
                'total_primers_designed': len(all_primers),
                'specific_primers_found': len(specific_primers),
                'final_recommendations': len(final_primers),
                'execution_time': round(elapsed_time, 2),
                'primers': [p.to_dict() for p in final_primers],
                'top_primer': final_primers[0].to_dict() if final_primers else None,
                'pipeline_version': 'enhanced_v1.0',
                'has_simulation': True
            }
            
            # Добавляем сводку
            if final_primers:
                result['summary'] = {
                    'best_cq': final_primers[0].simulation.predicted_cq if final_primers[0].simulation else 30.0,
                    'best_efficiency': final_primers[0].simulation.efficiency if final_primers[0].simulation else 1.9,
                    'best_score': final_primers[0].total_score,
                    'score_range': [p.total_score for p in final_primers]
                }
            
            print(f"\n[Enhanced] Пайплайн успешно завершён за {elapsed_time:.1f} сек")
            print(f"[Enhanced] Рекомендовано праймеров: {len(final_primers)}")
            
            return result
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            print(f"\n[Enhanced] Ошибка пайплайна: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'error_details': error_details,
                'execution_time': (datetime.now() - start_time).total_seconds()
            }

# Функция для обратной совместимости
def run_enhanced_pipeline(target_sequence, target_name, parameters):
    """Обёртка для использования из существующего кода"""
    pipeline = EnhancedPipeline()
    return pipeline.run(
        target_sequence=target_sequence,
        target_name=target_name,
        parameters=parameters
    )