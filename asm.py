# CHIP-8 Assembler.
#     @ORG
#     #LABEL
#     ;COMMENT
#     $DATA

import re
import sys
import argparse


REGEX_CMD = re.compile('(RET|JMP(?:V0)?|IF_(?:N?EQ|KEY|NOTKEY)|CALL|CLEAR_SCREEN|JMP|LD[IR]?|ADDC?|X?OR|AND|SUB[C2]|SH[LR]|STR|BCD|CHAR|GET_DELAY|SET_(?:DELAY|SOUND)|WAITKEY|RANDOM|DRAW)',
    flags=re.IGNORECASE
)
REGEX_V = re.compile('[vV]([0-9a-fA-F])')
REGEX_REG = re.compile('[vV]([0-9a-fA-F])|([iI])')
ORG = None
LABEL_DICT = {}

def _N(s: str) -> int:
    r = 0
    for i in s:
        r *= 16
        if '0' <= i <= '9': r += ord(i) - ord('0')
        elif 'a' <= i <= 'f': r += ord(i) - ord('a') + 10
        elif 'A' <= i <= 'F': r += ord(i) - ord('A') + 10
    return r

def _int(s: str) -> int:
    return int(s.strip(),
        16 if s.startswith('0x')
        else 2 if s.startswith('0b')
        else 8 if s.startswith('0o')
        else 10
    )

