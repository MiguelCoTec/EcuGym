from flask import Flask, render_template, request, redirect, url_for, session, make_response
from weasyprint import HTML
import pyodbc

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Datos de conexión a SQL Server
server = 'MIGUEL-COLIN\\SQLEXPRESS'  
database = 'ecugym'  
username = 'Administrador'  
password = 'admin123'  

def crear_conexion():
    conn = pyodbc.connect(f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}')
    return conn

@app.route('/')
def index():
    return render_template('index.html', error=False)

@app.route('/login', methods=['POST'])
def login():
    correo = request.form['email']
    contrasena = request.form['password']
    
    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        
        query = "SELECT id_usuario, nombre_usuario, rol FROM Usuario WHERE correo = ? AND contrasena = ?"
        cursor.execute(query, (correo, contrasena))
        usuario = cursor.fetchone()
        
        if usuario:
            session['id_usuario'] = usuario[0]
            session['nombre'] = usuario[1]
            session['rol'] = usuario[2]
            return redirect(url_for('menu'))
        else:
            return render_template('index.html', error=True)
    except Exception as e:
        print(f"Error al autenticar usuario: {e}")
        return "Ocurrió un error al autenticar el usuario."
    finally:
        conn.close()

@app.route('/menu')
def menu():
    if 'id_usuario' not in session:
        return redirect(url_for('index'))
    id_usuario = session['id_usuario']
    nombre = session['nombre']
    rol = session['rol']
    return render_template('menu.html', id_usuario=id_usuario, nombre=nombre, rol=rol)

@app.route('/nuevo_miembro')
def nuevo_miembro():
    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id_membresia, nombre_membresia FROM Membresia")
        membresias = [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]
        conn.close()
        return render_template('nuevo_miembro.html', membresias=membresias)
    except Exception as e:
        print(f"Error al obtener membresías: {e}")
        return "Ocurrió un error al cargar las membresías."

@app.route('/registrar_miembro', methods=['POST'])
def registrar_miembro():
    nombre = request.form['nombre']
    apellido = request.form['apellido']
    email = request.form['email']
    telefono = request.form['telefono']
    membresia_id = request.form['membresia']

    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        # Calcular fecha_inicio (GETDATE())
        query_fecha_inicio = "SELECT GETDATE()"
        cursor.execute(query_fecha_inicio)
        fecha_inicio = cursor.fetchone()[0]  # Obtener la fecha de inicio (GETDATE())

        # Insertar en la tabla Miembro
        query_miembro = """
        INSERT INTO Miembro (nombre, apellido, email, telefono, fecha_registro) 
        OUTPUT INSERTED.id_miembro -- Obtener el id generado 
        VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query_miembro, (nombre, apellido, email, telefono, fecha_inicio))
        miembro_id = cursor.fetchone()[0]  # Obtener el id generado por el primer INSERT

        # Obtener la vigencia de la membresía
        query_vigencia = "SELECT vigencia, nombre_membresia, costo FROM membresia WHERE id_membresia = ?"
        cursor.execute(query_vigencia, (membresia_id,))
        membresia_data = cursor.fetchone()
        if not membresia_data:
            raise Exception("Membresía no encontrada.")
        vigencia, nombre_membresia, costo = membresia_data  

        # Calcular fecha_fin sumando la vigencia a fecha_inicio
        query_fecha_fin = "SELECT DATEADD(DAY, ?, ?)"  # Sumar días a la fecha de inicio
        cursor.execute(query_fecha_fin, (vigencia, fecha_inicio))
        fecha_fin = cursor.fetchone()[0]  # Obtener la fecha de fin calculada

        # Insertar en la tabla miembro_membresia
        query_miembro_membresia = """
        INSERT INTO miembro_membresia (id_miembro, id_membresia, fecha_inicio, fecha_fin, estado) 
        VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query_miembro_membresia, (miembro_id, membresia_id, fecha_inicio, fecha_fin, 1))

        # Confirmar transacción
        conn.commit()
        conn.close()

        # Generar el ticket
        ticket_html = render_template('ticket_membresia.html',
                                      nombre=nombre,
                                      apellido=apellido,
                                      fecha_inicio=fecha_inicio.strftime('%d/%m/%Y'),
                                      nombre_membresia=nombre_membresia,
                                      precio=costo,
                                      fecha_fin=fecha_fin.strftime('%d/%m/%Y'))

        pdf = HTML(string=ticket_html).write_pdf()

        # Abrir el ticket en una nueva pestaña
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=ticket.pdf'
        
        # Redirigir al menú principal
        redirect_response = redirect(url_for('menu'))
        redirect_response.headers['Refresh'] = '0; url=/menu'  # Redirección automática
        
        return response
        #return redirect(url_for('menu'))
    except Exception as e:
        print(f"Error al registrar miembro y membresía: {e}")
        return "Ocurrió un error al registrar el miembro y su membresía."

