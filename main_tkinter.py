import sys
import math
import random
import tkinter
import time
import argparse
import queue
import threading

TIMED_COMMAND_QUEUE = queue.Queue()
NOTIFY_QUEUE = queue.Queue()
TIMED_THREAD = None

CELL_SIZE = 10
WINDOW_WIDTH = 64 * CELL_SIZE
WINDOW_HEIGHT = 32 * CELL_SIZE

root = tkinter.Tk()
root.title('CHIP-8')
canvas_main = tkinter.Canvas(root, bg="black", height=WINDOW_HEIGHT, width=WINDOW_WIDTH)

V = [0 for _ in range(16)]
MEM = [0 for _ in range(4096)]
I = 0
STK = [0 for _ in range(16)]
SP = 0
DELAY = 0
SOUND = 0
SCREEN = [0 for _ in range(64 * 32)]
PC = 0x200
KEY_BUFFER = {}
WAITKEY = False
WAITKEY_TARGET = None
RUNNING = True

DEBUG_FLAG = False
SCHIP_COMPATIBLE_FLAG = False

for y in range(32):
    for x in range(64):
        i = y * 64 + x
        canvas_main.create_rectangle(
            x * CELL_SIZE, y * CELL_SIZE,
            x * CELL_SIZE + CELL_SIZE, y * CELL_SIZE + CELL_SIZE,
            fill='black',
            outline='black',
        )
canvas_main.pack()

FONT_BASE = 0x0
FONT = [
    0xf0, 0x90, 0x90, 0x90, 0xf0,
    0x20, 0x60, 0x20, 0x20, 0x70,
    0xf0, 0x10, 0xf0, 0x80, 0xf0,
    0xf0, 0x10, 0xf0, 0x10, 0xf0,
    0x90, 0x90, 0xf0, 0x10, 0x10,
    0xf0, 0x80, 0xf0, 0x10, 0xf0,
    0xf0, 0x80, 0xf0, 0x90, 0xf0,
    0xf0, 0x10, 0x20, 0x40, 0x40,
    0xf0, 0x90, 0xf0, 0x90, 0xf0,
    0xf0, 0x90, 0xf0, 0x10, 0xf0,
    0xf0, 0x90, 0xf0, 0x90, 0x90,
    0xe0, 0x90, 0xe0, 0x90, 0xe0,
    0xf0, 0x80, 0x80, 0x80, 0xf0,
    0xe0, 0x90, 0x90, 0x90, 0xe0,
    0xf0, 0x80, 0xf0, 0x80, 0xf0,
    0xf0, 0x80, 0xf0, 0x80, 0x80,
]
for i, x in enumerate(FONT):
    MEM[FONT_BASE+i] = x

def _N(s: str) -> int:
    r = 0
    for i in s:
        r *= 16
        if '0' <= i <= '9': r += ord(i) - ord('0')
        elif 'a' <= i <= 'f': r += ord(i) - ord('a') + 10
        elif 'A' <= i <= 'F': r += ord(i) - ord('A') + 10
    return r

