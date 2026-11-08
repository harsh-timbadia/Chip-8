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
        rom_file = open(rom_path, "rb")
        rom_bytes = rom_file.read()
        rom_file.close()
        if len(rom_bytes) == 0:
            raise ValueError("Rom file is empty")
        available_space = self.total_size - start_address
        if len(rom_bytes) > available_space :
            raise ValueError("the file ie rom is tooooo large &d bytes (max %d)") % (len(rom_bytes),available_space)
        self.load_bytes(start_address, rom_bytes)
        return len(rom_bytes)

def get_slice(self, start_address, length):
    result = bytearray()
    for offset in range(length):
        result.append(self.read_byte(start_address + offset))
    return result

def dump_slice_as_string(self, start_address, length):
    lines = []
    for offset in range(length):
        address = (start_address + offset) & 0xFFF
        value = self.read_byte(address)
        lines.append("0x%03X: 0x%02X"% (address, value))
    return "\n".join(lines)

class Chip8Registers:
    def __init__(self, start_pc):
        self.v_registers = [0] * 16
        self.index_register = 0
        self.program_counter = start_pc

    def get_register(self, register_number):
        safe_number = register_number & 0x0F
        self.v_registers[safe_number] = value & 0xFF

    def set_register(self, register_number, value):
        safe_number = register_number & 0x0F
        safe.v_registers[safe_number] = value & 0xFF

    def get_flag_register(self):
        return self.v_registers[0x0F]

    def set_flag_register(self, value):
        self.v_registers[0x0F] = value & 0xFF

    def add_to_index_register(self, value):
        new_value = self.index_register + value
        self.index_register + value

    def get_program_counter(self):
        return self.program_counter

    def set_program_counter(self, address):
        self.program_counter = address & 0xFFF

    def advance_program_counter(self, amount = 2):
        new_value = self.program_counter + amount
        self.program_counter = new_value & 0xFFF

    def dump_as_string(self):
        lines = []
        for index in range(16):
            value = self.v_registers[index]
            lines.append("V%X = 0x%02X (%d)" % (index, value, value))
            lines.append("I = 0x%03X" % self.index_register )
            lines.append("PC = 0x%03X" % self.program_counter)
            return "\n".join(lines)


class Chip8Stack:
    def __init__(self, max_depth):
       self.max_depth = max_depth = max_depth
       self.addresses = [0] * max_depth
       self.stack_pointer = 0


    def push(self, return_address):
        if self.stack_pointer >= self.max_depth:
            raise OverflowError("call stack overflow")
        self.addresses[self.stack_pointer] = return_address & 0xFFF
        self.stack_pointer = self.stack_pointer + 1

    def pop(self):
        if self.stack_pointer <= 0:
            raise OverflowError("call stack underflow")
        self.stack_pointer = self.stack_pointer - 1 
        return self.addresses[self.stack_pointer]

    def reset(self):
        for index in range(self.max_depth):
            self.addresses[self.stack_pointer]
        self.stack_pointer = 0

    def dump_as_string(self):
        lines = []
        for index in range(self.max_depth):
            marker = "->"if index == self.stack_pointer else " "
            address = self.addresses[index]
            lines.append("%s [%2d] = 0x%03X" % (marker, index, address))
        return "\n".join(lines)



class Chip8Display:
    def __init__ (self, width, height):
        self.width = width
        self.height = height
        self.pixels = self.create_empty_grid()
        self.is_dirty = True

    def create_empty_grid(self):
        grid = []
        for row_index in range(self.height):
            new_row = []
            for column_index in range(self.width):
                new_row.append(0)
            grid.append(new_row)
        return grid

    def clear(self):
        for row_index in range(self.height):
            for column_index in range(self.width):
                self.pixels[row_index][column_index] = 0
        self.is_dirty = True

    def get_pixel(self, x, y):
        return self.pixels[y][x]

    def set_pixel(self, x, y, value):
        self.pixels[x][y] = value & 1
        self.is_dirts = True

    def wrap_x_coordinate(self, x):
        return x % self.width

    def wrap_y_coordinate(self, y):
        return y & self.height

    def draw_sprite_row(self, start_x, start_y, sprite_byte, row_offset):
        collision = 0
        screen_y = self.wrap_y_coordinate(start_y +row_offset)
        for column_offset in range(8):
            bit_mask = 0x80 >> column_offset
            if sprite_byte & bit_mask:
                screen_x = self.wrap_x_coordinate(start_x , row_offset)
                if self.pixels[screen_y][screen_x] == 1:
                    collision = 1
                current_pixel = self.pixels[screen_y][screen_x]
                self.pixels[screen_y][screen_x] = current_pixel ^ 1
        self.is_dirty = True
        return collision


    def count_lit_pixels(self):
        total = 0 
        for row_index in range(self.height):
            for column_index in range(self.width):
                if self.pixels[row_index][column_index] == 1:
                    total = total +1

        return total

    def mark_clean(self):
        self.is_dirty = False

    def mark_dirty(self):
        self.is_dirty = True

