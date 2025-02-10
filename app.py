from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from werkzeug.utils import secure_filename
import os
from collections import defaultdict
import mimetypes
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from dotenv import load_dotenv

# Cargar variables de entorno primero
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-por-defecto')  # Valor por defecto para desarrollo

# Configurar Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Debes iniciar sesión para acceder a esta página'
login_manager.login_message_category = 'error'

# Configuración de usuario
USUARIO = os.getenv('APP_USER', 'admin')
CONTRASENA = os.getenv('APP_PASSWORD', 'admin123')

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id == USUARIO else None

# Ruta raíz que redirige al login
@app.route('/')
def root():
    return redirect(url_for('login'))

# Ruta de login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        contrasena = request.form.get('contrasena')
        
        if usuario == USUARIO and contrasena == CONTRASENA:
            user = User(USUARIO)
            login_user(user)
            return redirect(url_for('index'))
        
        return render_template('login.html', error='Credenciales inválidas')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Conexión a la base de datos SQLite
def get_db_connection():
    conn = sqlite3.connect('data/clientes.db')
    conn.row_factory = sqlite3.Row
    return conn

# Crear tablas si no existen
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS destinatarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER,
            nombre TEXT,
            email TEXT,
            tipo TEXT,  -- 'principal' o 'cc'
            FOREIGN KEY(cliente_id) REFERENCES clientes(id)
        )
    ''')
    conn.commit()
    conn.close()

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ruta principal protegida
@app.route('/index')
@login_required
def index():
    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('index.html', clientes=clientes)

@app.route('/crear_cliente', methods=['GET', 'POST'])
@login_required
def crear_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        conn = get_db_connection()
        conn.execute('INSERT INTO clientes (nombre) VALUES (?)', (nombre,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('crear_cliente.html')

@app.route('/eliminar_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def eliminar_cliente(cliente_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM destinatarios WHERE cliente_id = ?', (cliente_id,))
    conn.execute('DELETE FROM clientes WHERE id = ?', (cliente_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/editar_cliente/<int:cliente_id>', methods=['GET'])
@login_required
def editar_cliente(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    conn.close()
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/actualizar_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def actualizar_cliente(cliente_id):
    nuevo_nombre = request.form['nombre']
    conn = get_db_connection()
    conn.execute('UPDATE clientes SET nombre = ? WHERE id = ?', (nuevo_nombre, cliente_id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/agregar_destinatarios/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def agregar_destinatarios(cliente_id):
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        tipo = request.form['tipo']
        conn = get_db_connection()
        conn.execute('INSERT INTO destinatarios (cliente_id, nombre, email, tipo) VALUES (?, ?, ?, ?)',
                     (cliente_id, nombre, email, tipo))
        conn.commit()
        conn.close()
        return redirect(url_for('agregar_destinatarios', cliente_id=cliente_id))

    conn = get_db_connection()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    destinatarios = conn.execute('SELECT * FROM destinatarios WHERE cliente_id = ?', (cliente_id,)).fetchall()
    conn.close()
    return render_template('agregar_destinatarios.html', cliente=cliente, destinatarios=destinatarios)

@app.route('/enviar_correo_global', methods=['GET', 'POST'])
@login_required
def enviar_correo_global():
    if request.method == 'POST':
        cliente_ids = request.form.getlist('clientes')
        asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']
        archivos = request.files.getlist('archivos')

        conn = get_db_connection()
        destinatarios = conn.execute(f'''
            SELECT cliente_id, email, tipo 
            FROM destinatarios 
            WHERE cliente_id IN ({','.join('?'*len(cliente_ids))})
        ''', cliente_ids).fetchall()
        conn.close()

        clientes_dict = defaultdict(lambda: {'to': [], 'cc': []})
        for d in destinatarios:
            key = 'to' if d['tipo'] == 'principal' else 'cc'
            clientes_dict[d['cliente_id']][key].append(d['email'])

        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASSWORD")

        try:
            adjuntos = []
            for archivo in archivos:
                if archivo.filename and allowed_file(archivo.filename):
                    filename = secure_filename(archivo.filename)
                    file_data = archivo.read()
                    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                    adjuntos.append({
                        'filename': filename,
                        'data': file_data,
                        'mime_type': mime_type
                    })
                    archivo.seek(0)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)

                for cliente_id, emails in clientes_dict.items():
                    msg = MIMEMultipart()
                    msg['From'] = smtp_user
                    msg['To'] = ", ".join(emails['to'])
                    if emails['cc']:
                        msg['Cc'] = ", ".join(emails['cc'])
                    msg['Subject'] = asunto
                    msg.attach(MIMEText(cuerpo, 'html'))
                    
                    for adjunto in adjuntos:
                        part = MIMEApplication(adjunto['data'], Name=adjunto['filename'])
                        part['Content-Disposition'] = f'attachment; filename="{adjunto["filename"]}"'
                        part['Content-Type'] = adjunto['mime_type']
                        msg.attach(part)
                    
                    server.sendmail(smtp_user, emails['to'] + emails['cc'], msg.as_string())

            return redirect(url_for('index'))
        
        except Exception as e:
            error_message = f"Error al enviar el correo: {str(e)}"
            print(error_message)
            return render_template('error.html', error=error_message)

    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('enviar_correo_global.html', clientes=clientes)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)