def disasm_s(s: str, next_s: str = ''):
    if not s: return ''
    elif s == '00E0': return 'CLEAR_SCREEN'
    elif s == '00EE': return 'RET'
    elif s[0] == '1': return f'JMP 0x{s[1:]}'
    elif s[0] == '2': return f'CALL 0x{s[1:]}'
    elif s[0] == '3': return f'IF_NEQ V{s[1]},0x{s[2:]}: {disasm_s(next_s)}'
    elif s[0] == '4': return f'IF_EQ V{s[1]},0x{s[2:]}: {disasm_s(next_s)}'
    elif s[0] == '5': return f'IF_NEQ V{s[1]},V{s[1]}: {disasm_s(next_s)}'
    elif s[0] == '6': return f'LD V{s[1]},0x{s[2:]}'
    elif s[0] == '7': return f'ADD V{s[1]},0x{s[2:]}'
    elif s[0] == '8':
        if s[3] == '0': return f'LD V{s[1]},V{s[2]}'
        elif s[3] == '1': return f'OR V{s[1]},V{s[2]}'
        elif s[3] == '2': return f'AND V{s[1]},V{s[2]}'
        elif s[3] == '3': return f'XOR V{s[1]},V{s[2]}'
        elif s[3] == '4': return f'ADDC V{s[1]},V{s[2]}'
        elif s[3] == '5': return f'SUBC V{s[1]},V{s[2]}'
        elif s[3] == '6': return f'SHR V{s[1]},V{s[2]}'
        elif s[3] == '7': return f'SUB2 V{s[1]},V{s[2]}'
        elif s[3] == 'E': return f'SHL V{s[1]},V{s[2]}'
    elif s[0] == '9': return f'IF_EQ V{s[1]},V{s[2]}: {disasm_s(next_s)}'
    elif s[0] == 'A': return f'LDI 0x{s[1:]}'
    elif s[0] == 'B': return f'JMP V0+0x{s[1:]}'
    elif s[0] == 'C': return f'RANDOM V{s[1]},0x{s[2:]}'
    elif s[0] == 'D': return f'DRAW V{s[1]},V{s[2]},0x{s[3]}'
    elif s[0] == 'E':
        if s[2:] == '9E': return f'IF_NOTKEY V{s[1]}: {disasm_s(next_s)}'
        elif s[2:] == 'A1': return f'IF_KEY V{s[1]}: {disasm_s(next_s)}'
    elif s[0] == 'F':
        if s[2:] == '07': return f'GET_DELAY V{s[1]}'
        elif s[2:] == '0A': return f'WAITKEY V{s[1]}'
        elif s[2:] == '15': return f'SET_DELAY V{s[1]}'
        elif s[2:] == '18': return f'SET_SOUND V{s[1]}'
        elif s[2:] == '1E': return f'ADD I,V{s[1]}'
        elif s[2:] == '29': return f'CHAR V{s[1]}'
        elif s[2:] == '33': return f'BCD V{s[1]}'
        elif s[2:] == '55': return f'STR {s[1]}'
        elif s[2:] == '65': return f'LDR {s[1]}'
    return '<UNSPECIFIED>'