def compile_source(s: str):
    global ORG
    res = []
    current_pos = 0
    cmd_list = s.split('\n')
    for _line, cmd in enumerate(cmd_list):
        cmd = cmd.strip()
        if not cmd: continue
        elif cmd[0] == ';': continue
        elif cmd[0] == '@':
            ORG = _N(cmd[1:])
            current_pos = ORG
        elif cmd[0] == '#':
            lbl_name = cmd[1:].strip()
            if lbl_name in LABEL_DICT:
                print(f'(L{_line+1}) Duplicated label {lbl_name}')
                return b''
            LABEL_DICT[lbl_name] = current_pos
        elif cmd[0] == '$':
            data_source = cmd[1:].strip()
            if data_source:
                current_pos += len(data_source.split(','))
        else:
            current_pos += 2
    
    for _line, cmd in enumerate(cmd_list):
        cmd = cmd.strip()
        if not cmd: continue
        elif cmd[0] in ';@#': continue
        elif cmd[0] == '$':
            data_source = cmd[1:].strip().split(',')
            data_res = []
            for d in data_source:
                d = d.strip()
                data_res.append(_int(d))
            res.append(bytes(data_res))
        else:
            z = REGEX_CMD.match(cmd)
            if not z: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
            zz = z[1].upper()
            
            if zz == 'CLEAR_SCREEN': res.append(b'\x00\xe0')
            elif zz == 'RET': res.append(b'\x00\xee')
            elif zz == 'JMP':
                target = cmd[z.span()[1]:].strip()
                if target.startswith('#'):
                    target_label = target[1:].strip()
                    if target_label not in LABEL_DICT:
                        print(f'(L{_line+1}) Undefined label {target_label}')
                        continue
                    n = LABEL_DICT[target_label]&0xfff
                else:
                    n = _int(cmd[z.span()[1]:].strip())&0xfff
                nnn_firstpart = (n >> 8) | 0x10
                nnn_secondpart = n & 0xff
                res.append(bytes([nnn_firstpart, nnn_secondpart]))
            elif zz == 'CALL':
                target = cmd[z.span()[1]:].strip()
                if target.startswith('#'):
                    target_label = target[1:].strip()
                    if target_label not in LABEL_DICT:
                        print(f'(L{_line+1}) Undefined label {target_label}')
                        continue
                    n = LABEL_DICT[target_label]&0xfff
                else:
                    n = _int(cmd[z.span()[1]:].strip())&0xfff
                nnn_firstpart = (n >> 8) | 0x20
                nnn_secondpart = n & 0xff
                res.append(bytes([nnn_firstpart, nnn_secondpart]))
            elif zz == 'IF_EQ':
                arg_raw = cmd[z.span()[1]:]
                arg_list = [i.strip() for i in arg_raw.strip().split(',')]
                if len(arg_list) != 2:
                    print(f'(L{_line+1}) Unsupported instruction: {cmd}')
                    continue
                m = REGEX_V.match(arg_list[0])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                l = m[1]
                m = REGEX_V.match(arg_list[1])
                r = m[1] if m else _int(arg_list[1])
                res.append(bytes([
                    int(l,16)|(0x90 if type(r) is str else 0x40),
                    _int(r)<<4 if type(r) is str else r
                ]))
            elif zz == 'IF_NEQ':
                arg_raw = cmd[z.span()[1]:]
                arg_list = [i.strip() for i in arg_raw.strip().split(',')]
                if len(arg_list) != 2:
                    print(f'(L{_line+1}) Unsupported instruction: {cmd}')
                    continue
                m = REGEX_V.match(arg_list[0])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                l = m[1]
                m = REGEX_V.match(arg_list[1])
                r = m[1] if m else _int(arg_list[1])
                res.append(bytes([
                    int(l,16)|(0x50 if type(r) is str else 0x30),
                    _int(r)<<4 if type(r) is str else r
                ]))
            elif zz == 'LD':
                arg_raw = cmd[z.span()[1]:]
                arg_list = [i.strip() for i in arg_raw.strip().split(',')]
                if len(arg_list) != 2:
                    print(f'(L{_line+1}) Unsupported instruction: {cmd}')
                    continue
                m = REGEX_V.match(arg_list[0])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                l = m[1]
                m = REGEX_V.match(arg_list[1])
                r = m[1] if m else _int(arg_list[1])
                res.append(bytes([
                    int(l,16)|(0x80 if type(r) is str else 0x60),
                    _int(r)<<4 if type(r) is str else r
                ]))
            elif zz == 'ADD':
                arg_raw = cmd[z.span()[1]:]
                arg_list = [i.strip() for i in arg_raw.strip().split(',')]
                if len(arg_list) != 2: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                if arg_list[0].upper() == 'I':
                    m = REGEX_V.match(arg_list[1])
                    if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                    res.append(bytes([int(m[1],16)|0xf0, 0x1e]))
                else:
                    m = REGEX_V.match(arg_list[0])
                    if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                    res.append(bytes([int(m[1], 16)|0x70, _int(arg_list[1])]))
            elif zz in ['OR', 'AND', 'XOR', 'ADDC', 'SUBC', 'SHR', 'SUB2', 'SHL']:
                arg_raw = cmd[z.span()[1]:]
                arg_list = [i.strip() for i in arg_raw.strip().split(',')]
                if len(arg_list) != 2: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                m = REGEX_V.match(arg_list[0])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                l = int(m[1],16)&0x80
                m = REGEX_V.match(arg_list[1])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                r = (_int(m[1])<<4)|{
                    'OR': 0x01,
                    'AND': 0x02,
                    'XOR': 0x03,
                    'ADDC': 0x04,
                    'SUBC': 0x05,
                    'SHR': 0x06,
                    'SUB2': 0x07,
                    'SHL': 0x0e
                }[zz]
                res.append(bytes([l, r]))
            elif zz == 'LDI':
                target = cmd[z.span()[1]:].strip()
                if target.startswith('#'):
                    target_label = target[1:].strip()
                    if target_label not in LABEL_DICT:
                        print(f'(L{_line+1}) Undefined label {target_label}')
                        continue
                    n = LABEL_DICT[target_label]&0xfff
                else:
                    n = _int(cmd[z.span()[1]:].strip())&0xfff
                nnn_firstpart = (n >> 8) | 0xa0
                nnn_secondpart = n & 0xff
                res.append(bytes([nnn_firstpart, nnn_secondpart]))
            elif zz == 'JMPV0':
                target = cmd[z.span()[1]:].strip()
                if target.startswith('#'):
                    target_label = target[1:].strip()
                    if target_label not in LABEL_DICT:
                        print(f'(L{_line+1}) Undefined label {target_label}')
                        continue
                    n = LABEL_DICT[target_label]&0xfff
                else:
                    n = _int(cmd[z.span()[1]:].strip())&0xfff
                nnn_firstpart = (n >> 8) | 0xb0
                nnn_secondpart = n & 0xff
                res.append(bytes([nnn_firstpart, nnn_secondpart]))
            elif zz == 'RANDOM':
                arg_raw = cmd[z.span()[1]:]
                arg_list = arg_raw.strip().split(',')
                if len(arg_list) != 2:
                    print(f'(L{_line+1}) Unsupported instruction: {cmd}')
                    continue
                m = REGEX_V.match(arg_list[0])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[1], 16)|0xc0
                res.append(bytes([vn, _int(arg_list[1])]))
            elif zz == 'DRAW':
                arg_raw = cmd[z.span()[1]:]
                arg_list = arg_raw.strip().split(',')
                if len(arg_list) != 3:
                    print(f'(L{_line+1}) Unsupported instruction: {cmd}')
                    continue
                m = REGEX_V.findall(arg_raw)
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xd0
                vn2 = int(m[1], 16) << 4
                n = _int(arg_list[2])
                res.append(bytes([vn, vn2|n]))
            elif zz == 'IF_NOTKEY':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xe0
                res.append(bytes([vn,0x9e]))
            elif zz == 'IF_KEY':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xe0
                res.append(bytes([vn,0xa1]))
            elif zz == 'GET_DELAY':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x07]))
            elif zz == 'WAITKEY':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x0a]))
            elif zz == 'SET_DELAY':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x15]))
            elif zz == 'SET_SOUND':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x18]))
            elif zz == 'CHAR':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x29]))
            elif zz == 'BCD':
                m = REGEX_V.findall(cmd[z.span()[1]:])
                if not m: print(f'(L{_line+1}) Unsupported instruction: {cmd}'); continue
                vn = int(m[0], 16)|0xf0
                res.append(bytes([vn,0x33]))
            elif zz == 'STR':
                n = cmd[z.span()[1]:].strip()
                vn = _int(n)|0xf0
                res.append(bytes([vn,0x55]))
            elif zz == 'LDR':
                n = cmd[z.span()[1]:].strip()
                vn = _int(n)|0xf0
                res.append(bytes([vn,0x65]))
                


    return b''.join(res)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CHIP-8 ROM Assembler.')
    parser.add_argument('file',
        type=str,
    )
    cmd = parser.parse_args(sys.argv[1:])
    p = cmd.file
    with open(p, 'r') as f:
        source = f.read()
    
    res = compile_source(source)

    data_len = len(res)
    if 0x200+data_len > 0xfff:
        res.append(f'# WARNING: data is {data_len} bytes, more than allowed {4096-0x200} bytes.')

    with open(f'{p}.ch8', 'wb') as f:
        f.write(res)
