import os
from app import app
from flask import render_template
from flask import Flask, request, jsonify,Response
import base64
from io import BytesIO
from PIL import Image
import cv2
from matplotlib import pyplot
import matplotlib
matplotlib.use('Agg')
from mtcnn.mtcnn import MTCNN
import numpy as np
import mediapipe as mp
import math
from app import db
from app.models.usuario import Usuario
from math import acos, degrees

# Inicializar la captura de video y MediaPipe
cap = None
mpDibujo = mp.solutions.drawing_utils
ConfDibu = mpDibujo.DrawingSpec(thickness=1, circle_radius=1)
mpMallaFacial = mp.solutions.face_mesh
MallaFacial = mpMallaFacial.FaceMesh(max_num_faces=1)
video_active = False

#conteo de dedos
# Pulgar
thumb_points = [1, 2, 4]
# Índice, medio, anular y meñique
palm_points = [0, 1, 2, 5, 9, 13, 17]
fingertips_points = [8, 12, 16, 20]
finger_base_points =[6, 10, 14, 18]
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/verifica_usuario',methods=['POST'])
def verifica_usuario():
    data = request.get_json()
    usuario_nombre = data.get('usuario')
    if not usuario_nombre:
        return jsonify({"error": "No se proporcionó el nombre de usuario"}), 400

    # Verificar si el usuario existe en la base de datos
    usuario = Usuario.query.filter_by(usuario=usuario_nombre).first()
    if usuario:
        usuario_data = {
            "id": usuario.id,
            "usuario": usuario.usuario,
            "foto": usuario.foto
        }
        return jsonify({"existe": True, "mensaje": "El usuario existe en la base de datos.","usuario":usuario_data}), 200
    else:
        return jsonify({"existe": False, "mensaje": "El usuario no existe en la base de datos."}), 404

@app.route('/login_facial', methods=['GET'])
def login_facial():
    usuario_nombre = request.args.get("usuario")
    global cap
    try:
        if cap is not None:
            ret, frame = cap.read()
            if not ret:
                return jsonify({"error": "No se pudo capturar el frame"}), 500

            # Crear la carpeta si no existe
            image_dir = 'app/static/images/logs'
            if not os.path.exists(image_dir):
                os.makedirs(image_dir)

            image_dir_login = 'app/static/images/logs/login'
            if not os.path.exists(image_dir_login):
                os.makedirs(image_dir_login)

            # Guardar la foto
            image_path_log = os.path.join(image_dir, f'{usuario_nombre}LOG.jpg')
            image_path_login = os.path.join(image_dir_login, f'{usuario_nombre}LOG.jpg')

            # Eliminar la imagen anterior si existe
            if os.path.exists(image_path_log):
                os.remove(image_path_log)

            # Guardar la nueva imagen
            cv2.imwrite(image_path_log, frame)

            # Procesar la imagen para detectar caras
            pixeles = cv2.imread(image_path_log)
            detector = MTCNN()
            caras = detector.detect_faces(pixeles)

            # Registrar rostro y guardarlo en el path de login
            reg_rostro(image_path_log, caras, image_path_login)

            # Comparar las imágenes
            ruta_registro = f"app/static/images/registros/{usuario_nombre}.jpg"
            ruta_login = f"app/static/images/logs/login/{usuario_nombre}LOG.jpg"

            if os.path.exists(ruta_registro) and os.path.exists(ruta_login):
                rostro_reg = cv2.imread(ruta_registro, 0)
                rostro_login = cv2.imread(ruta_login, 0)
                # Comparar las imágenes
                similitud = comparar_imgs(rostro_reg, rostro_login)
                print(similitud)

                if similitud >= 0.90:
                    return jsonify({"existe": True})
                else:
                    return jsonify({"existe": False})
            else:
                return jsonify({"error": "No se pudo verificar la sesión"})
        else:
            return jsonify({"error": "Captura no inicializada"})

    except Exception as e:
        # Capturar cualquier error inesperado y devolver un mensaje adecuado
        return jsonify({"error": f"Se produjo un error: {str(e)}"}), 500

    finally:
        pyplot.close()  # Cerrar cualquier gráfico de matplotlib que se esté utilizando

@app.route('/registrarse')
def about():
    return render_template('registro.html')

