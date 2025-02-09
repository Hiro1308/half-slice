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
        self.mute = False

    def toggle_mute(self, value):
        self.mute = value

    def play_sound(self, sound):
        if self.mute:
            return

        sounds = {
            "button": "sounds\\button.wav",
            "slice": "sounds\\slice.wav",
            "slidebar": "sounds\\slidebar.wav",
            "denied": "sounds\\denied.wav",
            "info": "sounds\\info.wav",
            "success": "sounds\\success.wav",
        }

        if sound in sounds:
            pygame.mixer.Sound(sounds[sound]).play()

    def play_loop(self, sound):
        if self.mute:
            return
        sounds = {
            "slice": "sounds\\slice.wav",
            "info": "sounds\\info.wav",
        }
        if sound in sounds:
            pygame.mixer.music.load(sounds[sound])
            pygame.mixer.music.play(-1)

    def stop_sound(self):
        pygame.mixer.music.stop()

    def on_slide_start(self, event):
        self.play_sound("slidebar")