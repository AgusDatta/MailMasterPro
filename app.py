from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)

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

@app.route('/')
def index():
    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('index.html', clientes=clientes)

@app.route('/crear_cliente', methods=['GET', 'POST'])
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
def eliminar_cliente(cliente_id):
    conn = get_db_connection()
    # Eliminar destinatarios asociados al cliente
    conn.execute('DELETE FROM destinatarios WHERE cliente_id = ?', (cliente_id,))
    # Eliminar el cliente
    conn.execute('DELETE FROM clientes WHERE id = ?', (cliente_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/editar_cliente/<int:cliente_id>', methods=['GET'])
def editar_cliente(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    conn.close()
    return render_template('editar_cliente.html', cliente=cliente)

@app.route('/actualizar_cliente/<int:cliente_id>', methods=['POST'])
def actualizar_cliente(cliente_id):
    nuevo_nombre = request.form['nombre']
    conn = get_db_connection()
    conn.execute('UPDATE clientes SET nombre = ? WHERE id = ?', (nuevo_nombre, cliente_id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/agregar_destinatarios/<int:cliente_id>', methods=['GET', 'POST'])
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
def enviar_correo_global():
    if request.method == 'POST':
        # Recoger datos del formulario
        cliente_ids = request.form.getlist('clientes')
        asunto = request.form['asunto']
        cuerpo = request.form['cuerpo']
        archivos = request.files.getlist('archivos')

        # Obtener destinatarios
        conn = get_db_connection()
        destinatarios = conn.execute('''
            SELECT email FROM destinatarios 
            WHERE cliente_id IN ({})
        '''.format(','.join('?' for _ in cliente_ids)), cliente_ids).fetchall()
        conn.close()

        # Configuración SMTP
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_user = "adattilio@4i.digital"
        smtp_password = "faru xueg ftia qgqc"

        try:
            # Preparar adjuntos una sola vez
            adjuntos = []
            for archivo in archivos:
                if archivo.filename != '':
                    file_data = archivo.read()
                    adjunto = {
                        'filename': secure_filename(archivo.filename),
                        'data': file_data,
                        'content_type': archivo.content_type
                    }
                    adjuntos.append(adjunto)

            # Enviar correos
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)

                for destinatario in destinatarios:
                    msg = MIMEMultipart()
                    msg['From'] = smtp_user
                    msg['To'] = destinatario['email']
                    msg['Subject'] = asunto
                    
                    # Cuerpo del mensaje
                    msg.attach(MIMEText(cuerpo, 'html'))
                    
                    # Adjuntar archivos
                    for adjunto in adjuntos:
                        part = MIMEApplication(
                            adjunto['data'],
                            Name=adjunto['filename']
                        )
                        part['Content-Disposition'] = f'attachment; filename="{adjunto["filename"]}"'
                        part['Content-Type'] = adjunto['content_type']
                        msg.attach(part)
                    
                    # Enviar mensaje
                    server.send_message(msg)

            return redirect(url_for('index'))
        
        except Exception as e:
            error_message = f"Error al enviar el correo: {str(e)}"
            print(error_message)
            return render_template('error.html', error=error_message)

    # GET: Mostrar formulario
    conn = get_db_connection()
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('enviar_correo_global.html', clientes=clientes)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)