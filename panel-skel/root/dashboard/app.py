#!/usr/bin/env python3
import os
import json
import subprocess
import threading
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

SCRIPTS_DIR = "/root/scripts"
STATUS_FILE = "/tmp/script_status.json"
HISTORY_FILE = "/tmp/script_history.json"

def init_files():
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    for f in [STATUS_FILE, HISTORY_FILE]:
        if not os.path.exists(f):
            with open(f, 'w') as fp:
                json.dump({}, fp)

def get_scripts():
    scripts = []
    if not os.path.exists(SCRIPTS_DIR):
        return scripts
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    with open(HISTORY_FILE, 'r') as f:
        history_data = json.load(f)
    for fn in sorted(os.listdir(SCRIPTS_DIR)):
        if fn.endswith('.py'):
            p = os.path.join(SCRIPTS_DIR, fn)
            st = os.stat(p)
            s = status_data.get(fn, {'status': 'idle'})
            h = history_data.get(fn, [])
            last_run = h[-1]['time'] if h else None
            scripts.append({
                'name': fn,
                'size': st.st_size,
                'mtime': datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'status': s.get('status', 'idle'),
                'last_run': last_run,
                'history_count': len(h)
            })
    return scripts

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/scripts')
def api_scripts():
    return jsonify(get_scripts())

@app.route('/api/run/<name>', methods=['POST'])
def run_script(name):
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return jsonify({'error': '脚本不存在'}), 404
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    status_data[name] = {'status': 'running'}
    with open(STATUS_FILE, 'w') as f:
        json.dump(status_data, f)
    
    def bg_run():
        start = datetime.now().isoformat()
        try:
            result = subprocess.run(
                ['python3', path],
                capture_output=True,
                text=True,
                timeout=300
            )
            output = result.stdout + result.stderr
            status = 'success' if result.returncode == 0 else 'failed'
        except subprocess.TimeoutExpired:
            output = '⏱ 超时'
            status = 'timeout'
        except Exception as e:
            output = f'❌ 异常: {str(e)}'
            status = 'error'
        
        with open(STATUS_FILE, 'r') as f:
            status_data = json.load(f)
        status_data[name] = {'status': status, 'last_output': output[:10000]}
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_data, f)
        
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        history.setdefault(name, []).append({
            'time': start,
            'status': status,
            'output': output[:500]
        })
        if len(history[name]) > 50:
            history[name] = history[name][-50:]
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)
    
    threading.Thread(target=bg_run, daemon=True).start()
    return jsonify({'message': f'✅ {name} 已开始执行'})