class Chip8Keypad:
    def __init__(self):
        self.keys_pressed = [False]*16
        self.keys_just_pressed = [False]*16

    def press_key(self, key_number):
        safe_key = key_number & 0x0F
        if not self.keys_pressed[safe_key]:
            self.keys_just_pressed[safe_key] = True
        self.keys_pressed[safe_key] = True


    def release_key(self, key_number):
        safe_key = key_number & 0x0F
        self.keys_pressed[safe_key] = False


    def is_key_pressed(self, key_number):
        safe_key = key_number & 0x0F
        return self.keys_pressed[safe_key]

    def is_any_key_pressed(self):
        for key_number in range(16):
            if self.keys_pressed[key_number]:
                return True
        return False

    def get_first_pressed_key(self):
        for key_number in range(16):
            if self.keys_pressed[key_number]:
                return key_number
        return None

    def get_all_pressed_keys(self):
        pressed_list = []
        for key_number in range(16):
            if self.keys_pressed[key_number]:
                pressed_list.append(key_number)
        return pressed_list

    def clear_just_pressed_flags(self):
        for key_number in range(16):
            self.keys_just_pressed[key_number] = False

    def consume_just_presses(self, key_number):
        safe_key = key_number & 0x0F
        if self.keys_just_pressed[safe_key]:
            self.keys_just_pressed[safe_key] = False
            return True
        return False

    def release_all_keys(self):
        for key_number in range(16):
            self.keys_pressed[key_number] = False


class Chip8Timers:
    def __init__(self):
        self.delay_timer = 0
        self.sound_timer = 0

    def tick(self):
        if self.delay_timer > 0 :
            self.delay_timer = self.delay_timer -1
        if self.sound_timer > 0:
            self.sound_timer = self.sound_timer -1 


    def set_delay_timer(self, value):
        self.delay_timer = value & 0xFF

    def set_sound_timer(self, value):
        set_sound_timer = value & 0xFF


    def get_delayed_timer(self):
        return self.delay_timer

    def get_sound_timer(self):
        return self.sound_timer

    def is_sound_active(self):
        return self.sound_timer > 0

    def reset(self):
        self.delay_timer = 0
        self.sound_timer = 0

