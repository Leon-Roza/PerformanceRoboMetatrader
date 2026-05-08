from collections import defaultdict
from datetime import datetime
import math


class KPIEngine:
    """Calcula todos os KPIs a partir das trades."""

    def analyze(self, trades):
        """Análise completa retornando todos os KPIs."""
        # Filtrar apenas trades com profit (excluir depósitos/retiradas)
        closed_trades = [t for t in trades if t.get('profit') is not None]

        if not closed_trades:
            return {'error': 'Nenhuma operação fechada encontrada'}

        # Ordenar por tempo
        closed_trades.sort(key=lambda t: t.get('open_time') or datetime.min)

        analysis = {
            'summary': self._summary_kpis(closed_trades),
            'daily': self._aggregate_by_period(closed_trades, 'day'),
            'monthly': self._aggregate_by_period(closed_trades, 'month'),
            'yearly': self._aggregate_by_period(closed_trades, 'year'),
            'hourly_distribution': self._hourly_distribution(closed_trades),
            'weekly_distribution': self._weekly_distribution(closed_trades),
            'drawdown': self._drawdown_analysis(closed_trades),
            'streaks': self._streak_analysis(closed_trades),
            'symbols': self._by_symbol(closed_trades),
            'equity_curve': self._equity_curve(closed_trades),
            'monthly_returns': self._monthly_returns(closed_trades),
            'profit_factor_by_period': self._profit_factor_trend(closed_trades),
        }

        return analysis

    def _summary_kpis(self, trades):
        """KPIs gerais do relatório."""
        profits = [t['profit'] for t in trades if t['profit'] is not None]
        commissions = [t.get('commission') or 0 for t in trades]
        swaps = [t.get('swap') or 0 for t in trades]

        total_profit = sum(profits)
        gross_profit = sum(p for p in profits if p > 0)
        gross_loss = abs(sum(p for p in profits if p < 0))
        total_commission = sum(commissions)
        total_swap = sum(swaps)
        net_profit = total_profit

        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]

        total_trades = len(trades)
        num_wins = len(wins)
        num_losses = len(losses)
        win_rate = (num_wins / total_trades * 100) if total_trades > 0 else 0

        avg_win = (sum(wins) / num_wins) if num_wins > 0 else 0
        avg_loss = (sum(losses) / num_losses) if num_losses > 0 else 0
        avg_trade = total_profit / total_trades if total_trades > 0 else 0

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Payoff ratio (ratio de recompensa/risco médio)
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # Expectância matemática
        expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * abs(avg_loss))

        # Maior trade e menor trade
        best_trade = max(profits) if profits else 0
        worst_trade = min(profits) if profits else 0

        # Desvio padrão
        std_dev = (sum((p - avg_trade) ** 2 for p in profits) / len(profits)) ** 0.5 if len(profits) > 1 else 0

        # Sharpe Ratio simplificado (assumindo risk-free = 0)
        sharpe_ratio = (avg_trade / std_dev * math.sqrt(252)) if std_dev > 0 else 0

        # Recuperação (Recovery Factor)
        max_drawdown = self._calculate_max_drawdown(trades)
        recovery_factor = abs(net_profit / max_drawdown) if max_drawdown != 0 else float('inf')

        return {
            'total_trades': total_trades,
            'wins': num_wins,
            'losses': num_losses,
            'win_rate': round(win_rate, 2),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'net_profit': round(net_profit, 2),
            'total_commission': round(total_commission, 2),
            'total_swap': round(total_swap, 2),
            'profit_factor': round(profit_factor, 2),
            'payoff_ratio': round(payoff_ratio, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_trade': round(avg_trade, 2),
            'expectancy': round(expectancy, 2),
            'best_trade': round(best_trade, 2),
            'worst_trade': round(worst_trade, 2),
            'std_deviation': round(std_dev, 2),
            'sharpe_ratio': round(sharpe_ratio, 3),
            'max_drawdown': round(max_drawdown, 2),
            'recovery_factor': round(recovery_factor, 2),
            'consecutive_wins': self._max_consecutive(profits, True),
            'consecutive_losses': self._max_consecutive(profits, False),
        }

    def _aggregate_by_period(self, trades, period):
        """Agrega trades por dia, mês ou ano."""
        periods = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0,
            'gross_profit': 0, 'gross_loss': 0,
            'net_profit': 0, 'commission': 0, 'swap': 0
        })

        for trade in trades:
            open_time = trade.get('open_time')
            if not open_time:
                continue

            if period == 'day':
                key = open_time.strftime('%Y-%m-%d')
            elif period == 'month':
                key = open_time.strftime('%Y-%m')
            elif period == 'year':
                key = open_time.strftime('%Y')
            else:
                key = str(open_time)

            profit = trade.get('profit') or 0
            commission = trade.get('commission') or 0
            swap = trade.get('swap') or 0

            p = periods[key]
            p['trades'] += 1
            p['commission'] += commission
            p['swap'] += swap
            p['net_profit'] += profit
            p['gross_profit'] += max(profit, 0)
            p['gross_loss'] += abs(min(profit, 0))

            if profit > 0:
                p['wins'] += 1
            elif profit < 0:
                p['losses'] += 1

        # Calular win_rate para cada período
        result = {}
        for key, data in sorted(periods.items()):
            data['win_rate'] = round((data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0, 2)
            data['gross_profit'] = round(data['gross_profit'], 2)
            data['gross_loss'] = round(data['gross_loss'], 2)
            data['net_profit'] = round(data['net_profit'], 2)
            data['commission'] = round(data['commission'], 2)
            data['swap'] = round(data['swap'], 2)
            result[key] = data

        return result

    def _hourly_distribution(self, trades):
        """Distribuição de trades e profit por hora do dia."""
        hourly = defaultdict(lambda: {'trades': 0, 'profit': 0, 'wins': 0, 'losses': 0})

        for trade in trades:
            open_time = trade.get('open_time')
            if not open_time:
                continue
            hour = open_time.hour
            profit = trade.get('profit') or 0

            hourly[hour]['trades'] += 1
            hourly[hour]['profit'] += profit
            if profit > 0:
                hourly[hour]['wins'] += 1
            elif profit < 0:
                hourly[hour]['losses'] += 1

        result = {}
        for h in range(24):
            data = hourly[h]
            data['profit'] = round(data['profit'], 2)
            result[h] = data

        return result

    def _weekly_distribution(self, trades):
        """Distribuição por dia da semana."""
        days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        weekly = defaultdict(lambda: {'trades': 0, 'profit': 0, 'wins': 0, 'losses': 0})

        for trade in trades:
            open_time = trade.get('open_time')
            if not open_time:
                continue
            day_idx = open_time.weekday()  # 0=Monday
            profit = trade.get('profit') or 0

            weekly[day_idx]['trades'] += 1
            weekly[day_idx]['profit'] += profit
            if profit > 0:
                weekly[day_idx]['wins'] += 1
            elif profit < 0:
                weekly[day_idx]['losses'] += 1

        result = {}
        for i in range(7):
            data = weekly[i]
            data['profit'] = round(data['profit'], 2)
            data['day_name'] = days[i]
            result[days[i]] = data

        return result

    def _drawdown_analysis(self, trades):
        """Análise de drawdown."""
        equity = 0
        peak = 0
        max_drawdown = 0
        max_drawdown_pct = 0
        drawdown_periods = []
        current_dd_start = None

        equity_curve = []

        for trade in trades:
            profit = trade.get('profit') or 0
            equity += profit
            equity_curve.append(round(equity, 2))

            if equity > peak:
                if peak > 0 and current_dd_start:
                    drawdown_periods.append({
                        'start': current_dd_start,
                        'depth': round(peak - (peak - max_drawdown), 2),
                        'pct': round(max_drawdown_pct, 2)
                    })
                peak = equity
                current_dd_start = None
            else:
                if current_dd_start is None:
                    current_dd_start = trade.get('open_time')

                dd = peak - equity
                dd_pct = (dd / peak * 100) if peak > 0 else 0

                if dd > max_drawdown:
                    max_drawdown = dd
                    max_drawdown_pct = dd_pct

        return {
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown_pct, 2),
            'current_equity': round(equity, 2),
            'equity_curve': equity_curve,
        }

    def _streak_analysis(self, trades):
        """Análise de sequências de vitórias/derrotas."""
        profits = [t.get('profit') or 0 for t in trades]

        streaks = {
            'current': {'type': None, 'count': 0},
            'max_win_streak': 0,
            'max_loss_streak': 0,
            'avg_win_streak': 0,
            'avg_loss_streak': 0,
            'win_streaks': [],
            'loss_streaks': [],
        }

        current_streak_type = None
        current_count = 0

        for p in profits:
            if p > 0:
                t = 'win'
            elif p < 0:
                t = 'loss'
            else:
                t = 'neutral'

            if t == current_streak_type:
                current_count += 1
            else:
                if current_streak_type == 'win' and current_count > 0:
                    streaks['win_streaks'].append(current_count)
                    streaks['max_win_streak'] = max(streaks['max_win_streak'], current_count)
                elif current_streak_type == 'loss' and current_count > 0:
                    streaks['loss_streaks'].append(current_count)
                    streaks['max_loss_streak'] = max(streaks['max_loss_streak'], current_count)

                current_streak_type = t
                current_count = 1

        # Fechar último streak
        if current_streak_type == 'win':
            streaks['win_streaks'].append(current_count)
            streaks['max_win_streak'] = max(streaks['max_win_streak'], current_count)
        elif current_streak_type == 'loss':
            streaks['loss_streaks'].append(current_count)
            streaks['max_loss_streak'] = max(streaks['max_loss_streak'], current_count)

        streaks['avg_win_streak'] = round(
            sum(streaks['win_streaks']) / len(streaks['win_streaks']) if streaks['win_streaks'] else 0, 1
        )
        streaks['avg_loss_streak'] = round(
            sum(streaks['loss_streaks']) / len(streaks['loss_streaks']) if streaks['loss_streaks'] else 0, 1
        )

        streaks['current'] = {
            'type': current_streak_type,
            'count': current_count
        }

        return streaks

    def _by_symbol(self, trades):
        """Análise por símbolo."""
        symbols = defaultdict(lambda: {
            'trades': 0, 'wins': 0, 'losses': 0,
            'gross_profit': 0, 'gross_loss': 0, 'net_profit': 0
        })

        for trade in trades:
            symbol = trade.get('symbol') or 'Unknown'
            profit = trade.get('profit') or 0

            s = symbols[symbol]
            s['trades'] += 1
            s['net_profit'] += profit
            s['gross_profit'] += max(profit, 0)
            s['gross_loss'] += abs(min(profit, 0))
            if profit > 0:
                s['wins'] += 1
            elif profit < 0:
                s['losses'] += 1

        result = {}
        for sym, data in sorted(symbols.items(), key=lambda x: x[1]['net_profit'], reverse=True):
            data['net_profit'] = round(data['net_profit'], 2)
            data['gross_profit'] = round(data['gross_profit'], 2)
            data['gross_loss'] = round(data['gross_loss'], 2)
            data['win_rate'] = round((data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0, 2)
            result[sym] = data

        return result

    def _equity_curve(self, trades):
        """Curva de equity."""
        equity = 0
        curve = []

        for trade in trades:
            equity += trade.get('profit') or 0
            curve.append({
                'trade': len(curve) + 1,
                'equity': round(equity, 2)
            })

        return curve

    def _monthly_returns(self, trades):
        """Retornos mensais para heatmap."""
        monthly = defaultdict(lambda: {'profit': 0, 'trades': 0})

        for trade in trades:
            open_time = trade.get('open_time')
            if not open_time:
                continue
            key = open_time.strftime('%Y-%m')
            monthly[key]['profit'] += trade.get('profit') or 0
            monthly[key]['trades'] += 1

        result = {}
        for key, data in sorted(monthly.items()):
            result[key] = {
                'profit': round(data['profit'], 2),
                'trades': data['trades']
            }

        return result

    def _profit_factor_trend(self, trades):
        """Profit factor por período (mensal)."""
        monthly = defaultdict(lambda: {'gross_profit': 0, 'gross_loss': 0})

        for trade in trades:
            open_time = trade.get('open_time')
            if not open_time:
                continue
            key = open_time.strftime('%Y-%m')
            profit = trade.get('profit') or 0

            if profit > 0:
                monthly[key]['gross_profit'] += profit
            else:
                monthly[key]['gross_loss'] += abs(profit)

        result = {}
        for key, data in sorted(monthly.items()):
            pf = (data['gross_profit'] / data['gross_loss']) if data['gross_loss'] > 0 else float('inf')
            result[key] = {
                'gross_profit': round(data['gross_profit'], 2),
                'gross_loss': round(data['gross_loss'], 2),
                'profit_factor': round(pf, 2) if pf != float('inf') else '∞'
            }

        return result

    def _calculate_max_drawdown(self, trades):
        """Calcula o drawdown máximo absoluto."""
        equity = 0
        peak = 0
        max_dd = 0

        for trade in trades:
            equity += trade.get('profit') or 0
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > max_dd:
                max_dd = dd

        return max_dd

    def _max_consecutive(self, profits, is_win):
        """Calcula a maior sequência consecutiva."""
        max_count = 0
        current_count = 0

        for p in profits:
            condition = (p > 0) if is_win else (p < 0)
            if condition:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0

        return max_count