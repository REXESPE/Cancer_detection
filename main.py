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
# Configuración de la conexiónººº
db = mysql.connector.connect(
        host="34.174.15.102" ,  # Reemplaza con la IP de tu base de datos
        user="root01",
        password="Carlos20045",
        database="Deteccion_de_cancer",
        port=3306
    )
cursor = db.cursor()
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuración de la cámara
cap = cv2.VideoCapture(0)
cap.set(3, 640)
cap.set(4, 640)
cap.set(cv2.CAP_PROP_FPS, 30)

# Cargar el modelo YOLO
model = YOLO('models/best.pt')

# Variable global para almacenar el frame detectado
detected_frame = None
last_detection_id = None  # Nueva variable para almacenar el ID de la última detección


def generate_video_stream():
    global detected_frame
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model.predict(frame, imgsz=640, conf=0.6)
        detections = len(results) > 0 and len(results[0].boxes) > 0

        if detections:
            detected_frame = frame.copy()
            annotated_frame = results[0].plot()
        else:
            annotated_frame = frame
            detected_frame = None

        _, jpeg = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = jpeg.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


session = {}


@app.get("/", response_class=HTMLResponse)
async def main_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})



@app.get("/video")
async def video_stream():
    return StreamingResponse(generate_video_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/detection-status")
async def detection_status():
    return {"detected": detected_frame is not None}


@app.get("/take-photo")
async def take_photo():
    global detected_frame, last_detection_id
    if detected_frame is None:
        return {"error": "No hay detección en pantalla"}

    # Procesar detección y generar reporte
    results = model.predict(detected_frame, imgsz=640, conf=0.5)
    if not results or len(results[0].boxes) == 0:
        return {"error": "No se detectó ningún tipo de cáncer"}

    detected_class = int(results[0].boxes.cls[0].item())
    cancer_types = {
        0: "Carcinoma Basocelular",
        1: "Carcinoma Espinocelular",
        2: "Melanoma",
        3: "Celulas de Merkel"
    }
    cancer_detected = cancer_types.get(detected_class, "Tipo desconocido")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Guardar imagen como binario
    _, image_encoded = cv2.imencode('.jpg', detected_frame)
    image_binary = image_encoded.tobytes()

    # Convertir la imagen de OpenCV a formato PIL
    detected_frame_rgb = cv2.cvtColor(detected_frame, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(detected_frame_rgb)

    # Configurar dimensiones de la imagen
    max_width = 300  # Ancho de la imagen en el PDF
    aspect_ratio = pil_image.width / pil_image.height
    new_height = int(max_width / aspect_ratio)
    pil_image = pil_image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    # Crear el PDF
    buffer = BytesIO()
    c = canvas.Canvas(buffer)

    # Definir posiciones del contenido
    margin_left = 50  # Margen izquierdo para todo el contenido
    current_y = 800  # Posición inicial Y
    line_height = 20  # Espacio entre líneas de texto

    # Dibujar encabezado
    c.drawString(margin_left, current_y, "UNIVERSIDAD DE LAS FUERZAS ARMADAS ESPE")
    current_y -= line_height
    c.drawString(margin_left, current_y, "Grupo Nro. 5")
    current_y -= line_height
    c.drawString(margin_left, current_y, "Informe de Detección de Cáncer de Piel")
    current_y -= line_height
    c.drawString(margin_left, current_y, f"Fecha: {timestamp}")
    current_y -= line_height
    c.drawString(margin_left, current_y, f"Tipo de cáncer detectado: {cancer_detected}")

    # Preparar la imagen
    temp_image = BytesIO()
    pil_image.save(temp_image, format='JPEG')
    temp_image.seek(0)

    # Posicionar la imagen
    image_x = margin_left + 100  # Centrar la imagen horizontalmente
    image_y = current_y - new_height - 100  # Dejar espacio después del texto
    c.drawImage(ImageReader(temp_image), image_x, image_y, width=max_width, height=new_height)

    # Actualizar posición Y para el texto que sigue
    current_y = image_y - 40  # Espacio después de la imagen

    # Añadir detalles específicos según el tipo de cáncer
    if detected_class == 0:  # Carcinoma Basocelular
        c.drawString(margin_left, current_y, "Carcinoma Basocelular")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Descripción: Tipo más común de cáncer de piel, crece lentamente y raramente se disemina.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Características: Protuberancia perlada, sangrado, formación de costra que no cicatriza.")
        current_y -= line_height
        c.drawString(margin_left, current_y, "Causas: Daño acumulativo en el ADN por exposición a rayos UV.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Factores de Riesgo: Piel clara, exposición solar prolongada, edad avanzada.")
        current_y -= line_height
        c.drawString(margin_left, current_y, "Tratamiento: Cirugía, terapias tópicas, terapia fotodinámica.")
        current_y -= line_height
        c.drawString(margin_left, current_y,
                     "Recomendaciones: Usar protector solar, evitar exposición solar prolongada.")
    # ... (resto de los tipos de cáncer)
    elif detected_class == 1:  # Carcinoma Espinocelular
        c.drawString(100, 700, "Carcinoma Espinocelular")
        c.drawString(100, 680, "Descripción: Segundo tipo más común de cáncer de piel, puede diseminarse.")
        c.drawString(100, 660, "Características: Lesión escamosa o costrosa, aumento rápido de tamaño.")
        c.drawString(100, 640, "Causas: Exposición prolongada a rayos UV, daño por quemaduras o cicatrices.")
        c.drawString(100, 620, "Factores de Riesgo: Exposición solar acumulativa, lesiones precancerosas.")
        c.drawString(100, 600, "Tratamiento: Escisión quirúrgica, crioterapia, radioterapia en casos avanzados.")
        c.drawString(100, 580, "Recomendaciones: Protegerse del sol, realizar autoexámenes frecuentes.")
    elif detected_class == 2:  # Melanoma
        c.drawString(100, 700, "Melanoma")
        c.drawString(100, 680, "Descripción: Tipo más peligroso de cáncer de piel, puede diseminarse rápidamente.")
        c.drawString(100, 660, "Características: Lunares asimétricos, bordes irregulares, cambios de color.")
        c.drawString(100, 640, "Causas: Daño en el ADN por rayos UV, factores genéticos.")
        c.drawString(100, 620, "Factores de Riesgo: Historia familiar, piel clara, alta cantidad de lunares.")
        c.drawString(100, 600, "Tratamiento: Extirpación quirúrgica, inmunoterapia, quimioterapia.")
        c.drawString(100, 580, "Recomendaciones: Usar protector solar, revisar lunares con la regla ABCDE.")
    elif detected_class == 3:  # Células de Merkel
        c.drawString(100, 700, "Células de Merkel")
        c.drawString(100, 680, "Descripción: Tipo raro y agresivo de cáncer de piel.")
        c.drawString(100, 660,
                     "Características: Nódulo firme sin dolor, color rojizo o azul, aparece en áreas expuestas al sol.")
        c.drawString(100, 640,
                     "Causas: Mutaciones genéticas inducidas por rayos UV, poliomavirus de células de Merkel.")
        c.drawString(100, 620, "Factores de Riesgo: Edad avanzada, sistema inmunológico comprometido.")
        c.drawString(100, 600, "Tratamiento: Cirugía, radioterapia, inmunoterapia con inhibidores de PD-1/PD-L1.")
        c.drawString(100, 580, "Recomendaciones: Protección solar estricta, monitoreo frecuente de la piel.")
    c.save()
    buffer.seek(0)
    pdf_binary = buffer.getvalue()

    # Guardar en MySQL
    sql = "INSERT INTO detections (timestamp, cancer_type, image, pdf) VALUES (%s, %s, %s, %s)"
    cursor.execute(sql, (timestamp, cancer_detected, image_binary, pdf_binary))
    db.commit()

    last_detection_id = cursor.lastrowid
    return {
        "message": "Datos guardados en la base de datos",
        "detection_id": last_detection_id
    }
@app.get("/download-pdf/{detection_id}")
async def download_pdf(detection_id: int):
    # Obtener el PDF de la base de datos
    sql = "SELECT pdf FROM detections WHERE id = %s"
    cursor.execute(sql, (detection_id,))
    result = cursor.fetchone()

    if not result:
        return {"error": "PDF no encontrado"}

    pdf_binary = result[0]

    # Crear un archivo temporal
    temp_pdf_path = f"temp_report_{detection_id}.pdf"
    with open(temp_pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_binary)

    # Devolver el archivo PDF
    return FileResponse(
        temp_pdf_path,
        media_type="application/pdf",
        filename=f"cancer_detection_report_{detection_id}.pdf",
        background=None  # Esto permite que FastAPI maneje la eliminación del archivo temporal
    )
@app.get("/get-detection/{detection_id}")
async def get_detection(detection_id: int):
    sql = "SELECT cancer_type, image, pdf FROM detections WHERE id = %s"
    cursor.execute(sql, (detection_id,))
    result = cursor.fetchone()
    if not result:
        return {"error": "Detección no encontrada"}

    cancer_type, image_binary, pdf_binary = result
    image_path = f"temp_{detection_id}.jpg"
    pdf_path = f"temp_{detection_id}.pdf"

    with open(image_path, "wb") as img_file:
        img_file.write(image_binary)

    with open(pdf_path, "wb") as pdf_file:
        pdf_file.write(pdf_binary)

    return {
        "cancer_type": cancer_type,
        "image_path": image_path,
        "pdf_path": pdf_path
    }
@app.on_event("shutdown")
def shutdown_event():
    cap.release()
    cv2.destroyAllWindows()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
