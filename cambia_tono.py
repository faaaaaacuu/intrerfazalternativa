"""
Pitch shifter propio, de "línea de retardo" (el método de los harmonizers
de los años 70-80).

¿Por qué uno propio? El PitchShift de pedalboard, cuando se usa bloque a
bloque desde Python, devuelve silencio (y adentro de AudioStream tiene
~1 segundo de retraso). Este tiene ~20 ms de retraso: se siente en vivo.

Idea:
  Guardamos los últimos 40 ms de voz y los volvemos a leer a otra velocidad.
  Leer más rápido = tono más agudo; más lento = más grave.
  Como la lectura se "adelanta" o "atrasa" respecto de la grabación, cada
  tanto tiene que saltar. Para que el salto no haga click usamos DOS
  lectores desfasados medio ciclo: mientras uno salta (volumen 0), el otro
  está en su punto más fuerte (volumen 1), y se van fundiendo.
"""

import numpy as np


class CambiaTono:
    def __init__(self, frecuencia, ventana_seg=0.04):
        self.ventana = int(frecuencia * ventana_seg)  # 40 ms = 1920 muestras a 48 kHz
        self.historia = np.zeros(self.ventana + 2, dtype=np.float32)
        self.fase = 0.0       # en qué punto del ciclo de lectura estamos (0 a 1)
        self.semitonos = 0.0  # esto es lo que cambiamos con los gestos

    def __call__(self, bloque):
        n = len(bloque)
        audio = np.concatenate([self.historia, bloque])  # pasado + presente

        # Velocidad de lectura: +12 semitonos = el doble (2.0), -12 = la mitad (0.5)
        velocidad = 2 ** (self.semitonos / 12)

        # La fase avanza un poquito en cada muestra y da la vuelta entre 0 y 1
        pasos = np.arange(1, n + 1) * (1 - velocidad) / self.ventana
        fases = (self.fase + pasos) % 1.0
        self.fase = fases[-1]

        ahora = len(self.historia) + np.arange(n)  # posición de cada muestra nueva
        salida = np.zeros(n, dtype=np.float32)

        for desfase in (0.0, 0.5):  # los dos lectores
            f = (fases + desfase) % 1.0
            posicion = ahora - 1 - f * self.ventana  # cuánto hacia atrás leemos
            i = posicion.astype(int)
            fraccion = posicion - i
            # Interpolación lineal: si caemos entre dos muestras, mezclamos ambas
            muestra = audio[i] * (1 - fraccion) + audio[i + 1] * fraccion
            # Volumen en forma de campana: 0 en el salto, 1 en el medio del ciclo
            salida += muestra * np.sin(np.pi * f) ** 2

        self.historia = audio[-len(self.historia):]  # lo guardamos para el próximo bloque
        return salida