@app.route('/membresias')
def membresias():
    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        # Consulta para obtener los datos de las membresías
        query = "SELECT nombre_membresia, descripcion, vigencia, costo FROM Membresia"
        cursor.execute(query)
        membresias = cursor.fetchall()

        conn.close()

        # Enviar datos al template
        return render_template('membresias.html', membresias=membresias)
    except Exception as e:
        print(f"Error al obtener membresías: {e}")
        return "Ocurrió un error al cargar las membresías."

@app.route('/nueva_venta')
def nueva_venta():
    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        query = "SELECT id_producto, nombre_producto, precio, existencia FROM Producto"
        cursor.execute(query)
        productos = [{"id": row[0], "nombre": row[1], "precio": row[2], "existencia": row[3]} for row in cursor.fetchall()]
        conn.close()
        return render_template('nueva_venta.html', productos=productos)
    except Exception as e:
        print(f"Error al cargar productos: {e}")
        return "Ocurrió un error al cargar los productos."


@app.route('/registrar_venta', methods=['POST'])
def registrar_venta():
    productos = request.form.getlist('producto[]')
    cantidades = list(map(int, request.form.getlist('cantidad[]')))
    precios = list(map(float, request.form.getlist('precio_unitario[]')))
    subtotales = list(map(float, request.form.getlist('subtotal[]')))
    comentarios = request.form['comentarios']
    total = sum(subtotales)
    usuario_id = session.get('id_usuario')
    usuario_nombre = session.get('nombre')

    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        # Registrar venta
        query_venta = """
            INSERT INTO Venta (id_usuario, fecha_venta, total_venta, comentarios)
            OUTPUT INSERTED.id_venta
            VALUES (?, GETDATE(), ?, ?)
        """
        cursor.execute(query_venta, (usuario_id, total, comentarios))
        venta_id = cursor.fetchone()[0]

        # Registrar detalle de la venta
        detalle_venta = []
        for producto_id, cantidad, precio_unitario, subtotal in zip(productos, cantidades, precios, subtotales):
            # Validar existencia
            cursor.execute("SELECT nombre_producto, existencia FROM Producto WHERE id_producto = ?", (producto_id,))
            producto = cursor.fetchone()
            nombre_producto, existencia = producto[0], producto[1]
            if cantidad > existencia:
                conn.rollback()
                return "Error: La cantidad solicitada supera la existencia del producto."

            # Actualizar existencia del producto
            cursor.execute("UPDATE Producto SET existencia = existencia - ? WHERE id_producto = ?", (cantidad, producto_id))

            # Insertar detalle de venta
            query_detalle = """
                INSERT INTO detalle_venta (id_venta, id_producto, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            """
            cursor.execute(query_detalle, (venta_id, producto_id, cantidad, precio_unitario))

            detalle_venta.append({
                'nombre_producto': nombre_producto,
                'cantidad': cantidad,
                'precio_unitario': precio_unitario,
                'subtotal': subtotal
            })

        # Confirmar transacción
        conn.commit()

        # Generar el ticket como PDF
        html_ticket = render_template('ticket_venta.html', 
                                       usuario_nombre=usuario_nombre, 
                                       detalle_venta=detalle_venta, 
                                       total=total, 
                                       comentarios=comentarios)
        pdf = HTML(string=html_ticket).write_pdf()

        # Enviar el PDF al cliente
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=ticket_venta.pdf'
        return response
        
        #return redirect(url_for('menu'))
    except Exception as e:
        print(f"Error al registrar venta: {e}")
        return "Ocurrió un error al registrar la venta."
    finally:
        conn.close()

