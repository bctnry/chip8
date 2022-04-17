import sys
import ctypes
import argparse
import math
import random
import sdl2
import sdl2.ext
import time
from dataclasses import dataclass
from typing import Callable, Any, Union

CELL_SIZE = 10
WINDOW_WIDTH = 64 * CELL_SIZE
WINDOW_HEIGHT = 32 * CELL_SIZE
RENDERER = None
RECT = sdl2.SDL_Rect(x=0, y=0, w=0, h=0)

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

SCHIP_COMPATIBLE_FLAG = False

# init font.
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

@dataclass
class NotificationTimer:
    interval_ms: int
    notification_code: Union[int, None] = None
    window_id: Union[int, None] = None

    def __timer_callback(self, t):
        # SDL_Event is a union so it should be done like in C.
        # in C you do it like:
        #     SDL_Event event;
        #     SDL_memset(&event, 0, sizeof(event));
        #     event.type = myEventType;
        #     event.user.code = my_event_code;
        #     event.user.data1 = significant_data;
        #     event.user.data2 = 0;
        # due to how ctypes work in python this would be a little
        # bit weird in python.
        wrapper_event = sdl2.events.SDL_Event()
        event = sdl2.events.SDL_UserEvent(
            type=self.event,
            code=self.notification_code or 1,
        )
        if self.window_id is not None:
            event.windowID = self.window_id
        wrapper_event.type = self.event
        wrapper_event.user = event
        
        sdl2.SDL_PushEvent(wrapper_event)
        return t

    def __post_init__(self):
        self.event = sdl2.SDL_RegisterEvents(1)
        if self.event == 0xffffffff:
            raise Exception(f'No more event to register!')
        self.__timer_handle = None
        self.__c_timer_callback = sdl2.timer.SDL_TimerCallback(lambda x, _: self.__timer_callback(x))

    def start(self):
        if self.__timer_handle is not None:
            sdl2.timer.SDL_RemoveTimer(self.__timer_handle)
        self.__timer_handle = sdl2.timer.SDL_AddTimer(
            self.interval_ms,
            self.__c_timer_callback,
            None
        )
    
    def stop(self):
        if self.__timer_handle is not None:
            sdl2.timer.SDL_RemoveTimer(self.__timer_handle)
        self.__timer_handle = None

def step():
    global I, SP, DELAY, SOUND, PC, WAITKEY, WAITKEY_TARGET, RUNNING
    if WAITKEY:
        return
    # instr are 2-bytes long, big endian.
    instr_1 = MEM[PC]; instr_2 = MEM[PC+1]
    instr = (instr_1<<8)|instr_2

    first_digit = (instr_1&0xf0)>>4
    
    if first_digit == 0:
        if instr == 0x00e0:
            for i in range(64 * 32): SCREEN[i] = False
            sdl2.SDL_SetRenderDrawColor(RENDERER, 0, 0, 0, 0xff)
            sdl2.SDL_RenderClear(RENDERER)
            sdl2.SDL_RenderPresent(RENDERER)
            PC += 2
        elif instr == 0x00ee:
            SP -= 1
            if SP < 0: raise Error('stack underflow')
            PC = STK[SP]
        else:
            print(f'Unsupported instruction {instr:04X}')
            raise Exception()
            PC += 2
    elif first_digit == 1:
        NNN = instr&0x0fff
        PC = NNN
    elif first_digit == 2:
        NNN = instr&0x0fff
        STK[SP] = PC+2
        SP += 1
        PC = NNN
    elif first_digit == 3:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        if V[X] == NN: PC += 2
        PC += 2
    elif first_digit == 4:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        if V[X] != NN: PC += 2
        PC += 2
    elif first_digit == 5:
        X = (instr&0x0f00)>>8; Y = (instr&0x00f0)>>4
        if V[X] == V[Y]: PC += 2
        PC += 2
    elif first_digit == 6:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        V[X] = NN; V[X] %= 256
        PC += 2
    elif first_digit == 7:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        V[X] += NN; V[X] %= 256
        PC += 2
    elif first_digit == 8:
        X = (instr&0x0f00)>>8; Y = (instr&0x00f0)>>4
        S3 = (instr&0x000f)
        if S3 == 0:
            V[X] = V[Y]
        elif S3 == 1:
            V[X] |= V[Y]
        elif S3 == 2:
            V[X] &= V[Y]
        elif S3 == 3:
            V[X] ^= V[Y]
        elif S3 == 4:
            V[X] += V[Y]
            if V[X] >= 256: V[0xf] = 1
            V[X] %= 256
        elif S3 == 5:
            V[X] -= V[Y]
            if V[X] >= 0: V[0xf] = 1
            V[X] %= 256
        elif S3 == 6:
            V[0xf] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) & 0x1
            V[X] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) >> 1
        elif S3 == 7:
            V[X] = V[Y] - V[X]
            if V[X] >= 0: V[0xf] = 1
            V[X] %= 256
        elif S3 == 0xe:
            V[0xf] = ((V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) & 0x80) >> 7
            V[X] = (V[X] if SCHIP_COMPATIBLE_FLAG else V[Y]) << 1
            V[X] %= 256
        PC += 2
    elif first_digit == 9:
        X = (instr&0x0f00)>>8; Y = (instr&0x00f0)>>4
        if V[X] != V[Y]: PC += 2
        PC += 2
    elif first_digit == 0x0a:
        NNN = instr&0x0fff
        I = NNN
        PC += 2
    elif first_digit == 0x0b:
        NNN = instr&0x0fff
        PC = NNN + V[0]
    elif first_digit == 0x0c:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        V[X] = math.floor(random.random()*256) & NN
        PC += 2
    elif first_digit == 0x0d:
        X = (instr&0x0f00)>>8; Y = (instr&0x00f0)>>4; N = instr&0x000f
        draw_sprite(V[X], V[Y], N)
        PC += 2
    elif first_digit == 0x0e:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        if NN == 0x9e:
            if V[X] in KEY_BUFFER and KEY_BUFFER[V[X]]: PC += 2
            PC += 2
        elif NN == 0xa1:
            if V[X] not in KEY_BUFFER or not KEY_BUFFER[V[X]]: PC += 2
            PC += 2
        else:
            print(f'Unsupported instr {instr:04X}')
            PC += 2
    elif first_digit == 0x0f:
        X = (instr&0x0f00)>>8; NN = instr&0x00ff
        if NN == 0x07:
            V[X] = DELAY
        elif NN == 0x0a:
            WAITKEY = True
            WAITKEY_TARGET = X
        elif NN == 0x15:
            DELAY = V[X]
        elif NN == 0x18:
            SOUND = V[X]
        elif NN == 0x1e:
            I += V[X]
        elif NN == 0x29:
            I = FONT_BASE + (V[X]%0x10) * 5
        elif NN == 0x33:
            store_bcd(X)
        elif NN == 0x55:
            for z in range(X+1):
                MEM[I+z] = V[z]
            if not SCHIP_COMPATIBLE_FLAG:
                I = I + X + 1; I %= 4096
        elif NN == 0x65:
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
            sdl2.SDL_SetRenderDrawColor(RENDERER,
                0xff if current else 0,
                0xff if current else 0,
                0xff if current else 0,
                0xff
            )
            RECT.x = x * CELL_SIZE
            RECT.y = y * CELL_SIZE
            RECT.w = CELL_SIZE
            RECT.h = CELL_SIZE
            sdl2.SDL_RenderFillRect(RENDERER, RECT)
    sdl2.SDL_RenderPresent(RENDERER)
    V[0xf] = int(turned_off)