def exec():
    global I, SP, DELAY, SOUND, PC, WAITKEY, WAITKEY_TARGET, RUNNING
    print('Interpreter started.')
    while RUNNING:
        try:
            if NOTIFY_QUEUE.get_nowait() == 'END':
                RUNNING = False
                continue
        except:
            pass
        if WAITKEY:
            root.update()
            continue
        # instr are 2-bytes long, big endian.
        instr_1 = MEM[PC]; instr_2 = MEM[PC+1]
        s = f'{instr_1:02X}{instr_2:02X}'
        if DEBUG_FLAG:
            next_s = '' if PC >= 4095 else f'{MEM[PC+2]:02X}{MEM[PC+2]:02X}'
            print(f'PC=0x{PC:04X} [{s}] {disasm_s(s, next_s)}')
            print(f'I={I:04X} DELAY={DELAY:04X} SOUND={SOUND:04X}')
            print(' '.join([f'V{i:01X}=0x{V[i]:02X}({V[i]})' for i in range(0, 8)]))
            print(' '.join([f'V{i:01X}=0x{V[i]:02X}({V[i]})' for i in range(8, 16)]))
            print(f'SP: {SP} STK: {STK}')
            prompt = None
            while True:
                prompt = input('>> ').lower()
                if not prompt: continue
                elif prompt == 'q': sys.exit(0)
                elif prompt == 's': break
                elif prompt[0] == 'm':
                    m = _N(prompt[1:])
                    print(f'0x{m:04X} {MEM[m]}')
                elif prompt[0] == 'v':
                    d = V[_N(prompt[1:])]
                    print(f'V{prompt[1]} = {d:02X} ({d})')

        if s[0] == '0':
            if s == '00E0':
                for i in range(64 * 32): SCREEN[i] = False
                PC += 2
            elif s == '00EE':
                SP -= 1
                if SP < 0: raise Error('stack underflow')
                PC = STK[SP]
                root.update()
            else:
                print(f'Unsupported instruction {s}')
                raise Exception()
                PC += 2
        elif s[0] == '1':
            NNN = _N(s[1:])
            PC = NNN
            root.update()
        elif s[0] == '2':
            NNN = _N(s[1:])
            STK[SP] = PC+2
            SP += 1
            PC = NNN
            root.update()
        elif s[0] == '3':
            X = _N(s[1]); NN = _N(s[2:])
            if V[X] == NN: PC += 2
            PC += 2
        elif s[0] == '4':
            X = _N(s[1]); NN = _N(s[2:])
            if V[X] != NN: PC += 2
            PC += 2
        elif s[0] == '5':
            X = _N(s[1]); Y = _N(s[2])
            if V[X] == V[Y]: PC += 2
            PC += 2
        elif s[0] == '6':
            X = _N(s[1]); NN = _N(s[2:])
            V[X] = NN; V[X] %= 256
            PC += 2
        elif s[0] == '7':
            X = _N(s[1]); NN = _N(s[2:])
            V[X] += NN; V[X] %= 256
            PC += 2
        elif s[0] == '8':
            X = _N(s[1]); Y = _N(s[2])
            if s[3] == '0':
                V[X] = V[Y]
            elif s[3] == '1':
                V[X] |= V[Y]
            elif s[3] == '2':
                V[X] &= V[Y]
            elif s[3] == '3':
                V[X] ^= V[Y]
            elif s[3] == '4':
                V[X] += V[Y]
                if V[X] >= 256: V[0xf] = 1
                V[X] %= 256
            elif s[3] == '5':
                V[X] -= V[Y]
                if V[X] >= 0: V[0xf] = 1
                V[X] %= 256
            elif s[3] == '6':
                V[0xf] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) & 0x1
                V[X] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) >> 1
            elif s[3] == '7':
                V[X] = V[Y] - V[X]
                if V[X] >= 0: V[0xf] = 1
                V[X] %= 256
            elif s[3] == 'E':
                V[0xf] = ((V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) & 0x80) >> 7
                V[X] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) << 1
                V[X] %= 256
            PC += 2
        elif s[0] == '9':
            X = _N(s[1]); Y = _N(s[2])
            if V[X] != V[Y]: PC += 2
            PC += 2
        elif s[0] == 'A':
            NNN = _N(s[1:])
            I = NNN
            PC += 2
        elif s[0] == 'B':
            NNN = _N(s[1:])
            PC = NNN + V[0]
        elif s[0] == 'C':
            X = _N(s[1]); NN = _N(s[2:])
            V[X] = math.floor(random.random()*256) & NN
            PC += 2
        elif s[0] == 'D':
            X = _N(s[1]); Y = _N(s[2]); N = _N(s[3])
            draw_sprite(V[X], V[Y], N)
            PC += 2
        elif s[0] == 'E':
            X = _N(s[1])
            if s[2:] == '9E':
                if V[X] in KEY_BUFFER and KEY_BUFFER[V[X]]: PC += 2
                PC += 2
            elif s[2:] == 'A1':
                if V[X] not in KEY_BUFFER or not KEY_BUFFER[V[X]]: PC += 2
                PC += 2
            else:
                print(f'Unsupported instr {s}')
                PC += 2
        elif s[0] == 'F':
            X = _N(s[1])
            if s[2:] == '07':
                # V[X] = DELAY
                TIMED_COMMAND_QUEUE.put_nowait(('G_DELAY', V[X]))
                V[X] = NOTIFY_QUEUE.get()                
            elif s[2:] == '0A':
                WAITKEY = True
                WAITKEY_TARGET = X
            elif s[2:] == '15':
                # DELAY = V[X]
                TIMED_COMMAND_QUEUE.put_nowait(('S_DELAY', V[X]))
            elif s[2:] == '18':
                # SOUND = V[X]
                TIMED_COMMAND_QUEUE.put_nowait(('S_SOUND', V[X]))
            elif s[2:] == '1E':
                I += V[X]
            elif s[2:] == '29':
                I = FONT_BASE + (V[X]%0x10) * 5
            elif s[2:] == '33':
                store_bcd(X)
            elif s[2:] == '55':
                for z in range(X+1):
                    MEM[I+z] = V[z]
                if not SCHIP_COMPATIBLE_FLAG:
                    I = I + X + 1; I %= 4096
            elif s[2:] == '65':
                for z in range(X+1):
                    V[z] = MEM[I+z]
                if not SCHIP_COMPATIBLE_FLAG:
                    I = I + X + 1; I %= 4096
            PC += 2
        

