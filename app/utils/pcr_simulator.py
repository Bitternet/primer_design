import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

@dataclass
class SimulationResult:
    """Результаты симуляции ПЦР"""
    predicted_cq: float
    efficiency: float
    curve_data: List[float]
    stability_score: float
    competition_penalty: float = 0.0
    inhibition_resistance: float = 0.0
    multiplex_compatibility: float = 1.0
    
    def calculate_performance_score(self) -> float:
        """Расчёт общего балла производительности"""
        base_score = (40 - self.predicted_cq) / 40 * 0.4  # Cq вклад (40%)
        eff_score = (self.efficiency - 1.0) * 0.3  # Эффективность (30%)
        stability_score = self.stability_score * 0.2  # Стабильность (20%)
        comp_score = (1.0 - self.competition_penalty) * 0.1  # Конкуренция (10%)
        
        return base_score + eff_score + stability_score + comp_score

class PCREmulator:
    """Эмулятор ПЦР-эксперимента"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rng = np.random.default_rng(config.get('random_seed', 42))
        
    def simulate_single(self, primer_data: Dict[str, Any]) -> SimulationResult:
        """Симуляция одиночной ПЦР"""
        # Извлекаем штрафы из данных праймера
        total_penalty = (
            primer_data.get('specificity_penalty', 0.0) * 0.4 +
            primer_data.get('thermodynamic_penalty', 0.0) * 0.6
        )
        
        # Базовые параметры
        initial_copies = self.config.get('initial_copies', 10)
        threshold = self.config.get('detection_threshold', 1e6)
        max_cycles = self.config.get('max_cycles', 40)
        
        # Базовая эффективность с учётом штрафов
        base_efficiency = 2.0 - total_penalty
        
        # Симуляция циклов
        copies = float(initial_copies)
        curve = []
        cq = max_cycles
        
        for cycle in range(1, max_cycles + 1):
            # Динамическая эффективность (падает со временем)
            cycle_efficiency = self._calculate_cycle_efficiency(
                base_efficiency, cycle, max_cycles
            )
            
            # Стохастический шум
            if self.config.get('add_noise', True):
                noise = self.rng.normal(1.0, 0.05)  # 5% шум
                cycle_efficiency *= noise
            
            # Ограничение эффективности
            cycle_efficiency = max(1.0, min(2.0, cycle_efficiency))
            
            # Амплификация
            copies *= cycle_efficiency
            curve.append(copies)
            
            # Определение Cq
            if copies >= threshold and cq == max_cycles:
                cq = cycle
        
        # Расчёт дополнительных метрик
        efficiency = self._calculate_efficiency_from_curve(curve)
        stability = self._calculate_stability_score(curve)
        
        return SimulationResult(
            predicted_cq=float(cq),
            efficiency=efficiency,
            curve_data=curve,
            stability_score=stability,
            competition_penalty=0.0,  # Для одиночной ПЦР
            inhibition_resistance=self._calculate_inhibition_resistance(total_penalty)
        )
    
    def _calculate_cycle_efficiency(self, base_eff: float, cycle: int, max_cycles: int) -> float:
        """Расчёт эффективности для конкретного цикла"""
        # Линейное падение после 30 цикла
        if cycle > 30:
            decay = 0.98 ** (cycle - 30)
        else:
            decay = 1.0
        
        # Эффект насыщения субстратов
        substrate_factor = 1.0 / (1.0 + 0.01 * cycle)
        
        return base_eff * decay * substrate_factor
    
    def _calculate_efficiency_from_curve(self, curve: List[float]) -> float:
        """Расчёт эффективности из кривой амплификации"""
        if len(curve) < 5:
            return 1.8
        
        # Находим экспоненциальную фазу
        exp_start = min(10, len(curve) // 4)
        exp_end = min(30, len(curve) * 3 // 4)
        
        if exp_end <= exp_start:
            return 1.8
        
        exp_curve = curve[exp_start:exp_end]
        if not exp_curve:
            return 1.8
        
        # Линейная регрессия в логарифмической шкале
        x = np.arange(len(exp_curve))
        y = np.log(np.array(exp_curve) + 1e-10)
        
        try:
            slope, _ = np.polyfit(x, y, 1)
            efficiency = np.exp(slope)
            return float(np.clip(efficiency, 1.0, 2.0))
        except:
            return 1.8
    
    def _calculate_stability_score(self, curve: List[float]) -> float:
        """Оценка стабильности амплификации"""
        if len(curve) < 3:
            return 0.5
        
        # Коэффициент вариации в экспоненциальной фазе
        mid_curve = curve[10:25] if len(curve) > 25 else curve[len(curve)//3:2*len(curve)//3]
        
        if not mid_curve:
            return 0.5
        
        cv = np.std(mid_curve) / (np.mean(mid_curve) + 1e-10)
        stability = 1.0 / (1.0 + cv * 10)  # Преобразуем в шкалу 0-1
        return float(np.clip(stability, 0.0, 1.0))
    
    def _calculate_inhibition_resistance(self, total_penalty: float) -> float:
        """Оценка устойчивости к ингибиторам"""
        # Праймеры с меньшим штрафом более устойчивы
        return 1.0 - total_penalty * 0.5

class MultiplexSimulator:
    """Симулятор мультиплексной ПЦР"""
    
    def __init__(self, base_emulator: PCREmulator):
        self.emulator = base_emulator
        self.config = base_emulator.config
    
    def simulate_multiplex(
        self,
        primer_data_list: List[Dict[str, Any]],
        multiplex_groups: List[List[str]]
    ) -> List[SimulationResult]:
        """Симуляция мультиплексной ПЦР"""
        results = []
        
        for group in multiplex_groups:
            # Находим данные праймеров в группе
            group_primers = [
                p for p in primer_data_list if p['id'] in group
            ]
            
            if not group_primers:
                continue
            
            # Симулируем конкурентную амплификацию
            group_results = self._simulate_competition(group_primers)
            results.extend(group_results)
        
        return results
    
    def _simulate_competition(
        self, 
        primer_data_list: List[Dict[str, Any]]
    ) -> List[SimulationResult]:
        """Симуляция конкуренции праймеров за ресурсы"""
        results = []
        
        # Базовые параметры
        initial_copies = self.config.get('initial_copies', 10)
        threshold = self.config.get('detection_threshold', 1e6)
        max_cycles = self.config.get('max_cycles', 40)
        total_resources = 1.0  # Общий пул ресурсов
        
        # Инициализация для каждого праймера
        primer_states = []
        for primer in primer_data_list:
            total_penalty = (
                primer.get('specificity_penalty', 0.0) * 0.4 +
                primer.get('thermodynamic_penalty', 0.0) * 0.6
            )
            
            primer_states.append({
                'id': primer['id'],
                'copies': float(initial_copies),
                'base_eff': 2.0 - total_penalty,
                'total_penalty': total_penalty,
                'curve': [],
                'cq': max_cycles
            })
        
        # Симуляция циклов с конкуренцией
        for cycle in range(1, max_cycles + 1):
            # Расчёт спроса на ресурсы
            total_demand = 0
            for state in primer_states:
                cycle_eff = self._calculate_multiplex_cycle_efficiency(
                    state['base_eff'], cycle, max_cycles
                )
                state['current_demand'] = state['copies'] * cycle_eff
                total_demand += state['current_demand']
            
            # Распределение ресурсов
            resource_factor = min(1.0, total_resources / total_demand) if total_demand > 0 else 1.0
            
            # Амплификация для каждого праймера
            for state in primer_states:
                effective_eff = 1.0 + (state['base_eff'] - 1.0) * resource_factor
                
                # Шум
                if self.config.get('add_noise', True):
                    noise = self.emulator.rng.normal(1.0, 0.05)
                    effective_eff *= noise
                
                effective_eff = max(1.0, min(2.0, effective_eff))
                
                # Амплификация
                state['copies'] *= effective_eff
                state['curve'].append(state['copies'])
                
                # Определение Cq
                if state['copies'] >= threshold and state['cq'] == max_cycles:
                    state['cq'] = cycle
        
        # Создание результатов
        for state in primer_states:
            efficiency = self.emulator._calculate_efficiency_from_curve(state['curve'])
            stability = self.emulator._calculate_stability_score(state['curve'])
            
            # Штраф за конкуренцию (разница между одиночной и мультиплексной ПЦР)
            single_result = self.emulator.simulate_single(
                {'specificity_penalty': state['total_penalty'] * 0.4,
                 'thermodynamic_penalty': state['total_penalty'] * 0.6}
            )
            competition_penalty = max(0, single_result.predicted_cq - state['cq']) / 40
            
            results.append(SimulationResult(
                predicted_cq=float(state['cq']),
                efficiency=efficiency,
                curve_data=state['curve'],
                stability_score=stability,
                competition_penalty=competition_penalty,
                inhibition_resistance=self.emulator._calculate_inhibition_resistance(
                    state['total_penalty']
                ),
                multiplex_compatibility=1.0 - competition_penalty
            ))
        
        return results
    
    def _calculate_multiplex_cycle_efficiency(
        self, 
        base_eff: float, 
        cycle: int, 
        max_cycles: int
    ) -> float:
        """Расчёт эффективности для мультиплекса"""
        # Более агрессивное падение из-за конкуренции
        if cycle > 25:
            decay = 0.95 ** (cycle - 25)
        else:
            decay = 1.0
        
        # Более сильный эффект насыщения
        substrate_factor = 1.0 / (1.0 + 0.02 * cycle)
        
        return base_eff * decay * substrate_factor