@app.route('/api/log/<name>')
def get_log(name):
    with open(STATUS_FILE, 'r') as f:
        status_data = json.load(f)
    s = status_data.get(name, {})
    return jsonify({
        'status': s.get('status', 'idle'),
        'output': s.get('last_output', '暂无输出')
    })

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🐍 脚本面板</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f0f2f5;padding:16px}
.container{max-width:1200px;margin:0 auto}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 24px;border-radius:12px;margin-bottom:20px}
.header h1{font-size:22px}.header .sub{opacity:.8;font-size:13px;margin-top:4px}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.stat-card{background:#fff;padding:12px 20px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.06);flex:1;min-width:80px}
.stat-card .num{font-size:24px;font-weight:700;color:#333}
.stat-card .label{font-size:12px;color:#999}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.card{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 1px 4px rgba(0,0,0,.06);border-left:4px solid #ddd}
.card.idle{border-left-color:#90a4ae}
.card.running{border-left-color:#ff9800;animation:pulse 1.2s infinite}
.card.success{border-left-color:#4caf50}
.card.failed{border-left-color:#f44336}
.card.timeout{border-left-color:#ff5722}
.card.error{border-left-color:#9c27b0}
@keyframes pulse{0%,100%{border-left-color:#ff9800}50%{border-left-color:#ffcc80}}
.card .top{display:flex;justify-content:space-between;align-items:center}
.card .name{font-weight:600;font-size:15px;word-break:break-all}
.badge{font-size:11px;padding:2px 12px;border-radius:20px;font-weight:500;flex-shrink:0;margin-left:10px}
.badge.idle{background:#eceff1;color:#546e7a}
.badge.running{background:#fff3e0;color:#e65100}
.badge.success{background:#e8f5e9;color:#1b5e20}
.badge.failed{background:#fce4ec;color:#b71c1c}
.badge.timeout{background:#fbe9e7;color:#bf360c}
.badge.error{background:#f3e5f5;color:#4a148c}
.card .info{margin-top:10px;font-size:13px;color:#666;line-height:1.6}
.card .info .lbl{color:#999}
.card .actions{margin-top:12px;display:flex;gap:6px;flex-wrap:wrap}
.card .actions button{padding:5px 14px;border:none;border-radius:6px;font-size:13px;cursor:pointer;font-weight:500}
.btn-run{background:#667eea;color:#fff}
.btn-run:hover{background:#5a6fd6}
.btn-run:disabled{opacity:.5;cursor:not-allowed}
.btn-log{background:#eceff1;color:#333}
.btn-log:hover{background:#d5d9de}
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;justify-content:center;align-items:center}
.modal.active{display:flex}
.modal-box{background:#fff;border-radius:14px;padding:24px;max-width:680px;width:92%;max-height:80vh;overflow-y:auto}
.modal-box h2{font-size:17px;margin-bottom:4px}
.modal-box .meta{font-size:13px;color:#888;margin-bottom:12px}
.modal-box pre{background:#1e1e1e;color:#d4d4d4;padding:14px;border-radius:8px;font-size:12px;line-height:1.5;max-height:400px;overflow:auto;white-space:pre-wrap;word-break:break-all}
.close{float:right;font-size:24px;cursor:pointer;color:#888}
.close:hover{color:#333}
.empty{padding:60px 20px;text-align:center;color:#999}
.refresh-btn{background:#fff;border:1px solid #ddd;padding:6px 16px;border-radius:8px;cursor:pointer;font-size:13px}
.refresh-btn:hover{background:#f5f5f5}
@media(max-width:600px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🐍 脚本面板</h1>
<div class="sub">📁 /root/scripts &nbsp;|&nbsp; ⏱ 自动刷新 10s</div>
</div>
<div class="stats" id="stats">
<div class="stat-card"><div class="num" id="total">0</div><div class="label">📄 总数</div></div>
<div class="stat-card"><div class="num" id="running">0</div><div class="label">🔄 运行中</div></div>
<div class="stat-card"><div class="num" id="success">0</div><div class="label">✅ 成功</div></div>
<div class="stat-card"><div class="num" id="failed">0</div><div class="label">❌ 失败</div></div>
<div class="stat-card" style="flex:0"><button class="refresh-btn" onclick="load()">🔄 刷新</button></div>
</div>
<div class="grid" id="grid"></div>
</div>

<div class="modal" id="modal"><div class="modal-box"><span class="close" onclick="closeModal()">&times;</span><h2 id="mTitle">日志</h2><div class="meta" id="mMeta"></div><pre id="mContent">暂无</pre></div></div>

<script>
function st(s){return{s:'idle',txt:'待执行'}[s]||{s:s,txt:s}}
function badge(s){return`<span class="badge ${s}">${st(s).txt}</span>`}
function load(){fetch('/api/scripts').then(r=>r.json()).then(data=>{
const g=document.getElementById('grid')
if(!data||!data.length){g.innerHTML='<div class="empty">📂 暂无脚本<br><small>请将 .py 文件放入 /root/scripts/</small></div>';return}
let rn=0,su=0,fa=0
g.innerHTML=data.map(s=>{const st=s.status||'idle';if(st==='running')rn++;if(st==='success')su++;if(['failed','timeout','error'].includes(st))fa++
return`<div class="card ${st}"><div class="top"><span class="name">${s.name}</span>${badge(st)}</div>
<div class="info"><span class="lbl">📏</span> ${(s.size/1024).toFixed(1)}KB &nbsp; <span class="lbl">🕐</span> ${s.mtime}<br><span class="lbl">⏱</span> ${s.last_run||'从未运行'} &nbsp; <span class="lbl">📋</span> ${s.history_count||0}次</div>
<div class="actions"><button class="btn-run" onclick="run('${s.name}')" ${st==='running'?'disabled':''}>▶ 运行</button><button class="btn-log" onclick="log('${s.name}')">📄 日志</button></div></div>`
}).join('')
document.getElementById('total').textContent=data.length
document.getElementById('running').textContent=rn
document.getElementById('success').textContent=su
document.getElementById('failed').textContent=fa
})}
function run(n){if(!confirm(`确定执行 "${n}" ?`))return;fetch(`/api/run/${encodeURIComponent(n)}`,{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.message||'已执行');load()})}
function log(n){fetch(`/api/log/${encodeURIComponent(n)}`).then(r=>r.json()).then(d=>{document.getElementById('mTitle').textContent='📄 '+n;document.getElementById('mMeta').textContent='状态: '+st(d.status).txt;document.getElementById('mContent').textContent=d.output||'暂无输出';document.getElementById('modal').classList.add('active')})}
function closeModal(){document.getElementById('modal').classList.remove('active')}
document.getElementById('modal').addEventListener('click',function(e){if(e.target===this)closeModal()})
load();setInterval(load,10000)
</script>
</body>
</html>
'''

if __name__ == '__main__':
    init_files()
    app.run(host='0.0.0.0', port=5000, debug=False)
