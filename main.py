import cv2
import datetime
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib.utils import ImageReader
from ultralytics import YOLO
from fastapi import FastAPI, Request, Form, Depends
from reportlab.pdfgen import canvas
from io import BytesIO
import mysql.connector
from PIL import Image

# Configuracion de la conexion a la base de datos MySQL
db = mysql.connector.connect(
    host="34.174.15.102",  # Direccion IP del servidor de base de datos
    user="root01",  # Nombre de usuario para acceder a la BD
    password="Carlos20045",  # Contraseña de acceso a la BD
    database="Deteccion_de_cancer",  # Nombre de la base de datos a utilizar
    port=3306  # Puerto de conexion a MySQL (puerto estandar)
)
cursor = db.cursor()  # Creacion del cursor para ejecutar consultas SQL

# Inicializacion de la aplicacion FastAPI
app = FastAPI()  # Crear instancia de la aplicacion FastAPI
app.mount("/static", StaticFiles(directory="static"), name="static")  # Montar archivos estaticos (CSS, JS, imagenes)
templates = Jinja2Templates(directory="templates")  # Configurar el motor de plantillas Jinja2

# Configuracion de la camara web
cap = cv2.VideoCapture(0)  # Inicializar la camara (0 = camara principal)
cap.set(3, 640)  # Establecer ancho de resolucion a 640px
cap.set(4, 640)  # Establecer alto de resolucion a 640px
cap.set(cv2.CAP_PROP_FPS, 30)  # Establecer tasa de cuadros por segundo a 30fps

# Cargar el modelo de deteccion YOLO entrenado
model = YOLO('models/best.pt')  # Carga el modelo entrenado desde la ruta especificada

# Variables globales para almacenar estados
detected_frame = None  # Almacena el frame cuando se detecta algo
last_detection_id = None  # Almacena el ID de la ultima deteccion guardada en BD


def generate_video_stream():
    """
    Funcion generadora que proporciona un flujo continuo de frames de video con deteccion.
    Captura frames de la camara, procesa cada frame con el modelo YOLO para detectar
    posibles tipos de cancer, y devuelve el frame procesado como parte de un stream.
    """
    global detected_frame
    while True:
        ret, frame = cap.read()  # Captura un frame de la camara
        if not ret:
            break  # Si no se puede leer el frame, salir del bucle

        # Ejecutar el modelo de deteccion en el frame actual
        results = model.predict(frame, imgsz=640, conf=0.6)  # conf=0.6 significa 60% de confianza minima
        detections = len(results) > 0 and len(results[0].boxes) > 0  # Comprobar si hay detecciones

        if detections:
            detected_frame = frame.copy()  # Guardar el frame con deteccion
            annotated_frame = results[0].plot()  # Dibujar las detecciones en el frame
        else:
            annotated_frame = frame  # Usar el frame original sin anotaciones
            detected_frame = None  # No hay deteccion, reiniciar variable

        # Convertir el frame a formato JPEG para transmitirlo
        _, jpeg = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = jpeg.tobytes()

        # Formato requerido por multipart/x-mixed-replace para streaming
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


