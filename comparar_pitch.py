"""
Prueba de oído del pitch shifter propio (cambia_tono.py).

Para comparar con el de pedalboard, corré después prueba.py.
  Enter      -> alternar entre voz con efecto y voz limpia
  un número  -> cambiar los semitonos (ej: 7, -5, 12)
  q          -> salir

¡Con auriculares puestos! (si no, el micrófono escucha los parlantes y acopla)
"""

import sounddevice as sd
from cambia_tono import CambiaTono

FRECUENCIA = 48000
BLOQUE = 512

tono = CambiaTono(FRECUENCIA)
tono.semitonos = 4
con_efecto = True


def procesar_audio(entrada, salida, frames, tiempo, estado):
    voz = entrada[:, 0].copy()
    procesada = tono(voz)  # se procesa siempre, así no hay saltos al alternar
    elegido = procesada if con_efecto else voz
    salida[:, 0] = elegido
    salida[:, 1] = elegido


# Chequeo de seguridad: no arrancar con los parlantes de la Mac
nombre_salida = sd.query_devices(kind="output")["name"]
print("Salida de audio:", nombre_salida)
if "Speakers" in nombre_salida or "Parlantes" in nombre_salida:
    print("Parece que no hay auriculares conectados. Enchufalos y volvé a correr.")
    raise SystemExit

with sd.Stream(samplerate=FRECUENCIA, blocksize=BLOQUE, channels=(1, 2),
               dtype="float32", latency="low", callback=procesar_audio):
    print(__doc__)
    while True:
        estado = f"con efecto ({tono.semitonos:+g} semitonos)" if con_efecto else "voz limpia"
        print("Escuchando:", estado)
        orden = input("> ").strip()
        if orden == "q":
            break
        elif orden == "":
            con_efecto = not con_efecto
        else:
            try:
                tono.semitonos = float(orden)
            except ValueError:
                print("No entendí. Enter, un número o q.")
