import os
import glob
import subprocess
from functools import wraps
from flask import Flask, request, Response, render_template_string, send_from_directory, redirect, url_for

app = Flask(__name__)

# GÜVENLİK AYARLARI
USERNAME = 'admin'
PASSWORD = '123'

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output_audio')

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        'Erişim reddedildi.', 401,
        {'WWW-Authenticate': 'Basic realm="KitapDuy Yönetmen Paneli"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def get_system_status():
    try:
        result = subprocess.run(['tmux', 'has-session', '-t', 'kitap'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def get_tmux_logs(lines=80):
    """tmux oturumunun son N satırını döndürür."""
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-p', '-t', 'kitap', '-S', f'-{lines}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
        return "(Üretim oturumu şu an kapalı veya henüz başlamadı.)"
    except Exception as e:
        return f"(Log alınırken hata: {e})"

def get_avci_logs(lines=15):
    """Avcı botun son N satırını döndürür."""
    try:
        result = subprocess.run(
            ['tmux', 'capture-pane', '-p', '-t', 'avci', '-S', f'-{lines}'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "(Avcı Bot kapalı veya çalışmıyor.)"
    except Exception as e:
        return f"(Log alınırken hata: {e})"

def get_stats():
    """Üretim istatistiklerini hesaplar."""
    stats = {'total_files': 0, 'total_size_mb': 0, 'books': {}}
    if os.path.exists(OUTPUT_DIR):
        for book_folder in os.listdir(OUTPUT_DIR):
            folder_path = os.path.join(OUTPUT_DIR, book_folder)
            if os.path.isdir(folder_path):
                audio_files = glob.glob(os.path.join(folder_path, '*.mp3')) + glob.glob(os.path.join(folder_path, '*.wav'))
                total_size = sum(os.path.getsize(f) for f in audio_files)
                stats['books'][book_folder] = {
                    'count': len(audio_files),
                    'size_mb': round(total_size / (1024*1024), 1)
                }
                stats['total_files'] += len(audio_files)
                stats['total_size_mb'] += total_size / (1024*1024)
    stats['total_size_mb'] = round(stats['total_size_mb'], 1)
    return stats

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KitapDuy Yönetmen Paneli</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #080d14;
            --surface: #0f1923;
            --surface2: #162030;
            --border: rgba(255,255,255,0.07);
            --text: #e2e8f0;
            --muted: #64748b;
            --accent: #3b82f6;
            --accent-glow: rgba(59,130,246,0.15);
            --green: #10b981;
            --green-glow: rgba(16,185,129,0.2);
            --red: #ef4444;
            --red-glow: rgba(239,68,68,0.2);
            --yellow: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 10% 0%, rgba(59,130,246,0.08) 0%, transparent 60%),
                radial-gradient(ellipse at 90% 100%, rgba(16,185,129,0.05) 0%, transparent 60%);
        }
        
        /* LAYOUT */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(8,13,20,0.9);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 60px;
        }
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon {
            width: 32px; height: 32px;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 16px;
        }
        .logo-text { font-weight: 700; font-size: 1rem; letter-spacing: -0.02em; }
        .logo-sub { font-size: 0.7rem; color: var(--muted); }
        
        .container { max-width: 1100px; margin: 0 auto; padding: 28px 20px; }
        
        /* STATS ROW */
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
        }
        .stat-label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
        .stat-value { font-size: 1.6rem; font-weight: 700; letter-spacing: -0.03em; }
        .stat-value.green { color: var(--green); }
        .stat-value.blue { color: var(--accent); }
        .stat-value.yellow { color: var(--yellow); }
        
        /* STATUS CARD */
        .status-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }
        .status-left { display: flex; align-items: center; gap: 16px; }
        .status-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .status-dot.running {
            background: var(--green);
            box-shadow: 0 0 12px var(--green);
            animation: pulse 2s infinite;
        }
        .status-dot.stopped {
            background: var(--red);
            box-shadow: 0 0 8px var(--red-glow);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .status-label { font-weight: 600; font-size: 1rem; }
        .status-sub { font-size: 0.8rem; color: var(--muted); margin-top: 2px; }
        
        .btn {
            padding: 9px 18px;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            text-decoration: none;
            color: white;
            transition: all 0.15s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-start { background: var(--green); box-shadow: 0 0 20px var(--green-glow); }
        .btn-stop { background: var(--red); box-shadow: 0 0 20px var(--red-glow); }
        .btn-delete {
            background: transparent;
            color: var(--red);
            border: 1px solid rgba(239,68,68,0.3);
            padding: 5px 10px;
            font-size: 0.78rem;
        }
        .btn:hover { opacity: 0.85; transform: translateY(-1px); }
        
        /* SECTION HEADER */
        .section-title {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--muted);
            margin-bottom: 12px;
            margin-top: 28px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .section-title::after {
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border);
        }
        
        /* AUDIO LIST */
        .book-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 16px;
        }
        .book-header {
            padding: 14px 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 12px;
            background: var(--surface2);
        }
        .book-badge {
            background: var(--accent-glow);
            color: var(--accent);
            border: 1px solid rgba(59,130,246,0.2);
            border-radius: 6px;
            padding: 3px 10px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .file-list { list-style: none; }
        .file-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 20px;
            border-bottom: 1px solid var(--border);
            gap: 12px;
            transition: background 0.1s;
            flex-wrap: wrap;
        }
        .file-item:last-child { border-bottom: none; }
        .file-item:hover { background: rgba(255,255,255,0.02); }
        .file-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .file-idx {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--muted);
            min-width: 30px;
        }
        .file-name { font-size: 0.9rem; font-weight: 500; }
        audio {
            height: 32px;
            max-width: 260px;
            border-radius: 6px;
            accent-color: var(--accent);
        }
        
        /* LOG BOX */
        .log-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            margin-bottom: 20px;
        }
        .log-header {
            padding: 12px 20px;
            border-bottom: 1px solid var(--border);
            background: var(--surface2);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .log-title { font-size: 0.85rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .live-badge {
            background: var(--green-glow);
            color: var(--green);
            border: 1px solid rgba(16,185,129,0.3);
            border-radius: 4px;
            padding: 2px 7px;
            font-size: 0.68rem;
            font-weight: 700;
            letter-spacing: 0.05em;
        }
        .log-body {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            line-height: 1.7;
            padding: 16px 20px;
            max-height: 380px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-break: break-word;
            color: #94a3b8;
        }
        /* Log renklendirme */
        .log-body .ok { color: var(--green); }
        .log-body .warn { color: var(--yellow); }
        .log-body .err { color: var(--red); }
        .log-body .info { color: var(--accent); }
        
        .empty-state {
            padding: 40px;
            text-align: center;
            color: var(--muted);
            font-size: 0.9rem;
        }
        
        /* YENİ KİTAP FORMU */
        .new-book-card {
            background: var(--surface);
            border: 1px solid rgba(59,130,246,0.25);
            border-radius: 16px;
            padding: 20px 24px;
            margin-bottom: 20px;
        }
        .new-book-title {
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .form-row {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .form-input {
            flex: 1;
            min-width: 200px;
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 14px;
            color: var(--text);
            font-size: 0.9rem;
            font-family: 'Inter', sans-serif;
            outline: none;
            transition: border-color 0.2s;
        }
        .form-input:focus { border-color: var(--accent); }
        .form-input::placeholder { color: var(--muted); }
        .btn-launch {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            box-shadow: 0 0 20px rgba(59,130,246,0.25);
            white-space: nowrap;
        }
        .form-hint {
            font-size: 0.75rem;
            color: var(--muted);
            margin-top: 10px;
        }
        
        /* AUTO REFRESH indicator */
        .refresh-bar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent), #8b5cf6);
            transform-origin: left;
            animation: shrink 15s linear forwards;
        }
        @keyframes shrink {
            from { transform: scaleX(1); }
            to { transform: scaleX(0); }
        }

        @media (max-width: 640px) {
            .stats-row { grid-template-columns: repeat(2, 1fr); }
            .status-card { flex-direction: column; align-items: flex-start; }
            audio { max-width: 100%; width: 100%; }
        }
    </style>
</head>
<body>
    <div class="topbar">
        <div class="logo">
            <div class="logo-icon">🎙️</div>
            <div>
                <div class="logo-text">KitapDuy</div>
                <div class="logo-sub">Yönetmen Paneli</div>
            </div>
        </div>
        <div style="font-size:0.75rem; color: var(--muted);">Otomatik yenileniyor (15s)</div>
    </div>

    <div class="container">
    
        <!-- STATS -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-label">Sistem Durumu</div>
                <div class="stat-value {% if is_running %}green{% else %}" style="color:var(--red){% endif %}">
                    {% if is_running %}Aktif{% else %}Durduruldu{% endif %}
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Üretilen Bölüm</div>
                <div class="stat-value blue">{{ stats.total_files }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Toplam Boyut</div>
                <div class="stat-value blue">{{ stats.total_size_mb }} MB</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Yaklaşık Süre</div>
                <div class="stat-value yellow">~{{ (stats.total_size_mb / 10.5) | round(1) }} dk</div>
            </div>
        </div>
        
        <!-- YENİ KİTAP BAŞLAT -->
        <div class="section-title">Yeni Kitap Başlat</div>
        <div class="new-book-card">
            <div class="new-book-title">📚 Kitap ID veya URL girin, sistem otomatik başlasın</div>
            <form action="/action/new_book" method="POST">
                <div class="form-row">
                    <input type="text" name="book_source" class="form-input"
                        placeholder="Gutenberg ID (örn: 902) veya sonsuz fabrika için 'auto' yazın"
                        required />
                    <button type="submit" class="btn btn-launch">🚀 Seslendirmeyi Başlat</button>
                </div>
                <div class="form-hint">
                    💡 Mevcut üretim durdurulur ve yeni kitap başlar. Gutenberg ID veya herhangi bir kitap URL'si girebilirsiniz.
                </div>
            </form>
        </div>

        <!-- STATUS + CONTROLS -->
        <div class="status-card">
            <div class="status-left">
                <div class="status-dot {% if is_running %}running{% else %}stopped{% endif %}"></div>
                <div>
                    <div class="status-label">{% if is_running %}Üretim Aktif — Kitap seslendiriliyor...{% else %}Üretim Durduruldu{% endif %}</div>
                    <div class="status-sub">Sunucu: 158.180.24.79 · Sefiller (Kitap ID: 135)</div>
                </div>
            </div>
            <div>
                {% if is_running %}
                <a href="/action/stop" class="btn btn-stop">⏹ Durdur</a>
                {% else %}
                <a href="/action/start" class="btn btn-start">▶ Başlat / Devam Et</a>
                {% endif %}
            </div>
        </div>

        <!-- AVCI BOT STATUS -->
        <div class="status-card" style="border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.03);">
            <div class="status-left" style="width: 100%;">
                <div class="status-dot running" style="background: var(--yellow); box-shadow: 0 0 12px var(--yellow);"></div>
                <div style="flex: 1; width: 100%;">
                    <div class="status-label" style="color: var(--yellow);">🦅 Avcı Bot Canlı Yayın</div>
                    <div class="status-sub" id="avciLogBox" style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; white-space: pre-wrap; margin-top: 8px; max-height: 100px; overflow-y: auto; color: #cbd5e1;">Yükleniyor...</div>
                </div>
            </div>
        </div>

        <!-- LIVE LOGS -->
        <div class="section-title">Canlı Üretim Logları</div>
        <div class="log-card">
            <div class="log-header">
                <div class="log-title">
                    tmux: kitap oturumu
                    {% if is_running %}<span class="live-badge">● CANLI</span>{% endif %}
                </div>
                <a href="/" style="color:var(--muted); text-decoration:none; font-size:0.8rem;">↻ Yenile</a>
            </div>
            <div class="log-body" id="logBox">{{ logs }}</div>
        </div>
        
        <!-- AUDIO FILES -->
        <div class="section-title">Üretilen Ses Dosyaları</div>
        {% for book, files in books.items() %}
        <div class="book-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div class="book-title" style="margin-bottom: 0;">📁 {{ book }}</div>
                <a href="/action/delete_book/{{ book }}" class="btn btn-delete" style="padding: 0.4rem 0.8rem; font-size: 0.85rem;" onclick="return confirm('Bu klasör ve içindeki TÜM dosyalar kalıcı olarak silinecek. Onaylıyor musunuz?');">🗑 Klasörü Sil</a>
            </div>
            <div class="book-header">
                <span class="book-badge">Kitap {{ book }}</span>
                <span style="color:var(--muted); font-size:0.8rem;">{{ files|length }} bölüm · {{ stats.books.get(book, {}).get('size_mb', 0) }} MB</span>
            </div>
            <ul class="file-list">
                {% if not files %}
                <li class="empty-state">Henüz ses dosyası üretilmemiş.</li>
                {% endif %}
                {% for f in files %}
                <li class="file-item">
                    <div class="file-meta">
                        <span class="file-idx">{{ loop.index }}.</span>
                        <span class="file-name">{{ f }}</span>
                        <audio controls preload="metadata">
                            <source src="/play/{{ book }}/{{ f }}">
                        </audio>
                    </div>
                    <a href="/action/delete/{{ book }}/{{ f }}" class="btn btn-delete"
                       onclick="return confirm('Bu dosya silinip baştan üretilecek. Onaylıyor musunuz?');">
                       🗑 Sil & Yeniden Üret
                    </a>
                </li>
                {% endfor %}
            </ul>
        </div>
        {% endfor %}
        
        {% if not books %}
        <div class="book-card">
            <div class="empty-state">Henüz hiçbir üretim klasörü bulunamadı. Sistemi başlatın!</div>
        </div>
        {% endif %}
        
    </div>
    
    <div class="refresh-bar" id="rbar"></div>

    <script>
        // Log kutusunu en alta kaydır
        var logBox = document.getElementById('logBox');
        if (logBox) logBox.scrollTop = logBox.scrollHeight;
        
        // Canlı Log Akışı (Sayfayı yenilemeden)
        setInterval(function() {
            fetch('/api/logs')
                .then(response => response.text())
                .then(data => {
                    var logBox = document.getElementById('logBox');
                    // Scroll eğer en altındaysa güncelledikten sonra tekrar en alta indir
                    var isAtBottom = (logBox.scrollHeight - logBox.scrollTop) <= (logBox.clientHeight + 20);
                    logBox.textContent = data;
                    if (isAtBottom) {
                        logBox.scrollTop = logBox.scrollHeight;
                    }
                })
                .catch(err => console.error("Loglar çekilemedi:", err));
                
            fetch('/api/avci_logs')
                .then(response => response.text())
                .then(data => {
                    var avciLogBox = document.getElementById('avciLogBox');
                    if(avciLogBox) {
                        avciLogBox.textContent = data;
                        avciLogBox.scrollTop = avciLogBox.scrollHeight;
                    }
                });
        }, 15000);
    </script>
</body>
</html>
"""

@app.route('/')
@requires_auth
def index():
    is_running = get_system_status()
    logs = get_tmux_logs(100)
    stats = get_stats()
    books = {}
    
    if os.path.exists(OUTPUT_DIR):
        for book_folder in sorted(os.listdir(OUTPUT_DIR)):
            folder_path = os.path.join(OUTPUT_DIR, book_folder)
            if os.path.isdir(folder_path):
                audio_files = glob.glob(os.path.join(folder_path, '*.mp3')) + glob.glob(os.path.join(folder_path, '*.wav'))
                audio_files = sorted([os.path.basename(w) for w in audio_files])
                books[book_folder] = audio_files

    return render_template_string(HTML_TEMPLATE, is_running=is_running, books=books, logs=logs, stats=stats)

@app.route('/play/<book_id>/<filename>')
@requires_auth
def play_audio(book_id, filename):
    folder_path = os.path.join(OUTPUT_DIR, book_id)
    return send_from_directory(folder_path, filename)

@app.route('/api/logs')
@requires_auth
def api_logs():
    return get_tmux_logs(100)

@app.route('/api/avci_logs')
@requires_auth
def api_avci_logs():
    return get_avci_logs(15)

@app.route('/action/start')
@requires_auth
def start_system():
    if not get_system_status():
        cmd = "tmux new-session -d -s kitap 'cd ~/KitapDuy_Bulut && . venv/bin/activate && export BOOK_SOURCE=135 && export BOOK_MODE=full && python3 main.py; exec bash'"
        subprocess.run(cmd, shell=True)
    return redirect(url_for('index'))

@app.route('/action/new_book', methods=['POST'])
@requires_auth
def new_book():
    book_source = request.form.get('book_source', '').strip()
    if not book_source:
        return redirect(url_for('index'))
    
    # Çalışan oturumu durdur
    subprocess.run(['tmux', 'kill-session', '-t', 'kitap'], capture_output=True)
    
    import time
    time.sleep(1)
    
    # Yeni kitabı başlat
    cmd = f"tmux new-session -d -s kitap 'cd ~/KitapDuy_Bulut && . venv/bin/activate && export BOOK_SOURCE={repr(book_source)} && export BOOK_MODE=full && python3 main.py; exec bash'"
    subprocess.run(cmd, shell=True)
    
    return redirect(url_for('index'))

@app.route('/action/stop')
@requires_auth
def stop_system():
    if get_system_status():
        subprocess.run(['tmux', 'kill-session', '-t', 'kitap'])
    return redirect(url_for('index'))

@app.route('/action/delete/<book_id>/<filename>')
@requires_auth
def delete_file(book_id, filename):
    file_path = os.path.join(OUTPUT_DIR, book_id, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect(url_for('index'))

@app.route('/action/delete_book/<book_id>')
@requires_auth
def delete_book(book_id):
    folder_path = os.path.join(OUTPUT_DIR, book_id)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        import shutil
        shutil.rmtree(folder_path)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