# Diccionario para mantener datos de sesion
session = {}


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    """
    Ruta principal de la aplicacion. Muestra la pagina index.html.

    Args:
        request: Objeto Request de FastAPI

    Returns:
        Renderiza la plantilla index.html
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/video")
async def video_stream():
    """
    Ruta que proporciona el stream de video en tiempo real.

    Returns:
        Un objeto StreamingResponse con el flujo de video procesado
    """
    return StreamingResponse(generate_video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/detection-status")
async def detection_status():
    """
    Ruta API que informa si hay una deteccion activa en el frame actual.

    Returns:
        Un diccionario JSON indicando si hay deteccion activa
    """
    return {"detected": detected_frame is not None}


@app.get("/take-photo")
async def take_photo():
    """
    Ruta que guarda la deteccion actual como foto, genera un informe PDF,
    y almacena ambos en la base de datos.

    Returns:
        Mensaje de exito o error con el ID de la deteccion guardada
    """
    global detected_frame, last_detection_id
    if detected_frame is None:
        return {"error": "No hay deteccion en pantalla"}

    # Procesar deteccion y generar reporte
    results = model.predict(detected_frame, imgsz=640, conf=0.5)
    if not results or len(results[0].boxes) == 0:
        return {"error": "No se detecto ningun tipo de cancer"}

    # Obtener la clase detectada (tipo de cancer)
    detected_class = int(results[0].boxes.cls[0].item())
    # Diccionario para mapear el indice de clase al nombre del tipo de cancer
    cancer_types = {
        0: "Carcinoma Basocelular",
        1: "Carcinoma Espinocelular",
        2: "Melanoma",
        3: "Celulas de Merkel"
    }
    cancer_detected = cancer_types.get(detected_class, "Tipo desconocido")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Marca de tiempo actual

    # Guardar imagen como binario para la base de datos
    _, image_encoded = cv2.imencode('.jpg', detected_frame)
    image_binary = image_encoded.tobytes()

    # Convertir la imagen de OpenCV a formato PIL para incluirla en el PDF
    detected_frame_rgb = cv2.cvtColor(detected_frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(detected_frame_rgb)

    # Configurar dimensiones de la imagen para el PDF
    max_width = 300  # Ancho de la imagen en el PDF
    aspect_ratio = pil_image.width / pil_image.height
    new_height = int(max_width / aspect_ratio)
    pil_image = pil_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # Crear el PDF usando ReportLab
    buffer = BytesIO()  # Buffer en memoria para el PDF
    c = canvas.Canvas(buffer)  # Crear el lienzo PDF

    # Definir posiciones del contenido en el PDF
    margin_left = 50  # Margen izquierdo para todo el contenido
    current_y = 800  # Posicion inicial Y (desde arriba)
    line_height = 20  # Espacio entre lineas de texto

    # Dibujar encabezado del documento
    c.drawString(margin_left, current_y, "UNIVERSIDAD DE LAS FUERZAS ARMADAS ESPE")
    current_y -= line_height
    c.drawString(margin_left, current_y, "Grupo Nro. 5")
    current_y -= line_height
    c.drawString(margin_left, current_y, "Informe de Deteccion de Cancer de Piel")
    current_y -= line_height
    c.drawString(margin_left, current_y, f"Fecha: {timestamp}")
    current_y -= line_height
    c.drawString(margin_left, current_y, f"Tipo de cancer detectado: {cancer_detected}")

    # Preparar la imagen para incluirla en el PDF
    temp_image = BytesIO()
    pil_image.save(temp_image, format='JPEG')
    temp_image.seek(0)  # Volver al inicio del buffer

    # Posicionar la imagen en el PDF
    image_x = margin_left + 100  # Centrar la imagen horizontalmente
    image_y = current_y - new_height - 220  # Dejar espacio despues del texto
    c.drawImage(ImageReader(temp_image), image_x, image_y, width=max_width, height=new_height)

    # Actualizar posicion Y para el texto que sigue
    current_y = image_y - 40  # Espacio despues de la imagen

    # Añadir detalles especificos segun el tipo de cancer detectado
    if detected_class == 0:  # Carcinoma Basocelular
        c.drawString(margin_left, current_y, "Carcinoma Basocelular")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Descripcion: Tipo mas comun de cancer de piel, crece lentamente y raramente se disemina.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Caracteristicas: Protuberancia perlada, sangrado, formacion de costra que no cicatriza.")
        current_y -= line_height
        c.drawString(margin_left, current_y, "Causas: Daño acumulativo en el ADN por exposicion a rayos UV.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Factores de Riesgo: Piel clara, exposicion solar prolongada, edad avanzada.")
        current_y -= line_height
        c.drawString(margin_left, current_y, "Tratamiento: Cirugia, terapias topicas, terapia fotodinamica.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Recomendaciones: Usar protector solar, evitar exposicion solar prolongada.")
    # Los demas tipos de cancer
    elif detected_class == 1:  # Carcinoma Espinocelular
        c.drawString(100, 700, "Carcinoma Espinocelular")
        c.drawString(100, 680, "Descripcion: Segundo tipo mas comun de cancer de piel, puede diseminarse.")
        c.drawString(100, 660, "Caracteristicas: Lesion escamosa o costrosa, aumento rapido de tamaño.")
        c.drawString(100, 640, "Causas: Exposicion prolongada a rayos UV, daño por quemaduras o cicatrices.")
        c.drawString(100, 620, "Factores de Riesgo: Exposicion solar acumulativa, lesiones precancerosas.")
        c.drawString(100, 600, "Tratamiento: Escision quirurgica, crioterapia, radioterapia en casos avanzados.")
        c.drawString(100, 580, "Recomendaciones: Protegerse del sol, realizar autoexamenes frecuentes.")
    elif detected_class == 2:  # Melanoma
        c.drawString(100, 700, "Melanoma")
        c.drawString(100, 680, "Descripcion: Tipo mas peligroso de cancer de piel, puede diseminarse rapidamente.")
        c.drawString(100, 660, "Caracteristicas: Lunares asimetricos, bordes irregulares, cambios de color.")
        c.drawString(100, 640, "Causas: Daño en el ADN por rayos UV, factores geneticos.")
        c.drawString(100, 620, "Factores de Riesgo: Historia familiar, piel clara, alta cantidad de lunares.")
        c.drawString(100, 600, "Tratamiento: Extirpacion quirurgica, inmunoterapia, quimioterapia.")
        c.drawString(100, 580, "Recomendaciones: Usar protector solar, revisar lunares con la regla ABCDE.")
    elif detected_class == 3:  # Celulas de Merkel
        c.drawString(100, 700, "Celulas de Merkel")
        c.drawString(100, 680, "Descripcion: Tipo raro y agresivo de cancer de piel.")
        c.drawString(100, 660,
                     "Caracteristicas: Nodulo firme sin dolor, color rojizo o azul, aparece en areas expuestas al sol.")
        c.drawString(100, 640,
                     "Causas: Mutaciones geneticas inducidas por rayos UV, poliomavirus de celulas de Merkel.")
        c.drawString(100, 620, "Factores de Riesgo: Edad avanzada, sistema inmunologico comprometido.")
        c.drawString(100, 600, "Tratamiento: Cirugia, radioterapia, inmunoterapia con inhibidores de PD-1/PD-L1.")
        c.drawString(100, 580, "Recomendaciones: Proteccion solar estricta, monitoreo frecuente de la piel.")

    # Finalizar y guardar el PDF
    c.save()
    buffer.seek(0)  # Volver al inicio del buffer
    pdf_binary = buffer.getvalue()  # Obtener el contenido binario del PDF

    # Guardar deteccion en MySQL
    sql = "INSERT INTO detections (timestamp, cancer_type, image, pdf) VALUES (%s, %s, %s, %s)"
    cursor.execute(sql, (timestamp, cancer_detected, image_binary, pdf_binary))
    db.commit()  # Confirmar la transaccion en la base de datos

    last_detection_id = cursor.lastrowid  # Obtener el ID generado para la deteccion
    return {
        "message": "Datos guardados en la base de datos",
        "detection_id": last_detection_id
    }


@app.get("/download-pdf/{detection_id}")
async def download_pdf(detection_id: int):
    """
    Ruta para descargar el informe PDF de una deteccion especifica.

    Args:
        detection_id: ID de la deteccion cuyo PDF se quiere descargar

    Returns:
        El archivo PDF como respuesta descargable o un mensaje de error
    """
    # Obtener el PDF de la base de datos
    sql = "SELECT pdf FROM detections WHERE id = %s"
    cursor.execute(sql, (detection_id,))
    result = cursor.fetchone()

    if not result:
        return {"error": "PDF no encontrado"}

    pdf_binary = result[0]  # Obtener los datos binarios del PDF

    # Crear un archivo temporal para el PDF
    temp_pdf_path = f"temp_report_{detection_id}.pdf"
    with open(temp_pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_binary)

    # Devolver el archivo PDF como respuesta descargable
    return FileResponse(
        temp_pdf_path,
        media_type="application/pdf",
        filename=f"cancer_detection_report_{detection_id}.pdf",
        background=None  # Permite que FastAPI maneje la eliminacion del archivo temporal
    )


@app.get("/get-detection/{detection_id}")
async def get_detection(detection_id: int):
    """
    Ruta para obtener los detalles de una deteccion especifica.

    Args:
        detection_id: ID de la deteccion que se quiere recuperar

    Returns:
        Informacion sobre el tipo de cancer detectado y rutas a la imagen y PDF
    """
    # Consultar la base de datos para obtener la deteccion
    sql = "SELECT cancer_type, image, pdf FROM detections WHERE id = %s"
    cursor.execute(sql, (detection_id,))
    result = cursor.fetchone()
    if not result:
        return {"error": "Deteccion no encontrada"}

    cancer_type, image_binary, pdf_binary = result

    # Guardar temporalmente la imagen y el PDF en archivos locales
    image_path = f"temp_{detection_id}.jpg"
    pdf_path = f"temp_{detection_id}.pdf"

    with open(image_path, "wb") as img_file:
        img_file.write(image_binary)

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_binary)

    # Devolver las rutas a los archivos y el tipo de cancer
    return {
        "cancer_type": cancer_type,
        "image_path": image_path,
        "pdf_path": pdf_path
    }


@app.on_event("shutdown")
def shutdown_event():
    """
    Funcion que se ejecuta cuando se cierra la aplicacion.
    Libera los recursos de la camara y cierra las ventanas de OpenCV.
    """
    cap.release()  # Liberar la camara
    cv2.destroyAllWindows()  # Cerrar todas las ventanas de OpenCV


# Punto de entrada para ejecutar la aplicacion directamente
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)  # Iniciar servidor en todas las interfaces (0.0.0.0) en
