"""
Interfaz alternativa inspirada en los MiMU gloves de Imogen Heap.

La cámara detecta las dos manos (mediapipe) y sus gestos controlan efectos
que se aplican en vivo a la voz que entra por el micrófono.

  MANO IZQUIERDA: con una postura elige qué efectos tocar.
  MANO DERECHA:   los dosifica -> altura de la mano = un efecto,
                                  pinza pulgar-índice = otro efecto.
  Si soltás la postura, todo vuelve a cero.

Cómo está organizado:
  1. El AUDIO corre en segundo plano: sounddevice llama a `procesar_audio`
     unas 94 veces por segundo con un bloque chiquito de voz (~10 ms).
     Ahí le aplicamos los efectos (efectos.py) y lo mandamos a los auriculares.
  2. El VIDEO corre en el bucle principal: leemos la cámara, buscamos las
     manos, leemos los gestos (gestos.py) y movemos las perillas de los efectos.

Salir: botón SALIR (arriba a la derecha), tecla q, o cerrar la ventana.
"""

import cv2
import mediapipe as mp
import numpy as np
import sounddevice as sd

import gestos
from efectos import Efectos


# ------------------------------------------------------------------
# Configuración del audio
# ------------------------------------------------------------------
FRECUENCIA = 48000  # muestras por segundo
BLOQUE = 512        # muestras por bloque (512 / 48000 = ~10 ms de audio)

efectos = Efectos(FRECUENCIA)


# ------------------------------------------------------------------
# Qué controla cada postura de la mano izquierda
#   postura: (lo que controla la ALTURA, lo que controla la PINZA)
# Los nombres son las perillas de efectos.py
# ------------------------------------------------------------------
REPARTO = {
    "índice":        ("semitonos", "armonia"),
    "V":             ("vocoder", "chorus"),
    "cuernos":       ("distorsion", "lofi"),
    "pulgar arriba": ("phaser", "delay"),
    "mano abierta":  ("reverb", "filtro"),
    # "puño" no está: con el puño no se toca nada (voz limpia)
}

# Todas las perillas que se pueden mover con gestos
PERILLAS = ["semitonos", "armonia", "vocoder", "chorus", "distorsion",
            "lofi", "phaser", "delay", "reverb", "filtro"]

# Qué tan rápido las perillas siguen a la mano (0 a 1).
# Más chico = más suave pero más lento. Evita saltos y clicks.
SUAVIZADO = 0.3


def valor_de_perilla(perilla, cantidad):
    """Pasa una cantidad de 0 a 1 (altura o pinza) al valor de la perilla.
    Casi todas van de 0 a 1, salvo el tono, que va de -12 a +12 semitonos
    (mano abajo = más grave, mano arriba = más agudo)."""
    if perilla == "semitonos":
        return -12 + 24 * cantidad
    return cantidad


# Copia del último bloque de voz ya procesada.
# Por ahora no se usa; es lo que después vamos a "mirar" para los visuales.
ultimo_bloque = np.zeros(BLOQUE, dtype=np.float32)


def procesar_audio(entrada, salida, frames, tiempo, estado):
    """La llama sounddevice cada vez que hay un bloque nuevo del micrófono.

    entrada: lo que grabó el micrófono  (forma: BLOQUE x 1 canal)
    salida:  lo que vamos a mandar a los auriculares (BLOQUE x 2 canales)
    """
    global ultimo_bloque

    voz = entrada[:, 0].copy()  # nos quedamos con el canal mono
    procesada = efectos.procesar(voz)
    ultimo_bloque = procesada

    # Misma señal en el oído izquierdo y en el derecho
    salida[:, 0] = procesada
    salida[:, 1] = procesada


# ------------------------------------------------------------------
# Chequeo de seguridad: sin auriculares, el micrófono escucha los
# parlantes y se genera un acople (el pitido agudo que crece).
# ------------------------------------------------------------------
nombre_salida = sd.query_devices(kind="output")["name"]
print("Salida de audio:", nombre_salida)
if "Speakers" in nombre_salida or "Parlantes" in nombre_salida:
    print("Parece que no hay auriculares conectados. Enchufalos y volvé a correr.")
    raise SystemExit


# ------------------------------------------------------------------
# Detección de manos y cámara
# ------------------------------------------------------------------
manos = mp.solutions.hands.Hands(max_num_hands=2)
camara = cv2.VideoCapture(0)


# ------------------------------------------------------------------
# Ventana y botón para salir
# ------------------------------------------------------------------
VENTANA = "camara"
cv2.namedWindow(VENTANA)