def store_bcd(X: int):
    x = V[X]
    a = x // 100; b = (x % 100) // 10; c = x % 10
    MEM[I] = a; MEM[I+1] = b; MEM[I+2] = c


KEYMAP = {
    sdl2.SDL_SCANCODE_1: 1,
    sdl2.SDL_SCANCODE_2: 2,
    sdl2.SDL_SCANCODE_3: 3,
    sdl2.SDL_SCANCODE_4: 0xc,
    sdl2.SDL_SCANCODE_Q: 4,
    sdl2.SDL_SCANCODE_W: 5,
    sdl2.SDL_SCANCODE_E: 6,
    sdl2.SDL_SCANCODE_R: 0xd,
    sdl2.SDL_SCANCODE_A: 7,
    sdl2.SDL_SCANCODE_S: 8,
    sdl2.SDL_SCANCODE_D: 9,
    sdl2.SDL_SCANCODE_F: 0xe,
    sdl2.SDL_SCANCODE_Z: 0xa,
    sdl2.SDL_SCANCODE_X: 0,
    sdl2.SDL_SCANCODE_C: 0xb,
    sdl2.SDL_SCANCODE_V: 0xf,
}


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

def main(title: str):
    global RENDERER, DELAY, SOUND, WAITKEY, WAITKEY_TARGET
    sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO)
    window = sdl2.SDL_CreateWindow(
        title.encode('utf-8'),
        sdl2.SDL_WINDOWPOS_CENTERED, sdl2.SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH, WINDOW_HEIGHT,
        sdl2.SDL_WINDOW_SHOWN
    )
    RENDERER = sdl2.SDL_CreateRenderer(
        window,
        -1,
        sdl2.SDL_RENDERER_SOFTWARE
    )
    TIMED_TIMER = NotificationTimer(
        interval_ms=int(1000/60),
    )
    running = True
    event = sdl2.SDL_Event()
    TIMED_TIMER.start()
    while running:
        event_list = sdl2.ext.get_events()
        for event in event_list:
            if event.type == sdl2.SDL_QUIT:
                break
            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.scancode in KEYMAP:
                    KEY_BUFFER[KEYMAP[event.key.keysym.scancode]] = True
                    if WAITKEY:
                        V[WAITKEY_TARGET] = KEYMAP[event.key.keysym.scancode]
                        WAITKEY = False
            elif event.type == sdl2.SDL_KEYUP:
                if event.key.keysym.scancode in KEYMAP:
                    KEY_BUFFER[KEYMAP[event.key.keysym.scancode]] = False

            elif event.type == TIMED_TIMER.event:
                if DELAY > 0: DELAY -= 1
                if SOUND > 0: SOUND -= 1

            step()
            sdl2.SDL_RenderPresent(RENDERER)

    # TIMED_TIMER.stop()
    sdl2.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CHIP-8 Emulator.')
    parser.add_argument('file',
        type=str,
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
    main(new_title)
