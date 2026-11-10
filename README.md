# Interfaz alternativa

Proyecto para TAD1: una interfaz para manipular la voz en vivo con gestos de las manos, inspirada en los MiMU gloves de Imogen Heap. Usa la cámara en lugar de guantes: mediapipe detecta las manos y los gestos controlan efectos sobre el micrófono.

## Qué necesitás

- Python 3.9 o más nuevo
- Cámara y micrófono
- **Auriculares con cable**. Sin ellos el micrófono capta los parlantes y se acopla. El programa no arranca si detecta que la salida son los parlantes.

Para instalar las librerías:

```
pip3 install -r requirements.txt
```

## Cómo se usa

```
python3 main.py
```

- La **mano izquierda** elige los efectos con una postura.
- La **mano derecha** los dosifica: la **altura** de la mano maneja un efecto y la **pinza** (separar pulgar e índice) maneja otro.
- Al soltar la postura, todo vuelve a cero.

| Mano izquierda | Altura (derecha) | Pinza (derecha) |
|---|---|---|
| puño | nada | nada |
| índice ☝ | tono (-12 a +12 semitonos) | armonía (coro de voces) |
| V ✌ | vocoder robot | chorus |
| cuernos 🤘 | distorsión | lo-fi |
| pulgar arriba 👍 | phaser | delay |
| mano abierta ✋ | reverb | filtro |

Para salir: botón **SALIR**, tecla `q` o cerrar la ventana.

## Archivos

- `prueba.py`: la primera versión (solo tono y reverb, con el `AudioStream` de pedalboard).
- `main.py`: el programa principal (cámara, gestos y audio).
- `efectos.py`: todos los efectos de voz, cada uno con una "perilla" de 0 a 1.
- `gestos.py`: cómo se leen las posturas, la altura y la pinza a partir de los 21 puntos de la mano.
- `cambia_tono.py`: un pitch shifter propio. El de pedalboard, usado en tiempo real desde Python, devuelve silencio.
- `comparar_pitch.py`: prueba de oído del pitch shifter.