def draw_sprite(X: int, Y: int, N: int):
    X %= 0x40; Y %= 0x20
    turned_off = False
    for i in range(N):
        b = f'{MEM[I+i]:08b}'
        for x in range(X, min(0x40, X+8)):
            y = Y+i; y %= 0x20
            j = x-X
            prev = SCREEN[y*64+x]
            SCREEN[y*64+x] ^= int(b[j])
            current = SCREEN[y*64+x]
            if prev == 1 and current == 0: turned_off = True
            canvas_main.itemconfigure(y*64+x+1,
                fill='white' if current else 'black',
                outline='white' if current else 'black',
            )
            
    root.update()
    V[0xf] = int(turned_off)

def store_bcd(X: int):
    x = V[X]
    a = x // 100; b = (x % 100) // 10; c = x % 10
    MEM[I] = a; MEM[I+1] = b; MEM[I+2] = c

KEYMAP = {
    '1': 1,
    '2': 2,
    '3': 3,
    '4': 0xc,
    'q': 4,
    'w': 5,
    'e': 6,
    'r': 0xd,
    'a': 7,
    's': 8,
    'd': 9,
    'f': 0xe,
    'z': 0xa,
    'x': 0,
    'c': 0xb,
    'v': 0xf,
}

def handle_key_down(e):
    global WAITKEY
    if e.keysym == 'minus':
        TIMED_COMMAND_QUEUE.put_nowait(('SPEED-', None))
    elif e.keysym == 'equal':
        TIMED_COMMAND_QUEUE.put_nowait(('SPEED+', None))
    elif e.keysym in KEYMAP:
        KEY_BUFFER[KEYMAP[e.keysym]] = True
        if WAITKEY:
            print(WAITKEY_TARGET, KEYMAP[e.keysym])
            V[WAITKEY_TARGET] = KEYMAP[e.keysym]
            WAITKEY = False

def handle_key_up(e):
    if e.keysym in KEYMAP:
        KEY_BUFFER[KEYMAP[e.keysym]] = False

def load_rom(p: str):
    with open(p, 'rb') as f:
        data = f.read()
    data_len = len(data)
    if 0x200+data_len > 0xfff:
        print(f'WARNING: data is {data_len} bytes, more than allowed {4096-0x200} bytes.')
    end_mem = min(4096, 0x200+data_len)
    print(f'Loading from 0x200 to 0x{end_mem:03X}')
    for i in range(data_len):
        MEM[0x200+i] = data[i]

def handle_destroy(e):
    TIMED_COMMAND_QUEUE.put_nowait(('END', None))
    NOTIFY_QUEUE.put_nowait('END')
    RUNNING = False

root.bind('<Key>', handle_key_down)
root.bind('<KeyRelease>', handle_key_up)
root.bind('<Destroy>', handle_destroy)

def timed_thread():
    SPEED_FACTOR = 45
    DELAY = 0
    SOUND = 0
    while True:
        try:
            # t = 'G_DELAY' | 'S_DELAY' | 'S_SOUND' | 'END'
            # v is None if t is 'G_DELAY' or 'END'.
            t, v = TIMED_COMMAND_QUEUE.get_nowait()
            if t == 'G_DELAY':
                NOTIFY_QUEUE.put_nowait(DELAY)
            elif t == 'S_DELAY':
                DELAY = v
            elif t == 'S_SOUND':
                SOUND = v
            elif t == 'END':
                break
            elif t == 'SPEED-':
                SPEED_FACTOR -= 10
                if SPEED_FACTOR < 10:
                    SPEED_FACTOR = 10
            elif t == 'SPEED+':
                SPEED_FACTOR += 10
        except:
            pass
        finally:
            time.sleep(1/SPEED_FACTOR)
            if DELAY > 0: DELAY -= 1
            if SOUND > 0: SOUND -= 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CHIP-8 Emulator.')
    parser.add_argument('file',
        type=str,
    )
    parser.add_argument('--debug',
        default=False,
        action='store_true',
    )
    parser.add_argument('--schip-compatible',
        default=False,
        action='store_true'
    )
    cmd = parser.parse_args(sys.argv[1:])
    load_rom(cmd.file)
    new_title = 'CHIP-8'
    if cmd.schip_compatible:
        SCHIP_COMPATIBLE_FLAG = True
        new_title += ' [S-Chip Semantics Compatible]'
    if cmd.debug:
        DEBUG_FLAG = True
        new_title += ' [Debug mode]'
    root.title(new_title)
    TIMED_THREAD = threading.Thread(
        target=timed_thread,
    )
    TIMED_THREAD.start()
    exec()