@app.route('/inventario')
def inventario():
    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        # Consulta para obtener todos los productos del inventario
        query = """
        SELECT nombre_producto, descripcion, categoria, precio, existencia 
        FROM Producto
        """
        cursor.execute(query)
        productos = [
            {
                "nombre_producto": row[0],
                "descripcion": row[1],
                "categoria": row[2],
                "precio": row[3],
                "existencia": row[4],
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return render_template('inventario.html', productos=productos)
    except Exception as e:
        print(f"Error al cargar el inventario: {e}")
        return "Ocurrió un error al cargar el inventario."

@app.route('/cancelar_membresias')
def cancelar_membresias():
    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        cursor.execute("EXEC actualizar_membresia")
        conn.commit()

        query = """
            SELECT mm.id_miembro_membresia, m.nombre, mm.id_miembro, mm.id_membresia, mm.fecha_inicio, mm.fecha_fin
            FROM miembro_membresia mm
            INNER JOIN miembro AS m ON m.id_miembro = mm.id_miembro
            WHERE estado = 1
        """
        cursor.execute(query)
        membresias = [
            {
                "id_miembro_membresia": row[0],
                "nombre": row[1],
                "id_miembro": row[2],
                "id_membresia": row[3],
                "fecha_inicio": row[4],
                "fecha_fin": row[5]
            }
            for row in cursor.fetchall()
        ]
        conn.close()
        return render_template('cancelar_membresias.html', membresias=membresias)
    except Exception as e:
        print(f"Error al cargar las membresías activas: {e}")
        return "Ocurrió un error al cargar las membresías activas."


@app.route('/cancelar_membresia/<int:id_miembro_membresia>', methods=['POST'])
def cancelar_membresia(id_miembro_membresia):
    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        
        # Actualizar el estado de la membresía
        query = "UPDATE miembro_membresia SET estado = 0 WHERE id_miembro_membresia = ?"
        cursor.execute(query, (id_miembro_membresia,))
        
        # Confirmar transacción
        conn.commit()
        conn.close()
        return redirect(url_for('cancelar_membresias'))
    except Exception as e:
        print(f"Error al cancelar la membresía: {e}")
        return "Ocurrió un error al cancelar la membresía."


#Rol Administrador
@app.route('/agregar_usuario')
def agregar_usuario():
    if 'id_usuario' not in session or session['rol'] != 'Administrador':
        return redirect(url_for('index'))

    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        cursor.execute("SELECT id_usuario, nombre_usuario, rol, correo, telefono, fecha_creacion FROM Usuario")
        usuarios = [
            {
                "id_usuario": row[0],
                "nombre_usuario": row[1],
                "rol": row[2],
                "correo": row[3],
                "telefono": row[4],
                "fecha_creacion": row[5]
            } for row in cursor.fetchall()
        ]
        conn.close()
        return render_template('agregar_usuario.html', usuarios=usuarios)
    except Exception as e:
        print(f"Error al obtener usuarios: {e}")
        return "Ocurrió un error al cargar los usuarios."

@app.route('/editar_usuario/<int:id_usuario>', methods=['GET', 'POST'])
def editar_usuario(id_usuario):
    if 'rol' not in session or session['rol'] != 'Administrador':
        return redirect(url_for('index'))

    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        if request.method == 'POST':
            nombre_usuario = request.form['nombre_usuario']
            contrasena = request.form['contrasena']
            rol = request.form['rol']
            correo = request.form['correo']
            telefono = request.form['telefono']
            
            query = """
                UPDATE Usuario SET nombre_usuario = ?, contrasena = ?, rol = ?, correo = ?, telefono = ? 
                WHERE id_usuario = ?
            """
            cursor.execute(query, (nombre_usuario, contrasena, rol, correo, telefono, id_usuario))
            conn.commit()
            conn.close()
            return redirect(url_for('agregar_usuario'))

        # GET: Obtener datos del usuario a editar
        query = "SELECT nombre_usuario, rol, correo, telefono FROM Usuario WHERE id_usuario = ?"
        cursor.execute(query, (id_usuario,))
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            return render_template('editar_usuario.html', usuario=usuario, id_usuario=id_usuario)
        else:
            return "Usuario no encontrado."
    except Exception as e:
        print(f"Error al editar usuario: {e}")
        return "Ocurrió un error al editar el usuario."

@app.route('/eliminar_usuario/<int:id_usuario>', methods=['POST'])
def eliminar_usuario(id_usuario):
    if 'id_usuario' not in session or session['rol'] != 'Administrador':
        return redirect(url_for('index'))

    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        query = "DELETE FROM Usuario WHERE id_usuario = ?"
        cursor.execute(query, (id_usuario,))
        conn.commit()
        conn.close()
        return redirect(url_for('agregar_usuario'))
    except Exception as e:
        print(f"Error al eliminar usuario: {e}")
        return "Ocurrió un error al eliminar el usuario."


@app.route('/registrar_usuario', methods=['POST'])
def registrar_usuario():
    # Validar si el usuario tiene el rol de Administrador
    if 'id_usuario' not in session or session['rol'] != 'Administrador':
        return redirect(url_for('index'))

    nombre_usuario = request.form['nombre_usuario']
    contrasena = request.form['contrasena']
    rol = request.form['rol']
    correo = request.form['correo']
    telefono = request.form['telefono']

    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        
        # Obtener la fecha actual
        query_fecha = "SELECT GETDATE()"
        cursor.execute(query_fecha)
        fecha_creacion = cursor.fetchone()[0]

        # Insertar el nuevo usuario en la base de datos
        query = """
            INSERT INTO Usuario (nombre_usuario, contrasena, rol, fecha_creacion, correo, telefono)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (nombre_usuario, contrasena, rol, fecha_creacion, correo, telefono))
        
        # Confirmar transacción
        conn.commit()
        conn.close()
        return redirect(url_for('menu'))
    except Exception as e:
        print(f"Error al registrar usuario: {e}")
        return "Ocurrió un error al registrar el usuario."

@app.route('/administrar_miembros')
def administrar_miembros():
    if 'id_usuario' not in session:
        return redirect(url_for('index'))
    
    try:
        conn = crear_conexion()
        cursor = conn.cursor()
        query = "SELECT id_miembro, nombre, apellido, email, telefono, fecha_registro FROM Miembro"
        cursor.execute(query)
        miembros = cursor.fetchall()
        cursor.execute("SELECT id_membresia, nombre_membresia FROM Membresia")
        membresias = [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]
        conn.close()
        if session['rol'] == 'Administrador':
            return render_template('administrar_miembros.html', miembros=miembros, membresias=membresias)
        elif session['rol'] == 'Recepcionista':
            return render_template('miembros.html', miembros=miembros, membresias=membresias)
    except Exception as e:
        print(f"Error al obtener membresías: {e}")
        return "Ocurrió un error al cargar las membresías."
    
@app.route('/editar_miembro/<int:miembro_id>', methods=['GET', 'POST'])
def editar_miembro(miembro_id):
    conn = crear_conexion()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Obtener datos del formulario
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        email = request.form.get('email', None)
        telefono = request.form.get('telefono', None)

        try:
            # Actualizar datos del miembro
            query = """
                UPDATE Miembro
                SET nombre = ?, apellido = ?, email = ?, telefono = ?
                WHERE id_miembro = ?
            """
            cursor.execute(query, (nombre, apellido, email, telefono, miembro_id))
            conn.commit()
            conn.close()
            return redirect(url_for('administrar_miembros'))
        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Error al actualizar miembro: {e}"

    # Cargar datos del miembro
    query = "SELECT nombre, apellido, email, telefono, fecha_registro FROM Miembro WHERE id_miembro = ?"
    cursor.execute(query, (miembro_id,))
    miembro = cursor.fetchone()
    conn.close()

    if not miembro:
        return "Miembro no encontrado", 404

    return render_template('editar_miembro.html', miembro=miembro, miembro_id=miembro_id)


@app.route('/eliminar_miembro/<int:miembro_id>', methods=['POST'])
def eliminar_miembro(miembro_id):
    conn = crear_conexion()
    cursor = conn.cursor()
    try:
        query = "DELETE FROM Miembro WHERE id_miembro = ?"
        cursor.execute(query, (miembro_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('administrar_miembros'))
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Error al eliminar miembro: {e}"


@app.route('/actualizar_miembro_membresia/<int:miembro_id>', methods=['GET', 'POST'])
def actualizar_miembro_membresia(miembro_id):
    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        if request.method == 'POST':
            cursor.execute("EXEC actualizar_membresia")
            conn.commit()

            membresia = request.form["membresia"]
            cursor.execute("EXEC nuevo_miembro_membresia ?, ?", (miembro_id, membresia))
            conn.commit()
            conn.close()
            return redirect(url_for('administrar_miembros'))

        # Cargar datos del miembro
        query = "SELECT nombre, apellido, email, telefono, fecha_registro FROM Miembro WHERE id_miembro = ?"
        cursor.execute(query, (miembro_id,))
        miembro = cursor.fetchone()
        cursor.execute("SELECT id_membresia, nombre_membresia FROM Membresia")
        membresias = [{"id": row[0], "nombre": row[1]} for row in cursor.fetchall()]
        conn.close()

        if not miembro:
            return "Miembro no encontrado", 404

        return render_template('actualizar_miembro_membresia.html', miembro=miembro, membresias=membresias, miembro_id=miembro_id)
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Error al agregar miembro_membresías: {e}")
        return "Ocurrió un error"


@app.route('/administrar_membresias', methods=['GET', 'POST'])
def administrar_membresias():
    conn = crear_conexion()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # Datos para agregar una nueva membresía
            nombre = request.form.get('nombre')
            descripcion = request.form.get('descripcion')
            vigencia = request.form.get('vigencia')
            costo = request.form.get('costo')

            if nombre and descripcion and vigencia and costo:
                query_insert = """
                    INSERT INTO Membresia (nombre_membresia, descripcion, vigencia, costo)
                    VALUES (?, ?, ?, ?)
                """
                cursor.execute(query_insert, (nombre, descripcion, vigencia, costo))
                conn.commit()

        except Exception as e:
            print(f"Error al agregar membresía: {e}")
            conn.rollback()

    # Obtener todas las membresías
    try:
        query_select = "SELECT id_membresia, nombre_membresia, descripcion, vigencia, costo FROM Membresia"
        cursor.execute(query_select)
        membresias = cursor.fetchall()
    except Exception as e:
        print(f"Error al cargar membresías: {e}")
        membresias = []

    conn.close()
    return render_template('administrar_membresias.html', membresias=membresias)


@app.route('/editar_membresia/<int:membresia_id>', methods=['GET', 'POST'])
def editar_membresia(membresia_id):
    conn = crear_conexion()
    cursor = conn.cursor()

    if request.method == 'POST':
        # Obtener datos del formulario
        nombre_membresia = request.form['nombre_membresia']
        descripcion = request.form['descripcion']
        vigencia = request.form['vigencia']
        costo = request.form['costo']

        try:
            # Actualizar datos de la membresía
            query = """
                UPDATE Membresia
                SET nombre_membresia = ?, descripcion = ?, vigencia = ?, costo = ?
                WHERE id_membresia = ?
            """
            cursor.execute(query, (nombre_membresia, descripcion, vigencia, costo, membresia_id))
            conn.commit()
            conn.close()
            return redirect(url_for('administrar_membresias'))
        except Exception as e:
            conn.rollback()
            conn.close()
            return f"Error al actualizar membresía: {e}"

    # Cargar datos de la membresía
    query = "SELECT nombre_membresia, descripcion, vigencia, costo FROM Membresia WHERE id_membresia = ?"
    cursor.execute(query, (membresia_id,))
    membresia = cursor.fetchone()
    conn.close()

    if not membresia:
        return "Membresía no encontrada", 404

    return render_template('editar_membresia.html', membresia=membresia, membresia_id=membresia_id)

@app.route('/eliminar_membresia/<int:id>', methods=['POST'])
def eliminar_membresia(id):
    try:
        conn = crear_conexion()
        cursor = conn.cursor()

        query_delete = "DELETE FROM Membresia WHERE id_membresia = ?"
        cursor.execute(query_delete, (id,))
        conn.commit()
        conn.close()
        return redirect('/administrar_membresias')
    except Exception as e:
        print(f"Error al eliminar membresía: {e}")
        return "Error al eliminar membresía."

@app.route('/administrar_productos', methods=['GET', 'POST'])
def administrar_productos():
    conn = crear_conexion()
    cursor = conn.cursor()

    if request.method == 'POST':
        nombre_producto = request.form['nombre_producto']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        precio = float(request.form['precio'])
        existencia = int(request.form['existencia'])

        try:
            # Insertar nuevo producto
            query = """
                INSERT INTO Producto (nombre_producto, descripcion, categoria, precio, existencia, fecha_registro)
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """
            cursor.execute(query, (nombre_producto, descripcion, categoria, precio, existencia))
            conn.commit()
            return redirect(url_for('administrar_productos'))
        except Exception as e:
            conn.rollback()
            return f"Error al agregar producto: {e}", 500

    # Cargar productos existentes
    query = "SELECT id_producto, nombre_producto, descripcion, categoria, precio, existencia, fecha_registro FROM Producto"
    cursor.execute(query)
    productos = cursor.fetchall()
    conn.close()

    return render_template('administrar_productos.html', productos=productos)

@app.route('/editar_producto/<int:producto_id>', methods=['GET', 'POST'])
def editar_producto(producto_id):
    conn = crear_conexion()
    cursor = conn.cursor()

    if request.method == 'POST':
        nombre_producto = request.form['nombre_producto']
        descripcion = request.form['descripcion']
        categoria = request.form['categoria']
        precio = float(request.form['precio'])
        existencia = int(request.form['existencia'])

        try:
            # Actualizar producto
            query = """
                UPDATE Producto
                SET nombre_producto = ?, descripcion = ?, categoria = ?, precio = ?, existencia = ?
                WHERE id_producto = ?
            """
            cursor.execute(query, (nombre_producto, descripcion, categoria, precio, existencia, producto_id))
            conn.commit()
            return redirect(url_for('administrar_productos'))
        except Exception as e:
            conn.rollback()
            return f"Error al actualizar producto: {e}", 500

    # Cargar producto específico para editar
    query = "SELECT nombre_producto, descripcion, categoria, precio, existencia FROM Producto WHERE id_producto = ?"
    cursor.execute(query, (producto_id,))
    producto = cursor.fetchone()
    conn.close()

    if not producto:
        return "Producto no encontrado", 404

    return render_template('editar_producto.html', producto=producto, producto_id=producto_id)

@app.route('/eliminar_producto/<int:producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    conn = crear_conexion()
    cursor = conn.cursor()

    try:
        # Eliminar producto
        query = "DELETE FROM Producto WHERE id_producto = ?"
        cursor.execute(query, (producto_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Error al eliminar producto: {e}", 500

    conn.close()
    return redirect(url_for('administrar_productos'))

    
@app.route('/cerrar_sesion')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
