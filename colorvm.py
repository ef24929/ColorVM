import argparse
import pathlib

from itertools import zip_longest
from PIL import Image
from rich.style import Style
from rich.table import Table
from rich.console import Console
from rich.text import Text

#
# Pollock image format definition
# First pixel of the first cell: [major version, minor version, cell size]
# First pixel of the second cell: [tnol % 16777216, tnol % 65536, tnol % 256], where tnol = total number of lines - 2
#  We do not need to count the first two elements, since they are the meta info
#
# If the number of lines is 0 or 1, we have a vertical image, due to flooring sqrt!
# After acquiring the metadata, any pixel is good from the cell to get the 3 channel instructions (v1.0)
#
# Known issues:
#

#
# Version info
#
V_MAJOR = 1
V_MINOR = 0

#
# VM operating states
#  OVERRUN is when the execution jumps out from the array
#  AWAIT is when a color thread waits for data to arrive to the alpha channel
#
LOADING = 1
RUNNING = 2
AWAIT = 3
HALTED = 4
OVERRUN = 5

#
# Rich styles for different outputs
#
red_style = Style(color="red3", bold=True)
green_style = Style(color="dark_green", bold=True)
blue_style = Style(color="deep_sky_blue4", bold=True)
alpha_style = Style(color="grey70", bold=True)
table_info_style = Style(color="grey85")
debug_style = Style(color="dark_orange", italic=True)
message_style = Style(color="yellow2")
important_style = Style(color="purple3", bold=True)
gendebug_style = Style(color="grey50", italic=True)
console = Console(highlight=False)

# Color styles dictionary
colorstyles: dict[str, Style] = {
    "r": red_style,
    "g": green_style,
    "b": blue_style
}
# Thread state reverse dictionary
statereverse: dict[int, str] = {
    1: "LOADING",
    2: "RUNNING",
    3: "AWAIT",
    4: "HALTED",
    5: "OVERRUN"
}
# The stack of the color threads, alpha (a) is the global communication channel
colorstack: dict[str, list[int]] = {
    'r': [],
    'g': [],
    'b': [],
    'a': []
}
# The code arrays of the color threads
colorcode: dict[str, list[int]] = {
    'r': [],
    'g': [],
    'b': []
}
# The execution states of the color threads
colorstate: dict[str, int] = {
    'r': LOADING,
    'g': LOADING,
    'b': LOADING
}
# The instruction pointers of the color threads
colorip: dict[str, int] = {
    'r': 0,
    'g': 0,
    'b': 0
}
# Statistics for each color thread
colorstat: dict[str, dict[str, int]] = {
    'r': {
        "push": 0,
        "add": 0,
        "sub": 0,
        "mul": 0,
        "div": 0,
        "rem": 0,
        "pop": 0,
        "swap": 0,
        "dup": 0,
        "rot": 0,
        "not": 0,
        "or": 0,
        "and": 0,
        "gt": 0,
        "eq": 0,
        "lt": 0,
        "nop": 0,
        "halt": 0,
        "jmpz": 0,
        "jmpnz": 0,
        "outc": 0,
        "inc": 0,
        "outi": 0,
        "ini": 0,
        "pusha": 0,
        "waita": 0,
        "neg": 0,
        "shl": 0,
        "shr": 0
    },
    'g': {
        "push": 0,
        "add": 0,
        "sub": 0,
        "mul": 0,
        "div": 0,
        "rem": 0,
        "pop": 0,
        "swap": 0,
        "dup": 0,
        "rot": 0,
        "not": 0,
        "or": 0,
        "and": 0,
        "gt": 0,
        "eq": 0,
        "lt": 0,
        "nop": 0,
        "halt": 0,
        "jmpz": 0,
        "jmpnz": 0,
        "outc": 0,
        "inc": 0,
        "outi": 0,
        "ini": 0,
        "pusha": 0,
        "waita": 0,
        "neg": 0,
        "shl": 0,
        "shr": 0
    },
    'b': {
        "push": 0,
        "add": 0,
        "sub": 0,
        "mul": 0,
        "div": 0,
        "rem": 0,
        "pop": 0,
        "swap": 0,
        "dup": 0,
        "rot": 0,
        "not": 0,
        "or": 0,
        "and": 0,
        "gt": 0,
        "eq": 0,
        "lt": 0,
        "nop": 0,
        "halt": 0,
        "jmpz": 0,
        "jmpnz": 0,
        "outc": 0,
        "inc": 0,
        "outi": 0,
        "ini": 0,
        "pusha": 0,
        "waita": 0,
        "neg": 0,
        "shl": 0,
        "shr": 0
    }
}
# The colors
colors = ["r", "g", "b"]
# Wait stack to avoid await race condition
waitstack = []
# The disassembly dictionary
disasmdict: dict[int, str] = {
    0b1000_0000: "add",
    0b1000_0100: "sub",
    0b1000_1000: "mul",
    0b1000_1100: "div",
    0b1001_0000: "rem",
    0b1001_0100: "pop",
    0b1001_1000: "swap",
    0b1001_1100: "dup",
    0b1010_0000: "rot",
    0b1010_0100: "not",
    0b1010_1000: "or",
    0b1010_1100: "and",
    0b1011_0000: "gt",
    0b1011_0100: "eq",
    0b1011_1000: "lt",
    0b1011_1100: "nop",
    0b1100_0000: "halt",
    0b1100_0100: "jmpz",
    0b1100_1000: "jmpnz",
    0b1100_1100: "outc",
    0b1101_0000: "inc",
    0b1101_0100: "outi",
    0b1101_1000: "ini",
    0b1101_1100: "pusha",
    0b1110_0000: "waita",
    0b1110_0100: "neg",
    0b1110_1000: "shl",
    0b1110_1100: "shr"
}

