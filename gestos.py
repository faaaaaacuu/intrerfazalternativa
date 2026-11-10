"""
Lectura de gestos a partir de los 21 puntos que mediapipe detecta en cada mano.

Números de los puntos (los que usamos):

        8   12  16  20      <- puntas de los dedos
        6   10  14  18      <- articulación del medio de cada dedo
    4   5   9   13  17      <- 4 = punta del pulgar; 5, 9, 13, 17 = nudillos
     3
      2
         0                  <- muñeca

Las coordenadas x e y van de 0 a 1 (0 = izquierda / arriba de la imagen).
"""


def distancia(a, b):
    """Distancia entre dos puntos de la mano (solo en x e y)."""
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def tamano_mano(p):
    """Distancia muñeca -> nudillo del dedo medio.
    Sirve de "regla": así los gestos funcionan igual con la mano cerca o
    lejos de la cámara."""
    return distancia(p[0], p[9])


def dedo_estirado(p, punta, medio):
    """Un dedo está estirado si su punta está bastante más lejos de la
    muñeca que su articulación del medio. (Doblado, la punta vuelve
    hacia la palma y queda más cerca de la muñeca.)"""
    return distancia(p[0], p[punta]) > distancia(p[0], p[medio]) * 1.2


def pulgar_para_arriba(p):
    """La punta del pulgar (4) es, por bastante, el punto más alto de la mano.
    (En la imagen y=0 es arriba, así que "más alto" = y más chica.)
    En un puño común lo más alto son los nudillos, no el pulgar."""
    lo_mas_alto_del_resto = min(p[i].y for i in range(5, 21))
    return p[4].y < lo_mas_alto_del_resto - tamano_mano(p) * 0.1


def postura(p):
    """Devuelve el nombre de la postura de la mano, o None si no es ninguna."""
    indice = dedo_estirado(p, 8, 6)
    medio = dedo_estirado(p, 12, 10)
    anular = dedo_estirado(p, 16, 14)
    menique = dedo_estirado(p, 20, 18)

    dedos = (indice, medio, anular, menique)

    if dedos == (False, False, False, False):
        # Los cuatro dedos cerrados: pulgar arriba o puño
        if pulgar_para_arriba(p):
            return "pulgar arriba"
        return "puño"
    if dedos == (True, False, False, False):
        return "índice"
    if dedos == (True, True, False, False):
        return "V"
    if dedos == (True, False, False, True):
        return "cuernos"
    if dedos == (True, True, True, True):
        return "mano abierta"
    return None  # otra combinación: no cuenta como postura


def limitar(valor):
    """Recorta un número para que quede entre 0 y 1."""
    return max(0.0, min(1.0, valor))


def altura(p):
    """Altura de la mano: 0 = abajo de todo, 1 = arriba de todo.
    Usamos el nudillo del medio (9), que es como el centro de la mano.
    Dejamos un margen de 10% arriba y abajo porque en los bordes la
    cámara pierde la mano."""
    return limitar((0.9 - p[9].y) / 0.8)


def pinza(p):
    """Apertura pulgar-índice: 0 = juntos, 1 = bien abiertos.
    Se mide en "tamaños de mano" para que no dependa de la distancia
    a la cámara."""
    apertura = distancia(p[4], p[8]) / tamano_mano(p)
    return limitar((apertura - 0.2) / 1.0)
