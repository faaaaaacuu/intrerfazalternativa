"""
Todos los efectos de voz, en un solo lugar.

Cada efecto tiene una "perilla" que va de 0 (apagado) a 1 (al máximo).
Los gestos de las manos solo mueven esas perillas; este archivo se encarga
de traducirlas a los parámetros técnicos de cada efecto.

Orden en que pasa la voz (como una cadena de pedales de guitarra):

  voz -> tono + armonía -> vocoder -> distorsión -> lo-fi -> filtro
      -> chorus -> phaser -> delay -> reverb -> limitador -> auriculares
"""

import numpy as np
from scipy.signal import butter, lfilter, sosfilt
from pedalboard import (Pedalboard, Bitcrush, Chorus, Compressor, Delay,
                        Distortion, LowpassFilter, Phaser, Reverb)

from cambia_tono import CambiaTono


# ------------------------------------------------------------------
# Vocoder robot
# ------------------------------------------------------------------
class VocoderRobot:
    """Tu voz "le da forma" a un sintetizador.

    Cómo funciona (vocoder de canales, como los de los 70):
      1. Partimos la voz en 16 bandas de frecuencia (de graves a agudos).
      2. En cada banda medimos cuánta energía hay en cada momento
         (la "envolvente"): eso es lo que hace que se entiendan las palabras.
      3. Generamos un acorde de sintetizador (ondas diente de sierra) y lo
         partimos en las mismas 16 bandas.
      4. A cada banda del sinte le ponemos el volumen de la banda de la voz.
    Resultado: el sinte "habla" con tus palabras, pero con sus notas.
    """

    BANDAS = 16

    def __init__(self, frecuencia):
        self.frecuencia = frecuencia
        # Notas del sintetizador (MIDI: 60 = Do central). Por defecto: Do mayor grave.
        self.notas_midi = [48, 52, 55]

        # Bordes de las bandas, repartidos "como oímos" (escala logarítmica)
        bordes = np.geomspace(100, 8000, self.BANDAS + 1)
        self.filtros = []
        for grave, agudo in zip(bordes[:-1], bordes[1:]):
            sos = butter(2, [grave, agudo], btype="band", fs=frecuencia, output="sos")
            self.filtros.append(sos)

        # Los filtros "recuerdan" el bloque anterior (estado), uno para la voz
        # y otro para el sinte en cada banda
        self.estado_voz = [np.zeros((len(s), 2)) for s in self.filtros]
        self.estado_sinte = [np.zeros((len(s), 2)) for s in self.filtros]
        self.envolventes = np.zeros(self.BANDAS)

        # Suavizado de la envolvente: ~10 ms (si es muy rápido, "raspa")
        self.suavizado = np.exp(-1 / (0.010 * frecuencia))
        self.fases = np.zeros(len(self.notas_midi))  # fase de cada oscilador

    def sintetizador(self, n):
        """Acorde de ondas diente de sierra + un poco de ruido (para las 's')."""
        frecuencias = 440 * 2 ** ((np.array(self.notas_midi) - 69) / 12)
        t = np.arange(1, n + 1)
        if len(self.fases) != len(frecuencias):  # si cambió la cantidad de notas
            self.fases = np.zeros(len(frecuencias))
        fases = (self.fases[:, None] + t * frecuencias[:, None] / self.frecuencia) % 1.0
        self.fases = fases[:, -1]
        sierra = (2 * fases - 1).sum(axis=0) / len(frecuencias)
        ruido = np.random.uniform(-1, 1, n) * 0.15
        return sierra + ruido

    def __call__(self, voz):
        n = len(voz)
        sinte = self.sintetizador(n)
        salida = np.zeros(n)

        for b, sos in enumerate(self.filtros):
            banda_voz, self.estado_voz[b] = sosfilt(sos, voz, zi=self.estado_voz[b])
            banda_sinte, self.estado_sinte[b] = sosfilt(sos, sinte, zi=self.estado_sinte[b])

            # Envolvente: valor absoluto de la banda, suavizado.
            # Es la fórmula env[i] = a * env[i-1] + (1 - a) * |voz[i]|
            # (lfilter la calcula para todo el bloque de una vez)
            a = self.suavizado
            env, _ = lfilter([1 - a], [1, -a], np.abs(banda_voz),
                                  zi=[a * self.envolventes[b]])
            self.envolventes[b] = env[-1]
            salida += banda_sinte * env

        return (salida * 18).astype(np.float32)  # 18 = ganancia para igualar volumen (medido)


# ------------------------------------------------------------------
# Todos los efectos juntos
# ------------------------------------------------------------------
class Efectos:
    def __init__(self, frecuencia):
        self.frecuencia = frecuencia

        # --- PERILLAS (las mueven los gestos) ---
        self.semitonos = 0.0   # tono de la voz principal, de -12 a +12
        self.armonia = 0.0     # volumen del coro de voces, 0 a 1
        self.vocoder = 0.0     # 0 = tu voz, 1 = solo el robot
        self.distorsion = 0.0  # 0 a 1
        self.lofi = 0.0        # 0 a 1 (voz "rota" digitalmente)
        self.filtro = 0.0      # 0 = voz normal, 1 = "bajo el agua" (sin agudos)
        self.chorus = 0.0      # 0 a 1
        self.phaser = 0.0      # 0 a 1
        self.delay = 0.0       # 0 a 1
        self.reverb = 0.0      # 0 a 1

        # Intervalos del coro, en semitonos sobre tu voz (4 = tercera mayor, 7 = quinta)
        self.intervalos = [4, 7]

        # --- Los efectos en sí ---
        self.tono = CambiaTono(frecuencia)
        self.voces_armonia = [CambiaTono(frecuencia) for _ in range(4)]  # hasta 4 voces
        self.robot = VocoderRobot(frecuencia)
        self.efecto_distorsion = Distortion(drive_db=0)
        self.efecto_lofi = Bitcrush(bit_depth=16)
        self.efecto_filtro = LowpassFilter(cutoff_frequency_hz=20000)
        self.efecto_chorus = Chorus(rate_hz=1.2, depth=0.5, centre_delay_ms=8, mix=0)
        self.efecto_phaser = Phaser(rate_hz=0.4, depth=0.8, feedback=0.6, mix=0)
        self.efecto_delay = Delay(delay_seconds=0.35, feedback=0.3, mix=0)
        self.efecto_reverb = Reverb(room_size=0.5, damping=0.3, width=1.0,
                                    wet_level=0, dry_level=1)
        # El limitador al final protege los oídos: si el sonido se pasa de
        # cierto volumen, lo aplasta (ratio 20 = casi no lo deja pasar).
        # Usamos Compressor y no Limiter porque el Limiter de pedalboard
        # sube el volumen por su cuenta (lo medimos: x1.5 a x3).
        self.limitador = Compressor(threshold_db=-6, ratio=20,
                                    attack_ms=1, release_ms=100)

        # Estos efectos tienen "memoria" (colas, ecos), así que van en cadena
        # y se procesan siempre, aunque la perilla esté en 0
        self.cadena = Pedalboard([self.efecto_filtro,
                                  self.efecto_chorus, self.efecto_phaser,
                                  self.efecto_delay, self.efecto_reverb,
                                  self.limitador])

    def actualizar_parametros(self):
        """Traduce las perillas (0 a 1) a los parámetros de cada efecto."""
        self.tono.semitonos = self.semitonos
        for voz, intervalo in zip(self.voces_armonia, self.intervalos):
            voz.semitonos = self.semitonos + intervalo  # la armonía sigue a tu tono

        self.efecto_distorsion.drive_db = self.distorsion * 30
        self.efecto_lofi.bit_depth = 16 - self.lofi * 12  # de 16 bits a 4 bits

        # Filtro: deja pasar solo lo que está por debajo de la frecuencia de
        # corte. Va de 20000 Hz (se oye todo) a 300 Hz (bajo el agua).
        # Usamos una escala "exponencial" porque así oímos las frecuencias.
        self.efecto_filtro.cutoff_frequency_hz = 20000 * (300 / 20000) ** self.filtro

        self.efecto_chorus.mix = self.chorus * 0.6
        self.efecto_chorus.depth = 0.2 + self.chorus * 0.6
        self.efecto_phaser.mix = self.phaser * 0.8
        self.efecto_delay.mix = self.delay * 0.6
        self.efecto_delay.feedback = 0.2 + self.delay * 0.5  # más perilla = más ecos

        # Reverb al máximo: sala enorme, casi sin voz directa (catedral)
        self.efecto_reverb.room_size = 0.5 + self.reverb * 0.48
        # Ojo: esta reverb multiplica por dentro la parte con efecto por 3 y
        # la voz directa por 2; por eso usamos 0.45 y 0.5 (ajustado midiendo)
        self.efecto_reverb.wet_level = self.reverb * 0.45
        self.efecto_reverb.dry_level = 0.5 * (1 - self.reverb * 0.8)

    def procesar(self, voz):
        """Recibe un bloque de voz limpia y devuelve la voz procesada."""
        self.actualizar_parametros()
        f = self.frecuencia

        # 1) Tono + coro de armonías (cada voz del coro sale de la voz original).
        #    El coro y el robot se calculan siempre, aunque la perilla esté en 0,
        #    para que al subirla no arranquen "en frío" con un click.
        sonido = self.tono(voz)
        voces = self.voces_armonia[: len(self.intervalos)]
        coro = sum(v(voz) for v in voces) / max(len(voces), 1)
        sonido = sonido + coro * self.armonia

        # 2) Vocoder: mezclamos entre tu voz y el robot
        robot = self.robot(sonido)
        sonido = sonido * (1 - self.vocoder) + robot * self.vocoder

        # 3) Distorsión y lo-fi: se mezclan con la voz limpia según la perilla
        if self.distorsion > 0:
            sucia = self.efecto_distorsion(sonido, f, reset=False)
            # La distorsión sube mucho el volumen; la compensamos bajándolo
            # a medida que sube el "drive" (fórmula ajustada midiendo)
            sucia = sucia * 10 ** (-self.efecto_distorsion.drive_db / 30)
            sonido = sonido * (1 - self.distorsion) + sucia * self.distorsion
        if self.lofi > 0:
            rota = self.efecto_lofi(sonido, f, reset=False)
            sonido = sonido * (1 - self.lofi) + rota * self.lofi

        # 4) Chorus, phaser, delay, reverb y limitador
        salida = self.cadena(sonido.astype(np.float32), f, reset=False)

        # 5) Red de seguridad final: nada pasa de +-1 (el máximo digital)
        return np.clip(salida, -1, 1)
