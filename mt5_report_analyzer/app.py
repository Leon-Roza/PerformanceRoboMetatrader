from flask import Flask, render_template, jsonify, request
from mt5_parser import MT5ReportParser
from kpi_engine import KPIEngine
import os
import glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
REPORT_FOLDER = os.path.join(BASE_DIR, 'reports')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

parser = MT5ReportParser()
kpi_engine = KPIEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/files', methods=['GET'])
def list_files():
    report_files = glob.glob(os.path.join(REPORT_FOLDER, '*.html'))
    report_files += glob.glob(os.path.join(REPORT_FOLDER, '*.htm'))
    
    files = []
    for f in sorted(report_files):
        try:
            files.append({
                'name': os.path.basename(f),
                'size_kb': round(os.path.getsize(f) / 1024, 2),
                'path': f
            })
        except Exception as e:
            print(f"Erro ao ler arquivo {f}: {e}")
            continue
            
    return jsonify({'files': files})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    print("✅ Rota /api/analyze acessada!")
    
    report_files = glob.glob(os.path.join(REPORT_FOLDER, '*.html'))
    report_files += glob.glob(os.path.join(REPORT_FOLDER, '*.htm'))

    if not report_files:
        print("❌ Nenhum arquivo encontrado")
        return jsonify({'success': False, 'error': 'Nenhum arquivo encontrado na pasta reports/'}), 404

    all_trades = []
    parsed_reports = []
    experts_found = {}

    for file_path in report_files:
        try:
            print(f"📄 Processando: {os.path.basename(file_path)}")
            trades, report_info = parser.parse(file_path)
            
            # Extrair nome do expert advisor
            expert_name = report_info.get('expert_advisor', 'Desconhecido')
            print(f"   🤖 Expert Advisor: {expert_name}")
            print(f"   📊 Trades extraídos: {len(trades)}")
            
            if expert_name not in experts_found:
                experts_found[expert_name] = []
            
            # Adicionar trades com nome do robô
            for trade in trades:
                trade['expert_advisor'] = expert_name
            
            experts_found[expert_name].extend(trades)
            all_trades.extend(trades)
            
            parsed_reports.append({
                'filename': os.path.basename(file_path),
                'total_trades': len(trades),
                'expert_advisor': expert_name
            })
        except Exception as e:
            print(f"❌ Erro ao processar {file_path}: {e}")
            import traceback
            traceback.print_exc()

    if not all_trades:
        print("❌ Nenhuma operação encontrada")
        return jsonify({
            'success': False, 
            'error': 'Nenhuma operação válida encontrada nos relatórios.'
        }), 404

    print(f"✅ Total de trades: {len(all_trades)}")
    print(f"🤖 Robôs encontrados: {list(experts_found.keys())}")

    # Gerar análise completa de TODOS os robôs
    analysis = kpi_engine.analyze(all_trades)
    
    # Gerar análise individual por robô
    analysis_by_robot = {}
    for expert_name, trades in experts_found.items():
        if trades:
            print(f"📈 Calculando KPIs para: {expert_name} ({len(trades)} trades)")
            analysis_by_robot[expert_name] = kpi_engine.analyze(trades)

    return jsonify({
        'success': True,
        'reports_analyzed': len(parsed_reports),
        'experts': sorted(list(experts_found.keys())),
        'report_details': parsed_reports,
        'analysis': analysis,
        'analysis_by_robot': analysis_by_robot
    })

if __name__ == '__main__':
    os.makedirs(REPORT_FOLDER, exist_ok=True)
    print("🚀 Servidor iniciado em http://localhost:5000")
    print(f"📁 Pasta de relatórios: {REPORT_FOLDER}")
    app.run(debug=True, port=5000)