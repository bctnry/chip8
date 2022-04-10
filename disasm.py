import sys
import argparse

def disasm_s(s: str):
    if not s: return ''
    elif s == '00E0': return 'CLEAR_SCREEN'
    elif s == '00EE': return 'RET'
    elif s[0] == '1': return f'JMP 0x{s[1:]}'
    elif s[0] == '2': return f'CALL 0x{s[1:]}'
    elif s[0] == '3': return f'IF_NEQ V{s[1]},0x{s[2:]}'
    elif s[0] == '4': return f'IF_EQ V{s[1]},0x{s[2:]}'
    elif s[0] == '5': return f'IF_NEQ V{s[1]},V{s[1]}'
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
    elif s[0] == '9': return f'IF_EQ V{s[1]},V{s[2]}'
    elif s[0] == 'A': return f'LDI 0x{s[1:]}'
    elif s[0] == 'B': return f'JMPV0 0x{s[1:]}'
    elif s[0] == 'C': return f'RANDOM V{s[1]},0x{s[2:]}'
    elif s[0] == 'D': return f'DRAW V{s[1]},V{s[2]},0x{s[3]}'
    elif s[0] == 'E':
        if s[2:] == '9E': return f'IF_NOTKEY V{s[1]}'
        elif s[2:] == 'A1': return f'IF_KEY V{s[1]}'
    elif s[0] == 'F':
        if s[2:] == '07': return f'GET_DELAY V{s[1]}'
        elif s[2:] == '0A': return f'WAITKEY V{s[1]}'
        elif s[2:] == '15': return f'SET_DELAY V{s[1]}'
        elif s[2:] == '18': return f'SET_SOUND V{s[1]}'
        elif s[2:] == '1E': return f'ADD I,V{s[1]}'
        elif s[2:] == '29': return f'CHAR V{s[1]}'
        elif s[2:] == '33': return f'BCD V{s[1]}'
        elif s[2:] == '55': return f'STR 0x{s[1]}'
        elif s[2:] == '65': return f'LDR 0x{s[1]}'
    return None

def disasm_octo(s: str):
    if not s: return ''
    elif s == '00E0': return 'clear'
    elif s == '00EE': return 'return'
    elif s[0] == '1': return f'jump {s[1:]}'
    elif s[0] == '2': return f'{s[1:]}'
    elif s[0] == '3': return f'if v{s[1]} != {s[2:]} then'
    elif s[0] == '4': return f'if v{s[1]} == {s[2:]} then'
    elif s[0] == '5': return f'if v{s[1]} != v{s[1]} then'
    elif s[0] == '6': return f'v{s[1]} := {s[2:]}'
    elif s[0] == '7': return f'v{s[1]} += {s[2:]}'
    elif s[0] == '8':
        if s[3] == '0': return f'v{s[1]} := v{s[2]}'
        elif s[3] == '1': return f'v{s[1]} |= v{s[2]}'
        elif s[3] == '2': return f'v{s[1]} &= v{s[2]}'
        elif s[3] == '3': return f'v{s[1]} |= v{s[2]}'
        elif s[3] == '4': return f'v{s[1]} &= v{s[2]}'
        elif s[3] == '5': return f'v{s[1]} -= v{s[2]}'
        elif s[3] == '6': return f'v{s[1]} >>= v{s[2]}'
        elif s[3] == '7': return f'v{s[1]} =- v{s[2]}'
        elif s[3] == 'E': return f'v{s[1]} <<= v{s[2]}'
    elif s[0] == '9': return f'if v{s[1]} == v{s[2]} then'
    elif s[0] == 'A': return f'i := {s[1:]}'
    elif s[0] == 'B': return f'jump0 {s[1:]}'
    elif s[0] == 'C': return f'v{s[1]} := random {s[2:]}'
    elif s[0] == 'D': return f'sprite v{s[1]} v{s[2]} {s[3]}'
    elif s[0] == 'E':
        if s[2:] == '9E': return f'if v{s[1]} -key then'
        elif s[2:] == 'A1': return f'if v{s[1]} key then'
    elif s[0] == 'F':
        if s[2:] == '07': return f'v{s[1]} := delay'
        elif s[2:] == '0A': return f'v{s[1]} := key'
        elif s[2:] == '15': return f'delay := v{s[1]}'
        elif s[2:] == '18': return f'sound := v{s[1]}'
        elif s[2:] == '1E': return f'i += v{s[1]}'
        elif s[2:] == '29': return f'i := hex v{s[1]}'
        elif s[2:] == '33': return f'bcd v{s[1]}'
        elif s[2:] == '55': return f'save v{s[1]}'
        elif s[2:] == '65': return f'load v{s[1]}'
    return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CHIP-8 ROM Disassembler.')
    parser.add_argument('file',
        type=str,
    )
    parser.add_argument('--octo',
        action='store_true',
        help='Use Octo syntax',
    )
    parser.add_argument('--no-addr',
        action='store_true',
        help='Do not output address.',
    )
    parser.add_argument('--no-opcode',
        action='store_true',
        help='Do not output CHIP-8 opcode.',
    )
    parser.add_argument('--force-opcode',
        action='store_true',
        help='Assume all data are opcodes regardless of validity.'
    )
    cmd = parser.parse_args(sys.argv[1:])
    p = cmd.file
    with open(p, 'rb') as f:
        data = f.read()
    data_len = len(data)
    res = []
    if 0x200+data_len > 0xfff:
        res.append(f'# WARNING: data is {data_len} bytes, more than allowed {4096-0x200} bytes.')
    res.append('')

    i = 0x200
    while i-0x200 < data_len:
        s = f'{data[i-0x200]:02X}{data[i+1-0x200]:02X}'
        disasm_res = (disasm_octo if cmd.octo else disasm_s)(s)
        if disasm_res is None and not cmd.force_opcode:
            res.append(
                ('' if cmd.no_addr else f'0x{i:03X}    ')
                + ('' if cmd.no_opcode else f'{data[i-0x200]:02X}    ')
                + f'$0x{data[i-0x200]:02X}'
            )
            i += 1
        else:
            disasm_res = disasm_res if disasm_res else '<UNSPECIFIED>'
            res.append(
                ('' if cmd.no_addr else f'0x{i:03X}    ')
                + ('' if cmd.no_opcode else f'{s}  ')
                + f'{disasm_res}'
            )
            i += 2

    res_text = '\n'.join(res)
    with open(f'{p}.lst', 'w') as f:
        f.write(res_text)
