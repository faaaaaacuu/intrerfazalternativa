import cv2
import mediapipe as mp
from pedalboard import Pedalboard, PitchShift, Reverb
from pedalboard.io import AudioStream

pitch = PitchShift(semitones=0)
reverb = Reverb(room_size=0.8, wet_level=0)

hands = mp.solutions.hands.Hands(max_num_hands=1)
cam = cv2.VideoCapture(0)

with AudioStream(
    input_device_name=AudioStream.default_input_device_name,
    output_device_name=AudioStream.default_output_device_name,
    allow_feedback=True,
) as stream:
    stream.plugins = Pedalboard([pitch, reverb])

    while True:
        ok, frame = cam.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)
        res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

        if res.multi_hand_landmarks:
            k = res.multi_hand_landmarks[0].landmark
            # altura de la mano -> tono
            pitch.semitones = 12 - k[0].y * 24
            # distancia pulgar-índice -> reverb
            d = ((k[4].x - k[8].x)**2 + (k[4].y - k[8].y)**2) ** 0.5
            reverb.wet_level = min(d * 4, 1.0)

        cv2.imshow("camara", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

cam.release()
cv2.destroyAllWindows()