@app.route('/registrar', methods=['POST'])
def registrar():
    data = request.get_json()
    usuario = data.get('usuario')
    imagen = data.get('imagen')

    # Validar que se haya proporcionado un nombre de usuario
    if not usuario:
        return jsonify({'error': 'El nombre de usuario es obligatorio.'}), 400

    # Validar que el usuario no exista en la base de datos
    existing_user = Usuario.query.filter_by(usuario=usuario).first()
    if existing_user:
        return jsonify({'error': 'El usuario ya existe.'}), 400

    # Validar que se haya proporcionado una imagen
    if not imagen:
        return jsonify({'error': 'No se ha cargado ninguna imagen.'}), 400

    # Procesar la imagen
    try:
        # Eliminar el prefijo de la cadena de imagen
        header, encoded = imagen.split(',', 1)
        # Decodificar la imagen
        binary_data = base64.b64decode(encoded)
        image = Image.open(BytesIO(binary_data))
        
        # Crear la carpeta si no existe
        image_dir = 'app/static/images/'
        if not os.path.exists(image_dir):
            os.makedirs(image_dir)
            
        # Crear la carpeta si no existe
        image_dir_reg = 'app/static/images/registros'
        if not os.path.exists(image_dir_reg):
            os.makedirs(image_dir_reg)

        # Guardar la foto
        image_path = os.path.join(image_dir, f'{usuario}.jpg')
        image_path_reg = os.path.join(image_dir_reg, f'{usuario}.jpg')
        image.save(image_path)
        pixeles = cv2.imread(image_path)
        detector = MTCNN()
        caras = detector.detect_faces(pixeles)
        reg_rostro(image_path,caras,image_path_reg)
    except Exception as e:
        return jsonify({'error': 'Error al procesar la imagen: ' + str(e)}), 500

    new_user = Usuario(usuario=usuario, foto=f'app/static/images/{usuario}.jpg')
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Usuario registrado exitosamente'}), 201

@app.route('/emotion', methods=['GET'])
def emotion_detection():
    global cap
    if cap is not None:
        ret, frame = cap.read()
        if not ret:
            return jsonify({"error": "No se pudo capturar el frame"}), 500

        emotion = detect_emotion(frame)
        return jsonify({"emotion": emotion[0],"dedos":emotion[1]})
    else:
        return jsonify({"error": "Captura no inicializada"})

@app.route('/video_feed')
def video_feed():
    global cap
    if video_active:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return ('',204)

@app.route('/toggle_video', methods=['POST'])
def toggle_video():
    global video_active
    global cap
    video_active = request.json.get('active', True)
    if video_active == False:
        release_camera()
    else:
        cap = cv2.VideoCapture(0)
    return jsonify({"video_active": video_active})

#funciones
# Función para detectar emociones
def detect_emotion(frame):
    frameRGB = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    #conteo de dedos
    
    with mp_hands.Hands(model_complexity=1,max_num_hands=1,min_detection_confidence=0.5,min_tracking_confidence=0.5) as hands:
        height, width, _ = frame.shape
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)
        fingers_counter = "_"
        thickness = [2, 2, 2, 2, 2]
        if results.multi_hand_landmarks:
            coordinates_thumb = []
            coordinates_palm = []
            coordinates_ft = []
            coordinates_fb = []
            for hand_landmarks in results.multi_hand_landmarks:
                for index in thumb_points:
                        x = int(hand_landmarks.landmark[index].x * width)
                        y = int(hand_landmarks.landmark[index].y * height)
                        coordinates_thumb.append([x, y])
                
                for index in palm_points:
                        x = int(hand_landmarks.landmark[index].x * width)
                        y = int(hand_landmarks.landmark[index].y * height)
                        coordinates_palm.append([x, y])
                
                for index in fingertips_points:
                        x = int(hand_landmarks.landmark[index].x * width)
                        y = int(hand_landmarks.landmark[index].y * height)
                        coordinates_ft.append([x, y])
                
                for index in finger_base_points:
                        x = int(hand_landmarks.landmark[index].x * width)
                        y = int(hand_landmarks.landmark[index].y * height)
                        coordinates_fb.append([x, y])
                ##########################
                # Pulgar
                p1 = np.array(coordinates_thumb[0])
                p2 = np.array(coordinates_thumb[1])
                p3 = np.array(coordinates_thumb[2])
                l1 = np.linalg.norm(p2 - p3)
                l2 = np.linalg.norm(p1 - p3)
                l3 = np.linalg.norm(p1 - p2)
                # Calcular el ángulo
                angle = degrees(acos((l1**2 + l3**2 - l2**2) / (2 * l1 * l3)))
                thumb_finger = np.array(False)
                if angle > 150:
                        thumb_finger = np.array(True)
                
                ################################
                # Índice, medio, anular y meñique
                nx, ny = palm_centroid(coordinates_palm)
                cv2.circle(frame, (nx, ny), 3, (0, 255, 0), 2)
                coordinates_centroid = np.array([nx, ny])
                coordinates_ft = np.array(coordinates_ft)
                coordinates_fb = np.array(coordinates_fb)
                # Distancias
                d_centrid_ft = np.linalg.norm(coordinates_centroid - coordinates_ft, axis=1)
                d_centrid_fb = np.linalg.norm(coordinates_centroid - coordinates_fb, axis=1)
                dif = d_centrid_ft - d_centrid_fb
                fingers = dif > 0
                fingers = np.append(thumb_finger, fingers)
                fingers_counter = str(np.count_nonzero(fingers==True))
    print("DEDOS CONTADOS: " + fingers_counter)    
    #reconocimiento de gestos
    resultados = MallaFacial.process(frameRGB)
    emotion = "Neutro"  # Valor por defecto
    if resultados.multi_face_landmarks:
        for rostros in resultados.multi_face_landmarks:
            mpDibujo.draw_landmarks(frame, rostros, mpMallaFacial.FACEMESH_TESSELATION, ConfDibu, ConfDibu)
            lista = []
            for id, puntos in enumerate(rostros.landmark):
                al, an, c = frame.shape
                x, y = int(puntos.x * an), int(puntos.y * al)
                lista.append([id, x, y])
                if len(lista) == 468:
                    #ceja derecha
                    x1, y1 = lista[65][1:]
                    x2,y2 =lista[158][1:]
                    cx,cy = (x1 + x2) // 2, (y1 + y2) // 2
                    #cv2.line(frame,(x1,y1),(x2,y2),(0,0,0),t)
                    #cv2.circle(frame,(x1,y1),r,(0,0,0), cv2.FILLED)
                    #cv2.circle(frame,(x2,y2),r,(0,0,0), cv2.FILLED)
                    #cv2.circle(frame,(cx,cy),r,(0,0,0), cv2.FILLED)
                    longitud1 = math.hypot(x2 - x1, y2 - y1)
                    print(longitud1)

                    #ceja izquierda
                    x3, y3 = lista[295][1:]
                    x4,y4 = lista[385][1:]
                    cx2, cy2 = (x3 + x4) // 2, (y3 + y4) // 2
                    longitud2 = math.hypot(x4-x3, y4-y3)
                    print(longitud2)

                    #boca extremos
                    x5, y5 = lista[78][1:]
                    x6, y6 = lista[308][1:]
                    cx3, cy3 = (x5 + x6) // 2, (y5 + y6) // 2
                    longitud3 = math.hypot(x6 - x5, y6 - y5)
                    print(longitud3)

                    #boca apertura
                    x7, y7 = lista[13][1:]
                    x8, y8 = lista[14][1:]
                    cx4, cy4 = (x7 + x8) // 2, (y7 + y8) // 2
                    longitud4 = math.hypot(x8-x7, y8-y7)
                    print(longitud4)

                    # Clasificación
                    if longitud1 < 22 and longitud2 < 22 and 60 < longitud3 < 80 and longitud4 < 5:
                        print("enojado")
                        emotion = "Enojado"
                    elif 20 < longitud1 < 30 and 20 < longitud2 < 30 and longitud3 > 77 and 10 < longitud4 < 20:
                        emotion = "Feliz"
                        print("feliz")
                    elif longitud1 > 23 and longitud2 > 22 and longitud3 < 90 and longitud4 > 30:
                        emotion = "Asombrado"
                        print("asombrado")
                    elif 25 < longitud1 < 35 and 25 < longitud2 < 35 and 60 < longitud3 < 70 and longitud4 < 4:
                        print("triste")
                        emotion = "Triste"
                    print("neutro")
                    

    return [emotion,fingers_counter]