# El botón va arriba a la derecha: (x1, y1) esquina de arriba a la
# izquierda, (x2, y2) esquina de abajo a la derecha, en píxeles
ancho_imagen = int(camara.get(cv2.CAP_PROP_FRAME_WIDTH))
BOTON = (ancho_imagen - 250, 30, ancho_imagen - 30, 120)
quiere_salir = False


def al_hacer_clic(evento, x, y, flags, param):
    """OpenCV la llama cada vez que movés o hacés clic con el mouse."""
    global quiere_salir
    x1, y1, x2, y2 = BOTON
    if evento == cv2.EVENT_LBUTTONDOWN and x1 <= x <= x2 and y1 <= y <= y2:
        quiere_salir = True


cv2.setMouseCallback(VENTANA, al_hacer_clic)


def dibujar_boton(imagen):
    x1, y1, x2, y2 = BOTON
    cv2.rectangle(imagen, (x1, y1), (x2, y2), (40, 40, 200), -1)  # relleno rojo (en BGR)
    cv2.putText(imagen, "SALIR", (x1 + 35, y2 - 28),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3)


def dibujar_ayuda(imagen, postura):
    """Texto TEMPORAL para probar los gestos: qué postura se detectó y
    cuánto vale cada perilla que se está moviendo. (OpenCV no dibuja
    tildes ni eñes, por eso las reemplazamos.)"""
    nombre = postura if postura else "-"
    lineas = ["Izquierda: " + nombre.replace("í", "i").replace("ñ", "n")]
    for perilla in PERILLAS:
        valor = getattr(efectos, perilla)
        if abs(valor) > 0.01:
            lineas.append(f"{perilla}: {valor:+.2f}")
    for i, linea in enumerate(lineas):
        cv2.putText(imagen, linea, (30, 60 + i * 45),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)


def ventana_abierta():
    """True mientras la ventana siga abierta.
    (En Mac, si la cerraste con la cruz roja, OpenCV tira un error.)"""
    try:
        return cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


# ------------------------------------------------------------------
# Bucle principal
# ------------------------------------------------------------------
# Al abrir el Stream, el audio empieza a correr en segundo plano.
# channels=(1, 2): 1 canal de entrada (mic), 2 de salida (estéreo).
with sd.Stream(
    samplerate=FRECUENCIA,
    blocksize=BLOQUE,
    channels=(1, 2),
    dtype="float32",
    latency="low",
    callback=procesar_audio,
):
    while True:
        ok, imagen = camara.read()
        if not ok:
            break
        imagen = cv2.flip(imagen, 1)  # espejo, para que se sienta natural
        resultado = manos.process(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))

        # --- 1) ¿Dónde está cada mano? ---
        # mediapipe nos dice si cada mano es "Left" o "Right". Como espejamos
        # la imagen antes, coincide con tu mano izquierda y derecha de verdad.
        izquierda = derecha = None
        if resultado.multi_hand_landmarks:
            for puntos, lado in zip(resultado.multi_hand_landmarks,
                                    resultado.multi_handedness):
                if lado.classification[0].label == "Left":
                    izquierda = puntos.landmark
                else:
                    derecha = puntos.landmark

        # --- 2) ¿A dónde tiene que ir cada perilla? ---
        # Por defecto, todas a cero (= voz limpia, tono normal)
        objetivos = {perilla: 0.0 for perilla in PERILLAS}

        postura = gestos.postura(izquierda) if izquierda else None
        if postura in REPARTO and derecha:
            perilla_altura, perilla_pinza = REPARTO[postura]
            objetivos[perilla_altura] = valor_de_perilla(perilla_altura, gestos.altura(derecha))
            objetivos[perilla_pinza] = valor_de_perilla(perilla_pinza, gestos.pinza(derecha))

        # --- 3) Mover cada perilla un poco hacia su objetivo (suavizado) ---
        # getattr / setattr leen y escriben una perilla por su nombre,
        # por ejemplo getattr(efectos, "reverb") es lo mismo que efectos.reverb
        for perilla, objetivo in objetivos.items():
            actual = getattr(efectos, perilla)
            nuevo = actual + (objetivo - actual) * SUAVIZADO
            if abs(nuevo) < 0.001:
                nuevo = 0.0  # si ya está casi en cero, que sea cero
            setattr(efectos, perilla, nuevo)

        # --- 4) Dibujar y mostrar ---
        dibujar_ayuda(imagen, postura)
        dibujar_boton(imagen)
        cv2.imshow(VENTANA, imagen)

        tecla = cv2.waitKey(1) & 0xFF
        if quiere_salir or tecla == ord("q") or not ventana_abierta():
            break

camara.release()
cv2.destroyAllWindows()
