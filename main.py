import os
import sys
import math
import time
import array
import random
import pickle
import pygame

HEX_FONT_DATA = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,
    0x20, 0x60, 0x20, 0x20, 0x70,
    0xF0, 0x10, 0xF0, 0x80, 0xF0,
    0xF0, 0x10, 0xF0, 0x10, 0xF0,
    0x90, 0x90, 0xF0, 0x10, 0x10,
    0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0,
    0xF0, 0x10, 0x20, 0x40, 0x40,
    0xF0, 0x90, 0xF0, 0x90, 0xF0,
    0xF0, 0x90, 0xF0, 0x10, 0xF0,
    0xF0, 0x90, 0xF0, 0x90, 0x90,
    0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0,
    0xE0, 0x90, 0x90, 0x90, 0xE0,
    0xF0, 0x80, 0xF0, 0x80, 0xF0,
    0xF0, 0x80, 0xF0, 0x80, 0x80,
]

CHIP8_KEYPAD_MAPPING = {
    pygame.K_1: 0x1, pygame.K_2: 0x2,
    pygame.K_3: 0x3, pygame.K_4: 0xC,
    pygame.K_q: 0x4, pygame.K_w: 0x5,
    pygame.K_e: 0x6, pygame.K_r: 0xD,
    pygame.K_a: 0x7, pygame.K_s: 0x8,
    pygame.K_d: 0x9, pygame.K_f: 0xE,
    pygame.K_z: 0xA, pygame.K_x: 0x0,
    pygame.K_c: 0xB, pygame.K_v: 0xF,
}

ROM_EXTENSIONS = (".ch8", ".rom", ".bin")


def application_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_folder():
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return application_folder()


def ensure_streams():
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def find_roms(folder):
    if not os.path.isdir(folder):
        return []
    result = []
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith(ROM_EXTENSIONS):
            result.append(os.path.join(folder, name))
    return result