# guardar imagen registro
def reg_rostro(img, lista_resultados,ruta_completa):
    data = cv2.imread(img)
    for i in range(len(lista_resultados)):
        x1,y1,ancho, alto = lista_resultados[i]['box']
        x2,y2 = x1 + ancho, y1 + alto
        pyplot.subplot(1, len(lista_resultados), i+1)
        pyplot.axis('off')
        cara_reg = data[y1:y2, x1:x2]
        cara_reg = cv2.resize(cara_reg,(150,200), interpolation = cv2.INTER_CUBIC) #Guardamos la imagen con un tamaño de 150x200
        if os.path.exists(ruta_completa):
            os.remove(ruta_completa)
        cv2.imwrite(ruta_completa,cara_reg)
        # pyplot.imshow(data[y1:y2, x1:x2])
    # pyplot.show()
    pyplot.close()

#-------------------------- Funcion para comparar los rostros --------------------------------------------
def comparar_imgs(img1,img2):
    orb = cv2.ORB_create()  #Creamos el objeto de comparacion
    kpa, descr_a = orb.detectAndCompute(img1, None)  #Creamos descriptor 1 y extraemos puntos claves
    kpb, descr_b = orb.detectAndCompute(img2, None)  #Creamos descriptor 2 y extraemos puntos claves
    comp = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck = True) #Creamos comparador de fuerza
    matches = comp.match(descr_a, descr_b)  #Aplicamos el comparador a los descriptores
    regiones_similares = [i for i in matches if i.distance < 70] #Extraemos las regiones similares en base a los puntos claves
    if len(matches) == 0:
        return 0
    return len(regiones_similares)/len(matches)  #Exportamos el porcentaje de similitud

# generar frames
def generate_frames():
    global cap
    while video_active and cap:
        ret, frame = cap.read()
        if not ret:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    release_camera()
    
def palm_centroid(coordinates_list):
    coordinates = np.array(coordinates_list)
    centroid = np.mean(coordinates, axis=0)
    centroid = int(centroid[0]), int(centroid[1])
    return centroid
#libera la camara        
def release_camera():
    global cap
    if cap is not None:
        cap.release()
        cap = None