def mesg(instring: str):
    global args
    if args.silent is False:
        console.print(f"INFO: {instring}", style=message_style)


def debuglog(instring: str, linestyle: Style):
    global args
    debug_header = Text()
    debug_header.append("DEBUG: ", style=debug_style)
    debug_header.append(f"{instring}", style=linestyle)
    if args.debug is True:
        console.print(debug_header)


def colorexec(colortoexec: str):
    global args
    if 0 <= colorcode[colortoexec][colorip[colortoexec]] <= 127 :
        debuglog(f"  Instruction: push {str(colorcode[colortoexec][colorip[colortoexec]])}", colorstyles[colortoexec])
        colorstack[colortoexec].append(colorcode[colortoexec][colorip[colortoexec]])
        colorstat[colortoexec]["push"] += 1
    else:
        debuglog(f"  Instruction: {disasmdict.get(colorcode[colortoexec][colorip[colortoexec]])}", colorstyles[colortoexec])
        match colorcode[colortoexec][colorip[colortoexec]]:
            case int(0b1000_0000):
                # add
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(colorstack[colortoexec].pop() + colorstack[colortoexec].pop())
                colorstat[colortoexec]["add"] += 1
            case int(0b1000_0100):
                # sub
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(colorstack[colortoexec].pop() - colorstack[colortoexec].pop())
                colorstat[colortoexec]["sub"] += 1
            case int(0b1000_1000):
                # mul
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(colorstack[colortoexec].pop() * colorstack[colortoexec].pop())
                colorstat[colortoexec]["mul"] += 1
            case int(0b1000_1100):
                # div
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(int(colorstack[colortoexec].pop() // colorstack[colortoexec].pop()))
                colorstat[colortoexec]["div"] += 1
            case int(0b1001_0000):
                # rem
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(int(colorstack[colortoexec].pop() % colorstack[colortoexec].pop()))
                colorstat[colortoexec]["rem"] += 1
            case int(0b1001_0100):
                # pop
                if len(colorstack[colortoexec]) >= 1:
                    _ = colorstack[colortoexec].pop()
                colorstat[colortoexec]["pop"] += 1
            case int(0b1001_1000):
                # swap
                if len(colorstack[colortoexec]) >= 2:
                    a = colorstack[colortoexec].pop()
                    b = colorstack[colortoexec].pop()
                    colorstack[colortoexec].append(a)
                    colorstack[colortoexec].append(b)
                colorstat[colortoexec]["swap"] += 1
            case int(0b1001_1100):
                # dup
                if len(colorstack[colortoexec]) >= 1:
                    a = colorstack[colortoexec].pop()
                    colorstack[colortoexec].append(a)
                    colorstack[colortoexec].append(a)
                colorstat[colortoexec]["dup"] += 1
            case int(0b1010_0000):
                # rot
                if len(colorstack[colortoexec]) >= 1:
                    torot = int(colorstack[colortoexec].pop())
                    if len(colorstack[colortoexec]) >= torot:
                        extract = colorstack[colortoexec].pop()
                        # We pop the last element and insert it into the length-1 (list starts with 0) minus rot-2 (one less element) position
                        colorstack[colortoexec].insert((len(colorstack[colortoexec])-1)-(torot-2), extract)
                colorstat[colortoexec]["rot"] += 1
            case int(0b1010_0100):
                # not
                if len(colorstack[colortoexec]) >= 1:
                    colorstack[colortoexec].append(int(~ colorstack[colortoexec].pop()))
                colorstat[colortoexec]["not"] += 1
            case int(0b1010_1000):
                # or
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(int(colorstack[colortoexec].pop() | colorstack[colortoexec].pop()))
                colorstat[colortoexec]["or"] += 1
            case int(0b1010_1100):
                # and
                if len(colorstack[colortoexec]) >= 2:
                    colorstack[colortoexec].append(int(colorstack[colortoexec].pop() & colorstack[colortoexec].pop()))
                colorstat[colortoexec]["and"] += 1
            case int(0b1011_0000):
                # gt
                if len(colorstack[colortoexec]) >= 2:
                    a = int(colorstack[colortoexec].pop())
                    b = int(colorstack[colortoexec].pop())
                    colorstack[colortoexec].append(1 if a > b else 0)
                colorstat[colortoexec]["gt"] += 1
            case int(0b1011_0100):
                # eq
                if len(colorstack[colortoexec]) >= 2:
                    a = int(colorstack[colortoexec].pop())
                    b = int(colorstack[colortoexec].pop())
                    colorstack[colortoexec].append(1 if a == b else 0)
                colorstat[colortoexec]["eq"] += 1
            case int(0b1011_1000):
                # lt
                if len(colorstack[colortoexec]) >= 2:
                    a = int(colorstack[colortoexec].pop())
                    b = int(colorstack[colortoexec].pop())
                    colorstack[colortoexec].append(1 if a < b else 0)
                colorstat[colortoexec]["lt"] += 1
            case int(0b1100_0100):
                # jmpz
                if len(colorstack[colortoexec]) >= 2:
                    value = int(colorstack[colortoexec].pop())
                    address = int(colorstack[colortoexec].pop())
                    if value == 0:
                        if 0 <= address < size:
                            # The new address should be 1 less, since we are adding 1 to it in the main sequence
                            colorip[colortoexec] = address - 1
                        else:
                            # We already overrun. The new address should be 1 less, then the size, since
                            # we are adding 1 to it in the main sequence, and we should reach size to show state overrun.
                            colorip[colortoexec] = size - 1
                colorstat[colortoexec]["jmpz"] += 1
            case int(0b1100_1000):
                # jmpnz
                if len(colorstack[colortoexec]) >= 2:
                    value = int(colorstack[colortoexec].pop())
                    address = int(colorstack[colortoexec].pop())
                    if value != 0:
                        if 0 <= address < size:
                            # The new address should be 1 less, since we are adding 1 to it in the main sequence
                            colorip[colortoexec] = address - 1
                        else:
                            # We already overrun. The new address should be 1 less, then the size, since
                            # we are adding 1 to it in the main sequence, and we should reach size to show state overrun.
                            colorip[colortoexec] = size - 1
                colorstat[colortoexec]["jmpnz"] += 1
            case int(0b1100_1100):
                # outc
                if len(colorstack[colortoexec]) >= 1:
                    char=str(chr(colorstack[colortoexec].pop()))
                    if char.isascii() is True :
                        print(f"{char}")
                colorstat[colortoexec]["outc"] += 1
            case int(0b1101_0000):
                # inc
                char=input(f"Char input for channel '{colortoexec}': ")
                colorstack[colortoexec].append(ord(char[0]))
                colorstat[colortoexec]["inc"] += 1
            case int(0b1101_0100):
                # outi
                if len(colorstack[colortoexec]) >= 1:
                    number=int(colorstack[colortoexec].pop())
                    print(f"{number}")
                colorstat[colortoexec]["outi"] += 1
            case int(0b1101_1000):
                # ini
                value=input(f"Integer input for channel '{colortoexec}': ")
                if value.isdecimal() is True :
                    colorstack[colortoexec].append(int(value))
                colorstat[colortoexec]["ini"] += 1
            case int(0b1101_1100):
                # pusha
                if len(colorstack[colortoexec]) >= 1:
                    colorstack['a'].append(colorstack[colortoexec].pop())
                colorstat[colortoexec]["pusha"] += 1
            case int(0b1110_0000):
                # waita
                if len(colorstack['a']) >= 1:
                    colorstack[colortoexec].append(colorstack['a'].pop())
                    colorstate[colortoexec] = RUNNING
                else:
                    # We have to stay at the same place, so the new address should be 1 less, since we are adding 1 to it in the main sequence
                    colorstate[colortoexec] = AWAIT
                    waitstack.append(colortoexec)
                    colorip[colortoexec] -= 1
                colorstat[colortoexec]["waita"] += 1
            case int(0b1110_0100):
                # neg
                if len(colorstack[colortoexec]) >= 1:
                    colorstack[colortoexec].append(int(0 - colorstack[colortoexec].pop()))
                colorstat[colortoexec]["neg"] += 1
            case int(0b1110_1000):
                # shl
                if len(colorstack[colortoexec]) >= 2:
                    shiftval = int(colorstack[colortoexec].pop())
                    value = int(colorstack[colortoexec].pop())
                    colorstack[colortoexec].append(int(value << shiftval))
                colorstat[colortoexec]["shl"] += 1
            case int(0b1110_1100):
                # shr
                if len(colorstack[colortoexec]) >= 2:
                    shiftval = int(colorstack[colortoexec].pop())
                    value = int(colorstack[colortoexec].pop())
                    colorstack[colortoexec].append(int(value << shiftval))
                colorstat[colortoexec]["shr"] += 1
            case _:
                mesg(f"Invalid instruction {colorcode[colortoexec][colorip[colortoexec]]} in '{colortoexec}' channel at {colorip[colortoexec]} position for ColorVM v{V_MAJOR}.{V_MINOR}.\nHalting channel '{colortoexec}'.")
                colorstate[colortoexec] = HALTED
    if args.debug is True:
        stacktable = Table(title="Stack dump")
        stacktable.add_column("Position", justify="left", style=table_info_style)
        stacktable.add_column("r", justify="right", style=red_style)
        stacktable.add_column("g", justify="right", style=green_style)
        stacktable.add_column("b", justify="right", style=blue_style)
        stacktable.add_column("a", justify="right", style=alpha_style)
        for pos, sval in enumerate(zip_longest(colorstack["r"], colorstack["g"], colorstack["b"], colorstack["a"], fillvalue='-')):
            stacktable.add_row(f"{pos}", f"{sval[0]}", f"{sval[1]}", f"{sval[2]}", f"{sval[3]}")
        debuglog(f"", colorstyles[colortoexec])
        console.print(stacktable)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    parser.add_argument('-b', '--bytedump', action='store_true', default=False, help='no execution, just dumping the bytearray in text')
    parser.add_argument('-d', '--disasm', action='store_true', default=False, help='no execution, just disassembling the program')
    parser.add_argument('-s', '--silent', action='store_true', default=False, help='silent run, no warnings or errors')
    parser.add_argument('-t', '--statistics', action='store_true', default=False, help='display execution statistics after the termination of the VM')
    parser.add_argument('-g', '--debug', action='store_true', default=False, help='provide detailed debug output')
    args = parser.parse_args()

    path = pathlib.Path(args.filename)

    if path.exists() and path.is_file():
        img = Image.open(path, mode='r')
        imgxsize = img.size[0]
        imgysize = img.size[1]
        (majorver, minorver, cellsize) = img.getpixel((0, 0))
        debuglog(f"Version: {majorver}.{minorver}, cellsize: {cellsize}", important_style)
        if (majorver > V_MAJOR) or (majorver == V_MAJOR and minorver > V_MINOR):
            mesg(f"Invalid version {majorver}.{minorver}, maximum supported: {V_MAJOR}.{V_MINOR}")
            exit()
        if imgxsize == cellsize:
            (size3, size2, size1) = img.getpixel((0, cellsize))
        else:
            (size3, size2, size1) = img.getpixel((cellsize, 0))
        size = size3 * 256 * 256 + size2 * 256 + size1
        debuglog(f"Program size: {size}", important_style)
        i = 1
        match size:
            case 0:
                mesg(f"File {args.filename} length is zero.")
                exit()
            case 1:
                x = 0
                y = 2 * cellsize
            case 2 | 3 | 4 | 5 | 6 :
                x = 0
                y = cellsize
            case _:
                x = 2 * cellsize
                y = 0
        # Reading the pixels into the code array
        while i <= size:
            (colorr, colorg, colorb) = img.getpixel((x, y))
            colorcode['r'].append(colorr)
            colorcode['g'].append(colorg)
            colorcode['b'].append(colorb)
            i += 1
            x += cellsize
            if x > imgxsize - 1:
                x = 0
                y += cellsize
        # Bytedump mode
        if args.bytedump is True:
            i = 0
            print(f"Dumping {args.filename}")
            print(f"ColorVM version: {V_MAJOR}.{V_MINOR}")
            print(f"Image file version: {majorver}.{minorver}, Cell size: {cellsize}\n")
            while i < size:
                print(f"Line {i}: [{colorcode["r"][i]}, {colorcode["g"][i]}, {colorcode["b"][i]}]")
                i += 1
            exit()
        # Disasm mode
        if args.disasm is True:
            i = 0
            print(f"#Disassembling {args.filename}")
            print(f"#ColorVM version: {V_MAJOR}.{V_MINOR}")
            print(f"#Image file version: {majorver}.{minorver}, Cell size: {cellsize}\n")
            while i < size:
                disasmr = "push " + str(colorcode["r"][i]) if disasmdict.get(colorcode["r"][i]) is None else disasmdict.get(colorcode["r"][i])
                disasmg = "push " + str(colorcode["g"][i]) if disasmdict.get(colorcode["g"][i]) is None else disasmdict.get(colorcode["g"][i])
                disasmb = "push " + str(colorcode["b"][i]) if disasmdict.get(colorcode["b"][i]) is None else disasmdict.get(colorcode["b"][i])
                print(f"{disasmr:9}; {disasmg:9}; {disasmb:9} #Line {i}")
                i += 1
            exit()
        # Changing state to RUNNING
        for color in colors:
            colorstate[color] = RUNNING
        # Main sequence
        terminate = False
        while not terminate:
            for color in colors:
                if colorstate[color] == OVERRUN:
                    debuglog(f"'{color}', State: {statereverse[colorstate[color]]}, IP: {colorip[color]}, Code data: N/A", colorstyles[color])
                else:
                    debuglog(f"'{color}', State: {statereverse[colorstate[color]]}, IP: {colorip[color]}, Code data: {colorcode[color][colorip[color]]}", colorstyles[color])
                if colorstate[color] == RUNNING:
                    match colorcode[color][colorip[color]]:
                        # Checking for a nop instruction
                        case(int(0b1011_1100)):
                            colorstat[color]["nop"] += 1
                            colorip[color] += 1
                            if colorip[color] == size:
                                colorstate[color] = OVERRUN
                                debuglog(f"  Thread '{color}' overrun.", colorstyles[color])
                        # Checking for a halt instruction
                        case(int(0b1100_0000)):
                            colorstat[color]["halt"] += 1
                            colorstate[color] = HALTED
                            debuglog(f"  Thread '{color}' halted.", colorstyles[color])
                        case _:
                            colorexec(color)
                            colorip[color] += 1
                            if colorip[color] == size:
                                colorstate[color] = OVERRUN
                                debuglog(f"  Thread '{color}' overrun.", colorstyles[color])
                elif colorstate[color] == AWAIT and waitstack[0] == color:
                    debuglog(f"  Thread '{color}' in AWAIT state (waitstack top: '{waitstack[0]}').", colorstyles[color])
                    colorstat[color]["waita"] += 1
                    if len(colorstack['a']) >= 1:
                        debuglog(f"  Data found in 'a' stack.", colorstyles[color])
                        _ = waitstack.pop(0)
                        colorexec(color)
                        colorip[color] += 1
                        if colorip[color] == size:
                            colorstate[color] = OVERRUN
                            debuglog(f"  Thread '{color}' overrun.", colorstyles[color])
            tmprun = 0
            tmpawait = 0
            for color in colors:
                if colorstate[color] == RUNNING:
                    tmprun += 1
                elif colorstate[color] == AWAIT:
                    tmpawait += 1
            debuglog(f"Number of running threads: {tmprun}, await threads: {tmpawait}.", gendebug_style)
            if tmprun == 0:
                if tmpawait != 0:
                    mesg("Thread deadlock. Exiting.")
                    terminate = True
                else:
                    mesg("Threads halted. Exiting.")
                    terminate = True
        if args.statistics is True:
            insttable = Table(title="Execution statistics")
            insttable.add_column("Instruction", justify="left", style=table_info_style)
            insttable.add_column("r", justify="right", style=red_style)
            insttable.add_column("g", justify="right", style=green_style)
            insttable.add_column("b", justify="right", style=blue_style)
            instlines = []
            for key in colorstat["r"].keys():
                if colorstat["r"][key] != 0 or colorstat["g"][key] != 0 or colorstat["b"][key] != 0:
                    instlines.append((key, colorstat["r"][key], colorstat["g"][key], colorstat["b"][key]))
            instline_sorted = sorted(instlines, key=lambda instline: instline[0])
            for line in instline_sorted:
                insttable.add_row(f"{line[0]}", f"{line[1]}", f"{line[2]}", f"{line[3]}")
            console.print(insttable)
    else:
        mesg(f"File {args.filename} not found.")