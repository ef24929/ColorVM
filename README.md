# ColorVM

A stack-based virtual machine that executes programs encoded in image pixels, with separate execution threads for red, green, and blue color channels.

## Overview

ColorVM is a unique virtual machine that interprets programs stored as color values in image files. Each pixel contains instructions for three separate execution threads (red, green, blue channels), creating a parallel execution environment with inter-thread communication through a shared alpha channel.

## Features

- **Multi-threaded execution**: Separate stacks and instruction pointers for R, G, B channels
- **Inter-thread communication**: Shared alpha channel for data exchange between threads
- **Stack-based architecture**: Standard stack operations (push, pop, dup, swap, etc.)
- **Arithmetic operations**: Basic math (add, sub, mul, div, rem)
- **Bitwise operations**: Logical operations (and, or, not, shl, shr)
- **Control flow**: Conditional jumps (jmpz, jmpnz)
- **I/O operations**: Character and integer input/output
- **Debug support**: Detailed execution tracing and statistics

## Usage

```bash
python colorvm.py <image_file> [options]
```

### Options

- `-b, --bytedump`: Display raw byte values without execution
- `-d, --disasm`: Disassemble the program without execution
- `-s, --silent`: Run silently without warnings or info messages
- `-t, --statistics`: Show execution statistics after termination
- `-g, --debug`: Enable detailed debug output with stack dumps

### Examples

```bash
# Run a ColorVM program
python colorvm.py program.png

# Disassemble a program
python colorvm.py program.png -d

# Run with debug output and statistics
python colorvm.py program.png -g -t
```

## Image Format (Pollock Format)

ColorVM uses a custom image format called "Pollock":

- **First pixel**: `[major_version, minor_version, cell_size]`
- **Second pixel**: Encodes program size as `[size÷65536, size÷256, size%256]`
- **Subsequent pixels**: Program instructions as RGB values
- **Cell size**: Determines pixel spacing for instruction reading

## Instruction Set

### Stack Operations
- `0-127`: Push literal value
- `add (128)`: Pop two values, push sum
- `sub (132)`: Pop two values, push difference
- `mul (136)`: Pop two values, push product
- `div (140)`: Pop two values, push quotient
- `rem (144)`: Pop two values, push remainder
- `pop (148)`: Remove top stack value
- `swap (152)`: Swap top two stack values
- `dup (156)`: Duplicate top stack value
- `rot (160)`: Rotate stack elements

### Bitwise Operations
- `not (164)`: Bitwise NOT
- `or (168)`: Bitwise OR
- `and (172)`: Bitwise AND
- `shl (232)`: Shift left
- `shr (236)`: Shift right

### Comparison
- `gt (176)`: Greater than
- `eq (180)`: Equal to
- `lt (184)`: Less than

### Control Flow
- `nop (188)`: No operation
- `halt (192)`: Halt thread
- `jmpz (196)`: Jump if zero
- `jmpnz (200)`: Jump if not zero

### I/O Operations
- `outc (204)`: Output character
- `outi (212)`: Output integer
- `inc (208)`: Input character
- `ini (216)`: Input integer

### Inter-thread Communication
- `pusha (220)`: Push value to alpha channel
- `waita (224)`: Wait for data from alpha channel

### Other
- `neg (228)`: Negate value

## Requirements

- Python 3.7+
- PIL (Pillow) library
- Rich library for colored output

## Installation

```bash
pip install pillow rich
```

## Thread States

- **LOADING**: Initial state before execution
- **RUNNING**: Active execution
- **AWAIT**: Waiting for data from alpha channel
- **HALTED**: Stopped by halt instruction
- **OVERRUN**: Execution pointer exceeded program bounds

## License

GPL-3.0 license
