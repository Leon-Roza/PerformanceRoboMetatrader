from bs4 import BeautifulSoup, NavigableString
from datetime import datetime
import re

def get_text_deep(element):
    if element is None: return ''
    if isinstance(element, NavigableString): return str(element).strip()
    return ' '.join(filter(None, (get_text_deep(c) for c in element.children))).strip().replace('\xa0', ' ')


class MT5ReportParser:
    def parse(self, file_path):
        print(f"\n🔍 Processando: {file_path}")
        
        html_content = None
        encodings = ['utf-8-sig', 'utf-16', 'cp1252', 'latin-1']
        
        for enc in encodings:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    html_content = f.read()
                print(f"   ✓ Encoding: {enc}")
                break 
            except (UnicodeDecodeError, UnicodeError):
                continue
        
        if html_content is None:
            raise ValueError(f"Erro de codificação em {file_path}")

        soup = BeautifulSoup(html_content, 'html.parser')
        trades = []
        report_info = self._extract_report_info(soup)
        trades = self._extract_trades(soup)

        print(f"   ✅ Total de trades extraídos: {len(trades)}")
        return trades, report_info

    def _extract_report_info(self, soup):
        info = {}
        text = soup.get_text().replace('\xa0', ' ')
        patterns = {
            'expert_advisor': r'Expert Advisor\s*\(Robô\):\s*(.+?)(?:\n|$)',
            'symbol': r'Ativo:\s*([\w\$\.]+)',
            'period': r'Per[íi]odo:\s*(.+)',
            'initial_deposit': r'Dep[óo]sito Inicial:\s*([\d\.,]+)',
            'currency': r'Moeda:\s*([\w]+)',
            'leverage': r'Alavancagem:\s*([\d:]+)',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info[key] = match.group(1).strip()
        return info

    def _extract_trades(self, soup):
        trades = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2: continue
            
            # BUSCAR SEÇÃO "TRANSAÇÕES"
            transacoes_header_idx = None
            transacoes_headers = None
            
            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                # Títulos de seção no MT5 ficam em uma única célula com colspan
                if len(cells) == 1:
                    cell_text = get_text_deep(cells[0]).lower().strip()
                    if 'transações' in cell_text or 'transacoes' in cell_text:
                        print(f"   🎯 Seção 'Transações' encontrada na linha {i}")
                        # O cabeçalho real vem nas próximas 1-5 linhas
                        for j in range(i+1, min(i+6, len(rows))):
                            hdr_cells = rows[j].find_all(['td', 'th'])
                            if len(hdr_cells) >= 10:  # Tabela de trades tem muitas colunas
                                transacoes_headers = [get_text_deep(c) for c in hdr_cells]
                                transacoes_header_idx = j
                                print(f"   📋 Cabeçalhos detectados: {transacoes_headers[:12]}")
                                break
                        break
            
            if not transacoes_headers:
                continue
                
            # Validar se é realmente a tabela de trades (precisa ter Lucro e Horário)
            headers_lower = ' '.join([h.lower() for h in transacoes_headers])
            if 'lucro' not in headers_lower and 'profit' not in headers_lower:
                continue
            if 'horário' not in headers_lower and 'horario' not in headers_lower:
                continue
                
            headers = [h.lower() for h in transacoes_headers]
            col_map = self._map_columns(headers)
            print(f"   🗺️ Mapeamento de colunas: {col_map}")
            
            if 'profit' not in col_map or 'open_time' not in col_map:
                print("   ⚠️ Colunas essenciais (Lucro ou Horário) não mapeadas")
                continue
                
            # EXTRAIR DADOS
            for row in rows[transacoes_header_idx+1:]:
                cells = row.find_all(['td'])
                if len(cells) < 10: continue
                
                # Parar se encontrar nova seção ou imagem
                if len(cells) == 1:
                    cell_text = get_text_deep(cells[0]).lower()
                    if any(s in cell_text for s in ['ordens', 'relatório', 'configuração', 'resultados']):
                        break
                    if 'img' in str(cells[0]).lower():
                        break
                        
                try:
                    trade = {
                        'ticket': self._safe_get(cells, col_map.get('ticket'), 'int'),
                        'open_time': self._parse_datetime(self._safe_get(cells, col_map.get('open_time'), 'str')),
                        'type': self._safe_get(cells, col_map.get('type'), 'str'),
                        'size': self._safe_get(cells, col_map.get('size'), 'float'),
                        'symbol': self._safe_get(cells, col_map.get('symbol'), 'str'),
                        'open_price': self._safe_get(cells, col_map.get('open_price'), 'float'),
                        'commission': self._safe_get(cells, col_map.get('commission'), 'float'),
                        'swap': self._safe_get(cells, col_map.get('swap'), 'float'),
                        'profit': self._safe_get(cells, col_map.get('profit'), 'float'),
                        'comment': self._safe_get(cells, col_map.get('comment'), 'str')
                    }
                    
                    if trade['open_time'] and trade['profit'] is not None:
                        trades.append(trade)
                        
                except Exception:
                    continue

        return trades

    def _map_columns(self, headers):
        mapping = {}
        for i, h in enumerate(headers):
            h_lower = h.lower().strip()
            
            if any(k in h_lower for k in ['oferta', 'ticket', '#', 'deal', 'negócio']): mapping['ticket'] = i
            elif any(k in h_lower for k in ['horário', 'horario', 'data', 'time', 'abertura']): mapping['open_time'] = i
            elif any(k in h_lower for k in ['tipo', 'type', 'action', 'direção', 'direcao', 'buy', 'sell', 'in', 'out']): mapping['type'] = i
            elif any(k in h_lower for k in ['volume', 'size', 'lots', 'lotes', 'tamanho', 'quantidade']): mapping['size'] = i
            elif any(k in h_lower for k in ['ativo', 'symbol', 'security', 'símbolo', 'simbolo', 'par', 'instrumento']): mapping['symbol'] = i
            elif any(k in h_lower for k in ['preço', 'preco', 'price', 'abertura']): mapping['open_price'] = i
            elif any(k in h_lower for k in ['comissão', 'comissao', 'commission', 'taxa']): mapping['commission'] = i
            elif 'swap' in h_lower: mapping['swap'] = i
            elif any(k in h_lower for k in ['lucro', 'profit', 'resultado', 'gain', 'loss', 'p&l']): mapping['profit'] = i
            elif any(k in h_lower for k in ['saldo', 'balance']): mapping['balance'] = i
            elif any(k in h_lower for k in ['comentário', 'comentario', 'comment', 'nota']): mapping['comment'] = i
                
        return mapping

    def _safe_get(self, cells, index, dtype='str'):
        if index is None or index >= len(cells): return None
        text = get_text_deep(cells[index])
        if not text or text in ('—', '-', 'n/a', '', 'None', 'filled', 'done'): return None
        try:
            if dtype == 'int': 
                clean = re.sub(r'[^\d,-]', '', text.replace('.', ''))
                return int(clean) if clean else None
            elif dtype == 'float': 
                clean = re.sub(r'[^\d,.-]', '', text).replace('.', '').replace(',', '.')
                return float(clean) if clean else None
            else: return text.strip()
        except: return None

    def _parse_datetime(self, text):
        if not text: return None
        text = text.strip().replace('\xa0', ' ').replace('  ', ' ')
        formats = [
            '%Y.%m.%d %H:%M:%S', '%Y.%m.%d %H:%M',
            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
            '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M',
            '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M'
        ]
        for fmt in formats:
            try: return datetime.strptime(text, fmt)
            except ValueError: continue
        return None