import os
import sys
import math
import time 
import array
import random
import pickle
import pygame

HEX_FONT_DATA = [
    0XF0, 0X90, 0X90, 0X90, 0XF0,
    0X20, 0X60, 0X20, 0X20, 0X70,
    0XF0, 0X10, 0XF0, 0X80, 0XF0,
    0XF0, 0X10, 0XF0, 0X10, 0XF0,
    0x90, 0x90, 0xF0, 0x10, 0x10,
    0xF0, 0X80, 0XF0, 0X10, 0XF0,
    0XF0, 0X80, 0XF0, 0X90, 0XF0,
    0XF0, 0X10, 0X20, 0X40, 0X40,
    0xF0, 0X90, 0XF0, 0X90, 0XF0,
    0XF0, 0X90, 0XF0, 0X10, 0XF0,
    0XF0, 0X90, 0XF0, 0X90, 0X90,
    0XE0, 0X90, 0XE0, 0X90, 0XE0,
    0XF0, 0X80, 0X80, 0X80, 0XF0,
    0XE0, 0X90, 0X90, 0X90, 0XE0,
    0XF0, 0X80, 0XF0, 0X80, 0XF0,
    0XF0, 0X80, 0XF0, 0X80, 0X80,
]

CHIP8_KEYPAD_KEYMAPPING = {
    pygame.K_1: 0x1, pygame.K_2: 0X2,
    pygame.K_3: 0x3, pygame.K_4: 0xC,
    pygame.K_q: 0x4, pygame.K_w: 0X5,
    pygame.K_e: 0x6, pygame.K_r: 0XD,
    pygame.K_a: 0X7, pygame.K_s: 0X8,
    pygame.K_d: 0x9, pygame.K_f: 0xE,
    pygame.K_z: 0xA, pygame.K_x: 0x0,
    pygame.K_c: 0xB, pygame.K_v: 0xF,
}


class Chip8Config:
    def __init__(self):
        self.display_width = 64
        self.display_height = 32
        self.pixel_scale = 12
        self.window_width = self.display_width * self.pixel_scale
        self.window_height = self.display_height * self.pixel_scale
        self.background_color = (10, 10, 15)
        self.pixel_color = (200, 240, 200)
        self.overlay_text_colour = (255, 255, 100)
        self.cpu_hz = 700
        self.timer_hz = 60
        self.window_size = 4096
        self.rom_start_address = 0x200
        self.font_start_address = 0x50
        self.font_bytes_per_character = 5
        self.max_stack_depth = 16
        self.debug_mode = False
        self.show_debug_overlay = True
        self.show_fps_counter = True
        self.enable_sound = True
        self.sound_frequency = 440
        self.sound_volume = 0.15
        self.instruction_history_max = 32
        self.state_folder = "states"
        self.screenshot_folder = "screenshots"

class Chip8Font:
    def __init__ (self, start_address, bytes_per_character):
        self.start_address = start_address
        self.bytes_per_character = bytes_per_character
        self.fonts_bytes = HEX_FONT_DATA

    def get_character_address(self, character_index):
        safe_index = character_index & 0x0F 
        offset = safe_index * self.bytes_per_character
        return self.start_address + offset

    def get_character_bytes(self, character_index):
        safe_index = character_index & 0x0F
        byte_start = safe_index * self.bytes_per_character
        byte_end = byte_start + self.bytes_per_character
        return self.font_bytes[byte_start:byte_end] 

    def get_total_byte_count(self):
        return len(self.font_bytes)


class Chip8Memory:
    def __init__ (self, total_size):
        self.total_size = total_size
        self.bytes = bytearray(total_size)

    def read_byte(self, address):
        safe_address = address & 0xFFF
        return self.bytes[safe_address]

    def write_byte(self, address, value):
        safe_address = address & 0xFFF
        self.bytes[safe_address] = valur & 0xFF

    def read_word(self, address):
        high_byte = self.read_byte(address)
        low_byte = self.read_byte(address+1)
        return (high_byte << 8) | low_byte

    def write_word(self, address, value):
        self.write_byte(address, (value >> 8 ) & 0XFF)
        self.write_byte(address + 1 ,value & 0xFF)

    def load_bytes(self, start_address, byte_sequence):
        for offset in range(len(byte_sequence)):
            self.write_byte(start_address + offset, byte_sequence[offset])

    def load_rom_from_file(self, rom_path, start_address):
        if not os.path.exists(rom_path):
            raise FileNotFoundError(rom_path)
        rom_file = open