def pick_rom_with_dialog():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    path = filedialog.askopenfilename(
        title="Select a CHIP-8 ROM",
        filetypes=[
            ("CHIP-8 ROMs", "*.ch8 *.rom *.bin"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return path or None


def pick_from_list(rom_paths):
    import tkinter as tk

    root = tk.Tk()
    root.title("CHIP-8 - Choose a ROM")
    root.geometry("480x360")
    selection = {"path": None}

    tk.Label(root, text="Bundled ROMs:", anchor="w").pack(
        fill="x", padx=8, pady=(8, 4)
    )

    listbox = tk.Listbox(root)
    for path in rom_paths:
        listbox.insert("end", os.path.basename(path))
    listbox.pack(fill="both", expand=True, padx=8)
    if rom_paths:
        listbox.selection_set(0)

    def on_open():
        indices = listbox.curselection()
        if indices:
            selection["path"] = rom_paths[indices[0]]
            root.destroy()

    def on_browse():
        root.destroy()
        selection["path"] = pick_rom_with_dialog()

    def on_cancel():
        root.destroy()

    button_row = tk.Frame(root)
    button_row.pack(fill="x", padx=8, pady=8)
    tk.Button(button_row, text="Cancel", command=on_cancel).pack(side="left")
    tk.Button(button_row, text="Browse...", command=on_browse).pack(side="right")
    tk.Button(button_row, text="Open", command=on_open).pack(
        side="right", padx=(0, 6)
    )

    listbox.bind("<Double-Button-1>", lambda event: on_open())
    listbox.bind("<Return>", lambda event: on_open())
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()
    return selection["path"]


def choose_rom(argument_list):
    if len(argument_list) >= 2:
        return argument_list[1]

    bundled_folder = os.path.join(resource_folder(), "roms")
    bundled_roms = find_roms(bundled_folder)
    if bundled_roms:
        return pick_from_list(bundled_roms)

    return pick_rom_with_dialog()


class Chip8Config:
    def __init__(self):
        self.display_width = 64
        self.display_height = 32
        self.pixel_scale = 12
        self.window_width = self.display_width * self.pixel_scale
        self.window_height = self.display_height * self.pixel_scale
        self.background_color = (10, 10, 15)
        self.pixel_color = (200, 240, 200)
        self.overlay_text_color = (255, 255, 100)
        self.cpu_hz = 700
        self.timer_hz = 60
        self.window_fps = 60
        self.memory_size = 4096
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
        base_folder = application_folder()
        self.state_folder = os.path.join(base_folder, "states")
        self.screenshot_folder = os.path.join(base_folder, "screenshots")


class Chip8Font:
    def __init__(self, start_address, bytes_per_character):
        self.start_address = start_address
        self.bytes_per_character = bytes_per_character
        self.font_bytes = HEX_FONT_DATA

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
    def __init__(self, total_size):
        self.total_size = total_size
        self.bytes = bytearray(total_size)

    def read_byte(self, address):
        safe_address = address & 0xFFF
        return self.bytes[safe_address]

    def write_byte(self, address, value):
        safe_address = address & 0xFFF
        self.bytes[safe_address] = value & 0xFF

    def read_word(self, address):
        high_byte = self.read_byte(address)
        low_byte = self.read_byte(address + 1)
        return (high_byte << 8) | low_byte

    def write_word(self, address, value):
        self.write_byte(address, (value >> 8) & 0xFF)
        self.write_byte(address + 1, value & 0xFF)

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
            raise ValueError("ROM file is empty")
        available_space = self.total_size - start_address
        if len(rom_bytes) > available_space:
            raise ValueError("ROM is too large: %d bytes (max %d)"
                             % (len(rom_bytes), available_space))
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
            lines.append("0x%03X: 0x%02X" % (address, value))
        return "\n".join(lines)


class Chip8Registers:
    def __init__(self, start_pc):
        self.v_registers = [0] * 16
        self.index_register = 0
        self.program_counter = start_pc

    def get_register(self, register_number):
        safe_number = register_number & 0x0F
        return self.v_registers[safe_number]

    def set_register(self, register_number, value):
        safe_number = register_number & 0x0F
        self.v_registers[safe_number] = value & 0xFF

    def get_flag_register(self):
        return self.v_registers[0x0F]

    def set_flag_register(self, value):
        self.v_registers[0x0F] = value & 0xFF

    def get_index_register(self):
        return self.index_register

    def set_index_register(self, value):
        self.index_register = value & 0xFFFF

    def add_to_index_register(self, value):
        new_value = self.index_register + value
        self.index_register = new_value & 0xFFFF

    def get_program_counter(self):
        return self.program_counter

    def set_program_counter(self, address):
        self.program_counter = address & 0xFFF

    def advance_program_counter(self, amount=2):
        new_value = self.program_counter + amount
        self.program_counter = new_value & 0xFFF

    def dump_as_string(self):
        lines = []
        for index in range(16):
            value = self.v_registers[index]
            lines.append("V%X = 0x%02X (%d)" % (index, value, value))
        lines.append("I = 0x%03X" % self.index_register)
        lines.append("PC = 0x%03X" % self.program_counter)
        return "\n".join(lines)


class Chip8Stack:
    def __init__(self, max_depth):
        self.max_depth = max_depth
        self.addresses = [0] * max_depth
        self.stack_pointer = 0

    def push(self, return_address):
        if self.stack_pointer >= self.max_depth:
            raise OverflowError("Call stack overflow")
        self.addresses[self.stack_pointer] = return_address & 0xFFF
        self.stack_pointer = self.stack_pointer + 1

    def pop(self):
        if self.stack_pointer <= 0:
            raise OverflowError("Call stack underflow")
        self.stack_pointer = self.stack_pointer - 1
        return self.addresses[self.stack_pointer]

    def reset(self):
        for index in range(self.max_depth):
            self.addresses[index] = 0
        self.stack_pointer = 0

    def dump_as_string(self):
        lines = []
        for index in range(self.max_depth):
            marker = "->" if index == self.stack_pointer else "  "
            address = self.addresses[index]
            lines.append("%s [%2d] = 0x%03X" % (marker, index, address))
        return "\n".join(lines)


class Chip8Display:
    def __init__(self, width, height):
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
        self.pixels[y][x] = value & 1
        self.is_dirty = True

    def wrap_x_coordinate(self, x):
        return x % self.width

    def wrap_y_coordinate(self, y):
        return y % self.height

    def draw_sprite_row(self, start_x, start_y, sprite_byte, row_offset):
        collision = 0
        screen_y = self.wrap_y_coordinate(start_y + row_offset)
        for column_offset in range(8):
            bit_mask = 0x80 >> column_offset
            if sprite_byte & bit_mask:
                screen_x = self.wrap_x_coordinate(start_x + column_offset)
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
                    total = total + 1
        return total

    def mark_clean(self):
        self.is_dirty = False

    def mark_dirty(self):
        self.is_dirty = True


class Chip8Keypad:
    def __init__(self):
        self.keys_pressed = [False] * 16
        self.keys_just_pressed = [False] * 16

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

    def consume_just_pressed(self, key_number):
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
        if self.delay_timer > 0:
            self.delay_timer = self.delay_timer - 1
        if self.sound_timer > 0:
            self.sound_timer = self.sound_timer - 1

    def set_delay_timer(self, value):
        self.delay_timer = value & 0xFF

    def set_sound_timer(self, value):
        self.sound_timer = value & 0xFF

    def get_delay_timer(self):
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
        return self.address_nnn


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

    if top == 0x0:
        return "SYS 0x%03X" % nnn_value
    if top == 0x1:
        return "JP 0x%03X" % nnn_value
    if top == 0x2:
        return "CALL 0x%03X" % nnn_value
    if top == 0x3:
        return "SE V%X, 0x%02X" % (x_register, nn_value)
    if top == 0x4:
        return "SNE V%X, 0x%02X" % (x_register, nn_value)
    if top == 0x5:
        return "SE V%X, V%X" % (x_register, y_register)
    if top == 0x6:
        return "LD V%X, 0x%02X" % (x_register, nn_value)
    if top == 0x7:
        return "ADD V%X, 0x%02X" % (x_register, nn_value)
    if top == 0x8:
        if n_value == 0x0:
            return "LD V%X, V%X" % (x_register, y_register)
        if n_value == 0x1:
            return "OR V%X, V%X" % (x_register, y_register)
        if n_value == 0x2:
            return "AND V%X, V%X" % (x_register, y_register)
        if n_value == 0x3:
            return "XOR V%X, V%X" % (x_register, y_register)
        if n_value == 0x4:
            return "ADD V%X, V%X" % (x_register, y_register)
        if n_value == 0x5:
            return "SUB V%X, V%X" % (x_register, y_register)
        if n_value == 0x6:
            return "SHR V%X" % x_register
        if n_value == 0x7:
            return "SUBN V%X, V%X" % (x_register, y_register)
        if n_value == 0xE:
            return "SHL V%X" % x_register
        return "UNKNOWN 0x%04X" % opcode_value

    if top == 0x9:
        return "SNE V%X, V%X" % (x_register, y_register)
    if top == 0xA:
        return "LD I, 0x%03X" % nnn_value
    if top == 0xB:
        return "JP V0, 0x%03X" % nnn_value
    if top == 0xC:
        return "RND V%X, 0x%02X" % (x_register, nn_value)
    if top == 0xD:
        return "DRW V%X, V%X, 0x%X" % (x_register, y_register, n_value)

    if top == 0xE:
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
            return "LD DT, V%X" % x_register
        if nn_value == 0x18:
            return "LD ST, V%X" % x_register
        if nn_value == 0x1E:
            return "ADD I, V%X" % x_register
        if nn_value == 0x29:
            return "LD F, V%X" % x_register
        if nn_value == 0x33:
            return "LD B, V%X" % x_register
        if nn_value == 0x55:
            return "LD [I], V0..V%X" % x_register
        if nn_value == 0x65:
            return "LD V0..V%X, [I]" % x_register
        return "UNKNOWN 0x%04X" % opcode_value
    return "UNKNOWN 0x%04X" % opcode_value


class Chip8Sound:
    def __init__(self, frequency, volume):
        self.frequency = frequency
        self.volume = volume
        self.enabled = True
        self.sound_object = None
        self.channel = None
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
        num_samples = int(sample_rate * duration_seconds)
        amplitude = int(32767 * self.volume)
        sample_data = array.array("h")
        for sample_index in range(num_samples):
            phase = (sample_index * self.frequency / sample_rate) % 1.0
            if phase < 0.5:
                sample_value = amplitude
            else:
                sample_value = -amplitude
            sample_data.append(sample_value)
        return pygame.mixer.Sound(buffer=sample_data.tobytes())

    def start_beep(self):
        if not self.enabled:
            return
        if self.is_playing:
            return
        self.channel.play(self.sound_object, loops=-1)
        self.is_playing = True

    def stop_beep(self):
        if not self.enabled:
            return
        if not self.is_playing:
            return
        self.channel.stop()
        self.is_playing = False

    def update_from_timer(self, sound_timer_value):
        if sound_timer_value > 0:
            self.start_beep()
        else:
            self.stop_beep()


class Chip8StateManager:
    def __init__(self, state_folder):
        self.state_folder = state_folder

    def ensure_folder_exists(self):
        if not os.path.exists(self.state_folder):
            os.makedirs(self.state_folder)

    def build_state_dict(self, machine):
        state_data = {
            "memory": bytes(machine.memory.bytes),
            "v_registers": list(machine.registers.v_registers),
            "index_register": machine.registers.index_register,
            "program_counter": machine.registers.program_counter,
            "stack_addresses": list(machine.stack.addresses),
            "stack_pointer": machine.stack.stack_pointer,
            "delay_timer": machine.timers.delay_timer,
            "sound_timer": machine.timers.sound_timer,
            "display_pixels": [list(row) for row in machine.display.pixels],
        }
        return state_data

    def save_state(self, machine, slot_name):
        self.ensure_folder_exists()
        state_path = os.path.join(self.state_folder, slot_name + ".state")
        state_data = self.build_state_dict(machine)
        state_file = open(state_path, "wb")
        pickle.dump(state_data, state_file)
        state_file.close()
        return state_path

    def load_state(self, machine, slot_name):
        state_path = os.path.join(self.state_folder, slot_name + ".state")
        if not os.path.exists(state_path):
            raise FileNotFoundError(state_path)
        state_file = open(state_path, "rb")
        state_data = pickle.load(state_file)
        state_file.close()
        machine.memory.bytes = bytearray(state_data["memory"])
        machine.registers.v_registers = list(state_data["v_registers"])
        machine.registers.index_register = state_data["index_register"]
        machine.registers.program_counter = state_data["program_counter"]
        machine.stack.addresses = list(state_data["stack_addresses"])
        machine.stack.stack_pointer = state_data["stack_pointer"]
        machine.timers.delay_timer = state_data["delay_timer"]
        machine.timers.sound_timer = state_data["sound_timer"]
        machine.display.pixels = [list(row) for row in state_data["display_pixels"]]
        machine.display.mark_dirty()
        return True


class Chip8Machine:
    def __init__(self, config):
        self.config = config
        self.memory = Chip8Memory(config.memory_size)
        self.registers = Chip8Registers(config.rom_start_address)
        self.stack = Chip8Stack(config.max_stack_depth)
        self.display = Chip8Display(config.display_width, config.display_height)
        self.keypad = Chip8Keypad()
        self.timers = Chip8Timers()
        self.font = Chip8Font(config.font_start_address, config.font_bytes_per_character)
        self.sound = Chip8Sound(config.sound_frequency, config.sound_volume)

        self.current_opcode = 0
        self.waiting_for_key_register = None
        self.instructions_executed = 0
        self.instruction_history = []

        self.rom_is_loaded = False
        self.rom_file_path = ""
        self.rom_size_bytes = 0

        self.load_font_into_memory()

    def load_font_into_memory(self):
        self.memory.load_bytes(self.font.start_address, self.font.font_bytes)

    def load_rom(self, rom_file_path):
        loaded_size = self.memory.load_rom_from_file(rom_file_path, self.config.rom_start_address)
        self.rom_is_loaded = True
        self.rom_file_path = rom_file_path
        self.rom_size_bytes = loaded_size
        return loaded_size

    def reset(self):
        self.memory = Chip8Memory(self.config.memory_size)
        self.registers = Chip8Registers(self.config.rom_start_address)
        self.stack.reset()
        self.display.clear()
        self.keypad.release_all_keys()
        self.timers.reset()
        self.current_opcode = 0
        self.waiting_for_key_register = None
        self.instructions_executed = 0
        self.instruction_history = []
        self.load_font_into_memory()
        if self.rom_file_path and os.path.exists(self.rom_file_path):
            self.load_rom(self.rom_file_path)

    def fetch_opcode(self):
        current_pc = self.registers.get_program_counter()
        high_byte = self.memory.read_byte(current_pc)
        low_byte = self.memory.read_byte(current_pc + 1)
        self.current_opcode = (high_byte << 8) | low_byte
        self.registers.advance_program_counter(2)
        if self.config.debug_mode:
            print("[fetch] PC=0x%03X op=0x%04X %s"
                  % (current_pc, self.current_opcode,
                     disassemble_opcode(self.current_opcode)))
        return current_pc

    def record_instruction_history(self, pc):
        entry = {
            "pc": pc,
            "opcode": self.current_opcode,
            "text": disassemble_opcode(self.current_opcode),
        }
        self.instruction_history.append(entry)
        if len(self.instruction_history) > self.config.instruction_history_max:
            self.instruction_history.pop(0)

    def step(self):
        if self.waiting_for_key_register is not None:
            pressed_key = self.keypad.get_first_pressed_key()
            if pressed_key is None:
                return
            self.registers.set_register(self.waiting_for_key_register, pressed_key)
            self.waiting_for_key_register = None
            return

        current_pc = self.fetch_opcode()
        self.record_instruction_history(current_pc)
        self.decode_and_execute()
        self.instructions_executed = self.instructions_executed + 1

    def tick_timers(self):
        self.timers.tick()

    def decode_and_execute(self):
        decoder = OpcodeDecoder(self.current_opcode)
        top = decoder.top_nibble

        if top == 0x0:
            self.execute_0xxx(decoder)
        elif top == 0x1:
            self.opcode_1nnn_jump(decoder)
        elif top == 0x2:
            self.opcode_2nnn_call(decoder)
        elif top == 0x3:
            self.opcode_3xnn_skip_if_equal(decoder)
        elif top == 0x4:
            self.opcode_4xnn_skip_if_not_equal(decoder)
        elif top == 0x5:
            self.opcode_5xy0_skip_if_equal_registers(decoder)
        elif top == 0x6:
            self.opcode_6xnn_load_byte(decoder)
        elif top == 0x7:
            self.opcode_7xnn_add_byte(decoder)
        elif top == 0x8:
            self.execute_8xxx(decoder)
        elif top == 0x9:
            self.opcode_9xy0_skip_if_not_equal_registers(decoder)
        elif top == 0xA:
            self.opcode_annn_load_index(decoder)
        elif top == 0xB:
            self.opcode_bnnn_jump_with_offset(decoder)
        elif top == 0xC:
            self.opcode_cxnn_random(decoder)
        elif top == 0xD:
            self.opcode_dxyn_draw_sprite(decoder)
        elif top == 0xE:
            self.execute_exxx(decoder)
        elif top == 0xF:
            self.execute_fxxx(decoder)
        else:
            print("[warning] unknown opcode 0x%04X" % self.current_opcode)

    def execute_0xxx(self, decoder):
        if self.current_opcode == 0x00E0:
            self.opcode_00e0_clear_display()
        elif self.current_opcode == 0x00EE:
            self.opcode_00ee_return_from_subroutine()
        else:
            if self.config.debug_mode:
                print("[info] ignore legacy sys 0x%03X" % decoder.address_nnn)

    def execute_8xxx(self, decoder):
        n_value = decoder.nibble_n
        if n_value == 0x0:
            self.opcode_8xy0_copy_register(decoder)
        elif n_value == 0x1:
            self.opcode_8xy1_bitwise_or(decoder)
        elif n_value == 0x2:
            self.opcode_8xy2_bitwise_and(decoder)
        elif n_value == 0x3:
            self.opcode_8xy3_bitwise_xor(decoder)
        elif n_value == 0x4:
            self.opcode_8xy4_add_registers(decoder)
        elif n_value == 0x5:
            self.opcode_8xy5_subtract_registers(decoder)
        elif n_value == 0x6:
            self.opcode_8xy6_shift_right(decoder)
        elif n_value == 0x7:
            self.opcode_8xy7_subtract_reverse(decoder)
        elif n_value == 0xE:
            self.opcode_8xye_shift_left(decoder)
        else:
            print("[warning] unknown 8XYN opcode 0x%04X" % self.current_opcode)

    def execute_exxx(self, decoder):
        nn_value = decoder.byte_nn
        if nn_value == 0x9E:
            self.opcode_ex9e_skip_if_key_pressed(decoder)
        elif nn_value == 0xA1:
            self.opcode_exa1_skip_key_not_pressed(decoder)
        else:
            print("[warning] unknown ExNN opcode 0x%04X" % self.current_opcode)

    def execute_fxxx(self, decoder):
        nn_value = decoder.byte_nn
        if nn_value == 0x07:
            self.opcode_fx07_read_delay_timer(decoder)
        elif nn_value == 0x0A:
            self.opcode_fx0a_wait_for_key(decoder)
        elif nn_value == 0x15:
            self.opcode_fx15_set_delay_timer(decoder)
        elif nn_value == 0x18:
            self.opcode_fx18_set_sound_timer(decoder)
        elif nn_value == 0x1E:
            self.opcode_fx1e_add_to_index(decoder)
        elif nn_value == 0x29:
            self.opcode_fx29_load_font_address(decoder)
        elif nn_value == 0x33:
            self.opcode_fx33_store_bcd(decoder)
        elif nn_value == 0x55:
            self.opcode_fx55_save_registers_to_memory(decoder)
        elif nn_value == 0x65:
            self.opcode_fx65_load_registers_from_memory(decoder)
        else:
            print("[warning] unknown FXnn opcode 0x%04X" % self.current_opcode)

    def opcode_00e0_clear_display(self):
        self.display.clear()

    def opcode_00ee_return_from_subroutine(self):
        return_address = self.stack.pop()
        self.registers.set_program_counter(return_address)

    def opcode_1nnn_jump(self, decoder):
        self.registers.set_program_counter(decoder.address_nnn)

    def opcode_2nnn_call(self, decoder):
        self.stack.push(self.registers.get_program_counter())
        self.registers.set_program_counter(decoder.address_nnn)

    def opcode_3xnn_skip_if_equal(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        if x_value == decoder.byte_nn:
            self.registers.advance_program_counter(2)

    def opcode_4xnn_skip_if_not_equal(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        if x_value != decoder.byte_nn:
            self.registers.advance_program_counter(2)

    def opcode_5xy0_skip_if_equal_registers(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        y_value = self.registers.get_register(decoder.register_y)
        if x_value == y_value:
            self.registers.advance_program_counter(2)

    def opcode_6xnn_load_byte(self, decoder):
        self.registers.set_register(decoder.register_x, decoder.byte_nn)

    def opcode_7xnn_add_byte(self, decoder):
        current_value = self.registers.get_register(decoder.register_x)
        new_value = current_value + decoder.byte_nn
        self.registers.set_register(decoder.register_x, new_value)

    def opcode_8xy0_copy_register(self, decoder):
        y_value = self.registers.get_register(decoder.register_y)
        self.registers.set_register(decoder.register_x, y_value)

    def opcode_8xy1_bitwise_or(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        y_value = self.registers.get_register(decoder.register_y)
        result = x_value | y_value
        self.registers.set_register(decoder.register_x, result)

    def opcode_8xy2_bitwise_and(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        y_value = self.registers.get_register(decoder.register_y)
        result = x_value & y_value
        self.registers.set_register(decoder.register_x, result)

    def opcode_8xy3_bitwise_xor(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        y_value = self.registers.get_register(decoder.register_y)
        result = x_value ^ y_value
        self.registers.set_register(decoder.register_x, result)

    def opcode_8xy4_add_registers(self, decoder):
        x_register = decoder.register_x
        x_value = self.registers.get_register(x_register)
        y_value = self.registers.get_register(decoder.register_y)
        total = x_value + y_value
        self.registers.set_register(x_register, total)
        if total > 0xFF:
            self.registers.set_flag_register(1)
        else:
            self.registers.set_flag_register(0)

    def opcode_8xy5_subtract_registers(self, decoder):
        x_register = decoder.register_x
        x_value = self.registers.get_register(x_register)
        y_value = self.registers.get_register(decoder.register_y)
        result = x_value - y_value
        self.registers.set_register(x_register, result)
        if x_value >= y_value:
            self.registers.set_flag_register(1)
        else:
            self.registers.set_flag_register(0)

    def opcode_8xy6_shift_right(self, decoder):
        x_register = decoder.register_x
        x_value = self.registers.get_register(x_register)
        lowest_bit = x_value & 0x01
        shifted = x_value >> 1
        self.registers.set_register(x_register, shifted)
        self.registers.set_flag_register(lowest_bit)

    def opcode_8xy7_subtract_reverse(self, decoder):
        x_register = decoder.register_x
        x_value = self.registers.get_register(x_register)
        y_value = self.registers.get_register(decoder.register_y)
        result = y_value - x_value
        self.registers.set_register(x_register, result)
        if y_value >= x_value:
            self.registers.set_flag_register(1)
        else:
            self.registers.set_flag_register(0)

    def opcode_8xye_shift_left(self, decoder):
        x_register = decoder.register_x
        x_value = self.registers.get_register(x_register)
        highest_bit = (x_value & 0x80) >> 7
        shifted = x_value << 1
        self.registers.set_register(x_register, shifted)
        self.registers.set_flag_register(highest_bit)

    def opcode_9xy0_skip_if_not_equal_registers(self, decoder):
        x_value = self.registers.get_register(decoder.register_x)
        y_value = self.registers.get_register(decoder.register_y)
        if x_value != y_value:
            self.registers.advance_program_counter(2)

    def opcode_annn_load_index(self, decoder):
        self.registers.set_index_register(decoder.address_nnn)

    def opcode_bnnn_jump_with_offset(self, decoder):
        offset_value = self.registers.get_register(0)
        target_address = decoder.address_nnn + offset_value
        self.registers.set_program_counter(target_address)

    def opcode_cxnn_random(self, decoder):
        random_byte = random.randint(0, 255)
        result = random_byte & decoder.byte_nn
        self.registers.set_register(decoder.register_x, result)

    def opcode_dxyn_draw_sprite(self, decoder):
        start_x = self.registers.get_register(decoder.register_x)
        start_y = self.registers.get_register(decoder.register_y)
        sprite_height = decoder.nibble_n
        self.registers.set_flag_register(0)
        index_value = self.registers.get_index_register()
        for row_offset in range(sprite_height):
            address = index_value + row_offset
            sprite_byte = self.memory.read_byte(address)
            collision = self.display.draw_sprite_row(start_x, start_y, sprite_byte, row_offset)
            if collision == 1:
                self.registers.set_flag_register(1)

    def opcode_ex9e_skip_if_key_pressed(self, decoder):
        key_number = self.registers.get_register(decoder.register_x) & 0x0F
        if self.keypad.is_key_pressed(key_number):
            self.registers.advance_program_counter(2)

    def opcode_exa1_skip_key_not_pressed(self, decoder):
        key_number = self.registers.get_register(decoder.register_x) & 0x0F
        if not self.keypad.is_key_pressed(key_number):
            self.registers.advance_program_counter(2)

    def opcode_fx07_read_delay_timer(self, decoder):
        delay_value = self.timers.get_delay_timer()
        self.registers.set_register(decoder.register_x, delay_value)

    def opcode_fx0a_wait_for_key(self, decoder):
        self.waiting_for_key_register = decoder.register_x

    def opcode_fx15_set_delay_timer(self, decoder):
        register_value = self.registers.get_register(decoder.register_x)
        self.timers.set_delay_timer(register_value)

    def opcode_fx18_set_sound_timer(self, decoder):
        register_value = self.registers.get_register(decoder.register_x)
        self.timers.set_sound_timer(register_value)

    def opcode_fx1e_add_to_index(self, decoder):
        register_value = self.registers.get_register(decoder.register_x)
        self.registers.add_to_index_register(register_value)

    def opcode_fx29_load_font_address(self, decoder):
        character_value = self.registers.get_register(decoder.register_x)
        font_address = self.font.get_character_address(character_value)
        self.registers.set_index_register(font_address)

    def opcode_fx33_store_bcd(self, decoder):
        register_value = self.registers.get_register(decoder.register_x)
        hundreds = register_value // 100
        tens = (register_value // 10) % 10
        ones = register_value % 10
        index_value = self.registers.get_index_register()
        self.memory.write_byte(index_value, hundreds)
        self.memory.write_byte(index_value + 1, tens)
        self.memory.write_byte(index_value + 2, ones)

    def opcode_fx55_save_registers_to_memory(self, decoder):
        index_value = self.registers.get_index_register()
        for register_number in range(decoder.register_x + 1):
            value = self.registers.get_register(register_number)
            self.memory.write_byte(index_value + register_number, value)

    def opcode_fx65_load_registers_from_memory(self, decoder):
        index_value = self.registers.get_index_register()
        for register_number in range(decoder.register_x + 1):
            value = self.memory.read_byte(index_value + register_number)
            self.registers.set_register(register_number, value)

    def dump_registers(self):
        return self.registers.dump_as_string()

    def dump_stack(self):
        return self.stack.dump_as_string()

    def dump_memory_slice(self, start_address, length):
        return self.memory.dump_slice_as_string(start_address, length)

    def dump_instruction_history(self):
        lines = []
        for entry in self.instruction_history:
            lines.append("PC=0x%03X  op=0x%04X  %s"
                         % (entry["pc"], entry["opcode"], entry["text"]))
        return "\n".join(lines)


class Chip8Renderer:
    def __init__(self, config):
        self.config = config
        self.screen = None
        self.small_surface = None
        self.overlay_font = None
        self.fps_font = None

    def initialize(self):
        pygame.init()
        window_size = (self.config.window_width, self.config.window_height)
        self.screen = pygame.display.set_mode(window_size)
        pygame.display.set_caption("CHIP-8 Interpreter")
        display_size = (self.config.display_width, self.config.display_height)
        self.small_surface = pygame.Surface(display_size)
        self.overlay_font = pygame.font.SysFont("monospace", 14)
        self.fps_font = pygame.font.SysFont("monospace", 16)

    def draw_display(self, display):
        self.small_surface.fill(self.config.background_color)
        for row_index in range(display.height):
            for column_index in range(display.width):
                if display.pixels[row_index][column_index] == 1:
                    pixel_color = self.config.pixel_color
                    self.small_surface.set_at((column_index, row_index), pixel_color)
        new_size = (self.config.window_width, self.config.window_height)
        scaled_surface = pygame.transform.scale(self.small_surface, new_size)
        self.screen.blit(scaled_surface, (0, 0))

    def draw_debug_overlay(self, machine, fps_value, paused):
        line_entries = []
        line_entries.append("PC: 0x%03X  I: 0x%03X"
                            % (machine.registers.get_program_counter(),
                               machine.registers.get_index_register()))
        line_entries.append("Opcode: 0x%04X  %s"
                            % (machine.current_opcode,
                               disassemble_opcode(machine.current_opcode)))
        line_entries.append("Insns: %d" % machine.instructions_executed)
        line_entries.append("DT: %d  ST: %d"
                            % (machine.timers.get_delay_timer(),
                               machine.timers.get_sound_timer()))
        line_entries.append("Paused: %s" % ("yes" if paused else "no"))
        y_position = 4
        for text_line in line_entries:
            color = self.config.overlay_text_color
            rendered = self.overlay_font.render(text_line, True, color)
            self.screen.blit(rendered, (4, y_position))
            y_position = y_position + 16

    def draw_fps_counter(self, fps_value):
        text = "FPS: %.1f" % fps_value
        color = self.config.overlay_text_color
        rendered = self.fps_font.render(text, True, color)
        text_width = rendered.get_width()
        text_height = rendered.get_height()
        draw_x = self.config.window_width - text_width - 4
        draw_y = self.config.window_height - text_height - 4
        self.screen.blit(rendered, (draw_x, draw_y))

    def save_screenshot(self, screenshot_folder, file_name):
        if not os.path.exists(screenshot_folder):
            os.makedirs(screenshot_folder)
        file_path = os.path.join(screenshot_folder, file_name)
        pygame.image.save(self.screen, file_path)
        return file_path

    def flip(self):
        pygame.display.flip()


class Chip8InputHandler:
    def __init__(self, machine, state_manager, renderer, config):
        self.machine = machine
        self.state_manager = state_manager
        self.renderer = renderer
        self.config = config
        self.should_quit = False
        self.is_paused = False
        self.should_step_once = False

    def handle_all_events(self):
        for event in pygame.event.get():
            self.handle_event(event)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.should_quit = True
            return
        if event.type == pygame.KEYDOWN:
            self.handle_key_down(event.key)
        if event.type == pygame.KEYUP:
            self.handle_key_up(event.key)

    def handle_key_down(self, key):
        if key == pygame.K_ESCAPE:
            self.should_quit = True
            return
        if key == pygame.K_SPACE:
            self.is_paused = not self.is_paused
            return
        if key == pygame.K_F1:
            self.machine.reset()
            return
        if key == pygame.K_F5:
            self.save_current_state()
            return
        if key == pygame.K_F9:
            self.load_current_state()
            return
        if key == pygame.K_F12:
            self.take_screenshot()
            return
        if key == pygame.K_PERIOD:
            if self.is_paused:
                self.should_step_once = True
            return
        if key in CHIP8_KEYPAD_MAPPING:
            chip8_key = CHIP8_KEYPAD_MAPPING[key]
            self.machine.keypad.press_key(chip8_key)

    def handle_key_up(self, key):
        if key in CHIP8_KEYPAD_MAPPING:
            chip8_key = CHIP8_KEYPAD_MAPPING[key]
            self.machine.keypad.release_key(chip8_key)

    def save_current_state(self):
        try:
            path = self.state_manager.save_state(self.machine, "slot1")
            print("[state] Saved to %s" % path)
        except Exception as error:
            print("[state] Save failed: %s" % str(error))

    def load_current_state(self):
        try:
            self.state_manager.load_state(self.machine, "slot1")
            print("[state] Loaded from slot1")
        except Exception as error:
            print("[state] Load failed: %s" % str(error))

    def take_screenshot(self):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_name = "screenshot_%s.png" % timestamp
        try:
            path = self.renderer.save_screenshot(
                self.config.screenshot_folder, file_name
            )
            print("[screenshot] Saved to %s" % path)
        except Exception as error:
            print("[screenshot] Failed: %s" % str(error))


class Chip8Frontend:
    def __init__(self, config, machine):
        self.config = config
        self.machine = machine
        self.state_manager = Chip8StateManager(config.state_folder)
        self.renderer = Chip8Renderer(config)
        self.input_handler = None
        self.clock = None
        self.cpu_cycle_accumulator = 0.0
        self.timer_tick_accumulator = 0.0
        self.seconds_per_cpu_cycle = 1.0 / config.cpu_hz
        self.seconds_per_timer_tick = 1.0 / config.timer_hz
        self.fps_sample_accumulator = 0.0
        self.fps_sample_frames = 0
        self.fps_display_value = 0.0

    def initialize(self):
        self.renderer.initialize()
        if self.config.enable_sound:
            self.machine.sound.initialize()
        self.input_handler = Chip8InputHandler(
            self.machine, self.state_manager, self.renderer, self.config
        )
        self.clock = pygame.time.Clock()

    def run(self):
        self.initialize()
        still_running = True
        while still_running:
            elapsed_seconds = self.clock.tick(self.config.window_fps) / 1000.0
            self.input_handler.handle_all_events()

            if self.input_handler.should_quit:
                still_running = False
                break

            self.update_fps_counter(elapsed_seconds)

            if not self.input_handler.is_paused:
                self.run_cpu_and_timers(elapsed_seconds)
            elif self.input_handler.should_step_once:
                self.machine.step()
                self.input_handler.should_step_once = False

            self.render_frame()
            self.renderer.flip()

        self.shutdown()

    def update_fps_counter(self, elapsed_seconds):
        self.fps_sample_accumulator = self.fps_sample_accumulator + elapsed_seconds
        self.fps_sample_frames = self.fps_sample_frames + 1
        if self.fps_sample_accumulator >= 0.5:
            self.fps_display_value = (
                self.fps_sample_frames / self.fps_sample_accumulator
            )
            self.fps_sample_accumulator = 0.0
            self.fps_sample_frames = 0

    def run_cpu_and_timers(self, elapsed_seconds):
        self.timer_tick_accumulator = self.timer_tick_accumulator + elapsed_seconds
        while self.timer_tick_accumulator >= self.seconds_per_timer_tick:
            self.machine.tick_timers()
            self.timer_tick_accumulator = (
                self.timer_tick_accumulator - self.seconds_per_timer_tick
            )

        self.cpu_cycle_accumulator = self.cpu_cycle_accumulator + elapsed_seconds
        cycle_count = int(self.cpu_cycle_accumulator / self.seconds_per_cpu_cycle)
        for cycle_index in range(cycle_count):
            self.machine.step()
        consumed_time = cycle_count * self.seconds_per_cpu_cycle
        self.cpu_cycle_accumulator = self.cpu_cycle_accumulator - consumed_time

        if self.config.enable_sound:
            sound_value = self.machine.timers.get_sound_timer()
            self.machine.sound.update_from_timer(sound_value)

    def render_frame(self):
        self.renderer.draw_display(self.machine.display)
        if self.config.show_debug_overlay:
            self.renderer.draw_debug_overlay(
                self.machine,
                self.fps_display_value,
                self.input_handler.is_paused,
            )
        if self.config.show_fps_counter:
            self.renderer.draw_fps_counter(self.fps_display_value)

    def shutdown(self):
        if self.config.enable_sound:
            self.machine.sound.stop_beep()
        if self.config.debug_mode:
            print("[shutdown] Instructions executed: %d"
                  % self.machine.instructions_executed)
            print(self.machine.dump_registers())
        pygame.quit()


def main(argument_list):
    ensure_streams()

    config = Chip8Config()
    rom_path = choose_rom(argument_list)

    if not rom_path:
        sys.exit(0)

    if not os.path.exists(rom_path):
        print("ERROR: ROM file not found: %s" % rom_path)
        sys.exit(1)

    machine = Chip8Machine(config)

    try:
        loaded_size = machine.load_rom(rom_path)
    except (OSError, ValueError) as error:
        print("ERROR: Could not load ROM: %s" % str(error))
        sys.exit(1)

    print("[startup] Loaded ROM: %s (%d bytes)" % (rom_path, loaded_size))
    print("[startup] CPU at %d Hz, timers at %d Hz"
          % (config.cpu_hz, config.timer_hz))

    frontend = Chip8Frontend(config, machine)
    try:
        frontend.run()
    except KeyboardInterrupt:
        print("\n[shutdown] Interrupted by user.")
    finally:
        if pygame.get_init():
            pygame.quit()

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv)