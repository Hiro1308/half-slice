import pygame

class SoundManager:
    def __init__(self):
        pygame.mixer.init()
        self.sounds = {
            "button": "sounds/button.wav",
            "slice": "sounds/slice.wav",
            "denied": "sounds/denied.wav",
            "info": "sounds/info.wav",
            "success": "sounds/success.wav",
        }
        self.muteado = False

    def play_sound(self, sound):
        """Reproduce un efecto de sonido."""
        if sound in self.sounds:
            pygame.mixer.Sound(self.sounds[sound]).play()

    def toggle_muteado(self, value):
        self.muteado = value

    def reproducir_sonido(self, sound):
        if self.muteado:
            return  # No reproducir si está muteado

        sonidos = {
            "button": "sounds\\button.wav",
            "slice": "sounds\\slice.wav",
            "slidebar": "sounds\\slidebar.wav",
            "denied": "sounds\\denied.wav",
            "info": "sounds\\info.wav",
            "success": "sounds\\success.wav",
        }

        if sound in sonidos:
            pygame.mixer.Sound(sonidos[sound]).play()

    def play_loop(self, sound):
        if self.muteado:
            return  # No reproducir si está muteado
        sonidos = {
            "slice": "sounds\\slice.wav",
            "info": "sounds\\info.wav",
        }
        if sound in sonidos:
            pygame.mixer.music.load(sonidos[sound])
            pygame.mixer.music.play(-1)

    def stop_sound(self):
        pygame.mixer.music.stop()

    def on_slide_start(self, event):
        self.reproducir_sonido("slidebar")