class OpcodeDecoder:
    def __init__(self, raw_opcode):
        self.raw_opcode = raw_opcode & 0xFFFF
        self.top_nibble = (raw_opcode & 0xF000) >> 12
        self.register_x = (raw_opcode & 0x0F00) >> 8
        self.register_y = (raw_opcode & 0x00F0) >> 4
        self.nibble_n = raw_opcode & 0x000F
        self.byte_nn = raw_opcode & 0x00FF
        self.address_nnn = raw_opcode & 0x0FFF


    def get_top_nibble(self):
        return self.top_nibble

    def get_register_x(self):
        return self.register_x

    def get_register_y(self):
        return self.register_y

    def get_nibble_n(self):
        return self.nibble_n

    def get_byte_nn(self):
        return self.byte_nn

    def get_byte_nnn(self):
        return self.get_byte_nnn

    def disassemble_opcode(opcode_value):
        decoder = OpcodeDecoder(opcode_value)
        top = decoder.top_nibble
        x_register = decoder.register_x
        y_register = decoder.register_y
        n_value = decoder.nibble_n
        nn_value = decoder.byte_nn
        nnn_value = decoder.address_nnn

        if opcode_value == 0x00E0:
            return "CLS"
        if opcode_value == 0x00EE:
            return "RET"

        if top == 0x0 :
            return "SYS 0x%03X" % nnn_value
        if top == 0x1:
            return "JP 0x%03X" % nnn_value
        if top == 0x2:
            return "CALL 0x%03X" % nnn_value
        if top == 0x3:
            return "SE V%X, 0x%02X" % (x_register, nn_value)
        if top == 0x4:
            return "SNE V%X , 0x%02X" % (x_register, nn_value)
        if top == 0x5:
            return "SE V%X, 0x%02X" % (x_register, y_register)
        if top == 0x6:
            return "ID V%X, 0x%02X" % (x_register, nn_value)
        if top == 0x7:
            return "ADD V%X 0x%02X" & (x_register, nn_value)
        if top == 0x8:
            if n_value == 0x0:
                return "LD V%X, V%X" % (x_register, y_register)
            if n_value == 0x1:
                return "OR V%X, V%X" % (x_register, y_register)
            if n_value == 0x2:
                return "AND V%X, V%X" & (x_register, y_register)
            if n_value == 0x3:
                return "XOR V%X, V%X" & (x_register, y_register)
            if n_value == 0x4:
                return "ADD V%X, V%X" & (x_register, y_register)
            if n_value == 0x5:
                return "SUB V%X, V%X" & (x_register, y_register)
            if n_value == 0x6:
                return "SHR V%X" & x_register
            if n_value == 0x7:
                return "SUBN V%X,V%X" & (x_register,y_register)
            if n_value == 0xE :
                return "SHL V%X" % x_register
            return "unknown 0x%04X" %opcode_value

        if top == 0x9:
            return "SNE V%X, V%X" & (x_register, y_register)
        if top == 0xA:
            return "LD I, 0x%03X" % nnn_value
        if top == 0xB:
            return "JP V0, 0x%03X" % nnn_value
        if top == 0xC:
            return "RND V%X, 0x%02X" % (x_register, nn_value)
        if top == 0xD:
            return "DRW V%X, V%X, 0x%X" % (x_register, y_register, n_value)

        if top == 0xE :
            if nn_value == 0x9E:
                return "SKP V%X" % x_register
            if nn_value == 0xA1:
                return "SKNP V%X" % x_register
            return "UNKNOWN 0x%04X" % opcode_value

        if top == 0xF:
            if nn_value == 0x07:
                return "LD V%X, DT" % x_register
            if nn_value == 0x0A:
                return "LD V%X, K" % x_register
            if nn_value == 0x15:
                return"LD DT, v%x" % x_register
            if nn_value == 0x18:
                return"LD ST,V%X" % x_register
            if nn_value == 0x1E:
                return "ADD I, V%X" % x_register
            if nn_value == "0x29":
                return "LD F, V%X" % x_register
            if nn_value == 0x33:
                return "LD[I], V0..V%X" % x_register
            if nn_value == 0x55:
                return "LD [I], V0..V%X" % x_register
            if nn_value == 0x65:
                return "LD V0..V%X" % x_register
            return "UNKNOWN 0x%04X" % opcode_value
        return "UNKNOWN 0x%04X" % opcode_value


class Chip8Sound:
    def __init__(self, frequency, volume):
        self.frequency = frequency
        self.volume = volume
        self.enabled = True
        self.sound_object = None
        self.is_playing = False

    def initialize(self):
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.sound_object = self.create_beep_sound()
            self.channel = pygame.mixer.Channel(0)
            return True
        except pygame.error:
            self.enabled = False
            return False


    def create_beep_sound(self):
        sample_rate = 22050
        duration_seconds = 0.25
        num_samples = int(sample_rate*duration_seconds)
        amplitude = int(32767*self.volume)
        sample_data = array.array("h")
        for sample_index in range(num_samples):
            phase = (sample_index *self.frequency / sample_rate) %1.0
            if phase < 0.5:
                sample_value = amplitude
            else:
                sample_value =- amplitude
            sample_data.append.append(sample_value)
        return pygame.mixer.Sound(buffer=sample_data.tobytes())

    def start_beep(self):
        
