# trycrackme — Crackme Writeup

> **Platform:** crackmes.one  
> **Difficulty:** 3.3 / 5  
> **Architecture:** x86 Windows EXE  
> **Packer:** UPX  
> **Serial Type:** Runtime generated (not hardcoded)  
> **Tools:** Binary Ninja, x32dbg, Python 3  

---

## Table of Contents

1. [Initial Analysis](#1-initial-analysis)
2. [Unpacking the Binary](#2-unpacking-the-binary)
3. [Reversing the Serial Algorithm](#3-reversing-the-serial-algorithm)
4. [Full Algorithm Flow](#4-full-algorithm-flow)
5. [Python Keygen](#5-python-keygen)
6. [Key Takeaways](#6-key-takeaways)

---

## 1. Initial Analysis

### Opening in Binary Ninja

The first step was loading the EXE into Binary Ninja for static analysis. Something was immediately wrong — only the `_start` function was visible. No other functions, no strings, no meaningful code anywhere.

```
Binary Ninja — Function List:
  _start    <-- only function visible
  (nothing else...)
```

This is the classic symptom of a **packed executable**. The real code is compressed or encrypted and only unpacks at runtime — Binary Ninja cannot analyze what it cannot see statically.

### Running `strings`

To identify the packer, `strings` was run against the binary:

```bash
$ strings trycrackme.exe | grep -i upx

UPX0
UPX1
UPX!
$Info: This file is packed with the UPX executable packer.
$Id: UPX 3.96 ...
```

The binary was packed with **UPX** — one of the most common packers. UPX conveniently leaves its signature strings in the file, making identification trivial.

---

## 2. Unpacking the Binary

### Finding OEP with the ESP Trick in x32dbg

Instead of using `upx -d`, the binary was unpacked manually using the **ESP Trick** in x32dbg — a reliable method for finding the Original Entry Point (OEP) of UPX-packed binaries.

**Why the ESP trick works:**  
UPX saves all registers with `PUSHAD` before unpacking, then restores them with `POPAD` and jumps to OEP. Setting a hardware breakpoint on the saved ESP catches this exact moment.

**Steps:**

1. Load EXE in x32dbg — debugger pauses at system entry point
2. Press `F9` once to run to the packer entry — note the **ESP** value in the registers panel
3. In the Dump panel, navigate to address **ESP−4**
4. Right-click → **Breakpoint → Hardware, Access → DWORD**
5. Press `F9` — hardware BP fires after UPX `POPAD` + `JMP` sequence
6. Step through with `F8` — the `JMP EAX/EDX` lands at OEP

```asm
; UPX unpacking stub ends with:
POPAD                  ; restore all registers saved by PUSHAD
JMP EAX                ; <-- jump to OEP

; At OEP — classic MSVC prologue:
PUSH EBP
MOV EBP, ESP           ; <-- you are now at the real code ✅
```

With the binary unpacked in memory, the full code was now visible and analyzable in both x32dbg and Binary Ninja.

---

## 3. Reversing the Serial Algorithm

The serial is **not hardcoded** — it is generated at runtime based on the **length of the username** entered. The algorithm has 4 stages.

---

### Stage 1 — Seed Generation (LCG + 128-bit Shift Register)

The crackme uses a **Linear Congruential Generator (LCG)** — the same constants as `glibc rand()` — seeded from the length of the input name:

```python
multiplier = 0x19660D
adder      = 0x3C6EF35F

eax = (len(name) * multiplier) + adder   # LCG seed
```

Then for each character of the name, **64 iterations** (`0x40`) of a chained bit-shift loop run:

```python
for i in range(0x40):
    eax, carry = SHL(eax, 1)         # shift eax left, MSB goes to carry
    edx, carry = RCL(edx, 1, carry)  # carry flows into edx
    esi, carry = RCL(esi, 1, carry)  # carry flows into esi
    rdi, carry = RCL(rdi, 1, carry)  # carry flows into rdi

    # rdi < ebp(1) overrides carry — injects extra entropy
    carry = 1 if rdi < 1 else 0
```

This forms a **128-bit shift register**: `eax → edx → esi → rdi`, all chained through the carry flag. After 64 rotations, `esi` holds the value used to generate one seed character:

```python
seed_char = chr((esi % 0x5E) + 0x21)
```

At the end of each outer loop iteration, `eax` is updated with a new LCG step:

```python
eax = ((esi * multiplier) + adder) & 0xFFFFFFFF
```

> **Note:** `edx`, `esi`, and `rdi` are **not reset** between outer iterations — each loop builds on the previous state, creating a cascading effect.

---

### Stage 2 — Convert to ASCII Hex

Each character of the seed string is converted to its **hex ASCII code** (no `0x` prefix) and uppercased:

```python
# 'A' (65)  -->  hex(65) = '0x41'  -->  strip prefix  -->  '41'  -->  uppercase '41'
# 'z' (122) -->  hex(122) = '0x7a' -->  strip prefix  -->  '7a'  -->  uppercase '7A'

ascii_hex = [hex(ord(c)).replace('0x', '').upper() for c in seed]
```

---

### Stage 3 — ROT-12 Caesar Cipher

Each **uppercase letter** in the hex string is shifted by 12 positions (ROT-12). Digits (`0–9`) are left unchanged. There is one edge case: if the shift lands on `chr(64)` (`@`), it is replaced with `'Z'`:

```python
# Shift formula:
result = chr(((ord(s) - 64 + 12) % 26) + 64)

# Edge case: 'N' -> (78 - 64 + 12) % 26 = 0 -> chr(64) = '@' -> force 'Z'

# Examples:
# 'A' --> 'M'
# 'N' --> 'Z'  (edge case)
# '4' --> '4'  (digit, unchanged)
```

---

### Stage 4 — Hyphen Formatting

A hyphen `'-'` is inserted after every **4 characters** to format the serial in the classic `XXXX-XXXX-XXXX` style. Any trailing hyphen is stripped:

```python
# 'ABCDEFGH12345678'  -->  'ABCD-EFGH-1234-5678'

formatted = [f'{c}-' if (i + 1) % 4 == 0 else c for i, c in enumerate(serial)]
if formatted[-1] == '-':
    formatted = formatted[:-1]
```

---

## 4. Full Algorithm Flow

```
Input: Name string
         |
         v
  len(Name)  --->  LCG seed (0x19660D / 0x3C6EF35F)
                         |
                         v
             64x [ SHL(eax) -> RCL(edx) -> RCL(esi) -> RCL(rdi) ]
                         |
                         v
              seed_char = chr((esi % 0x5E) + 0x21)
                         |
                         v
              hex(ord(seed_char)).upper()  -- e.g. 'A' -> '41'
                         |
                         v
              ROT-12 on each uppercase letter
              (digits unchanged, '@' edge case -> 'Z')
                         |
                         v
              Insert '-' every 4 characters
                         |
                         v
              Serial Key: XXXX-XXXX-XXXX-XXXX  ✅
```

---

## 5. Python Keygen

The full algorithm was replicated in Python:

```python
#!/usr/bin/python3

import string

def rcl(value, shift, carry, bits=32):
    """Rotate through Carry Left"""
    mask = (1 << bits) - 1
    for _ in range(shift):
        new_carry = (value >> (bits - 1)) & 1
        value = ((value << 1) | carry) & mask
        carry = new_carry
    return value, carry

def shl(value, shift, bits=32):
    """Shift Left"""
    mask = (1 << bits) - 1
    new_cf = (value >> (bits - shift)) & 1 if shift > 0 else 0
    result = (value << shift) & mask
    return result, new_cf

def rotating(length):
    """Generate seed from name length using LCG + 128-bit shift register"""
    multiplier = 0x19660d
    adder      = 0x3c6ef35f
    divider    = 0x5e
    t_rot      = 0x40
    seed       = ""
    eax        = (length * multiplier) + adder

    for _ in range(length):
        carry = esi = rdi = edx = 0
        ebp = 1
        for _ in range(t_rot):
            eax, carry = shl(eax, 1)
            edx, carry = rcl(edx, 1, carry)
            esi, carry = rcl(esi, 1, carry)
            rdi, carry = rcl(rdi, 1, carry)
            carry = 1 if rdi < ebp else 0
        eax = (((esi * multiplier) & 0xFFFFFFFF) + adder) & 0xFFFFFFFF
        seed += chr((esi % divider) + 0x21)
    return seed

def convert_to_ascii(s):
    """Convert each seed character to its uppercase hex ASCII code"""
    return [hex(ord(c)).replace('0x', '') for c in s]

def addnumber(string1):
    """Apply ROT-12 to uppercase letters only"""
    letters = string.ascii_letters
    return [
        s.replace(s, chr(((ord(s) - 64 + 12) % 26) + 64))
        if s in letters and (((ord(s) - 64 + 12) % 26) + 64) != 64
        else 'Z' if (((ord(s) - 64 + 12) % 26) + 64) == 64 and s in letters
        else s
        for s in string1
    ]

def addhiphun(s):
    """Insert '-' after every 4 characters"""
    st = [f'{c}-' if (i + 1) % 4 == 0 else c for i, c in enumerate(s)]
    result = "".join(st)
    return result[:-1] if result.endswith('-') else result

if __name__ == "__main__":
    name = input('\033[32m[-] Enter Your Name: \033[0m')
    seed = rotating(len(name))
    ball = list("".join(convert_to_ascii(seed)).upper())
    n    = addnumber(ball)
    cat  = addhiphun("".join(n))
    print("\033[33m[+] Your Serial Key:", cat)
```

**Usage:**

```bash
$ python3 key_gen.py

[-] Enter Your Name: Alice
[+] Your Serial Key: XXXX-XXXX-XXXX-XXXX
```

---

## 6. Key Takeaways

- **UPX detection is easy** — `strings` leaks the packer signature immediately; always run `strings` on an unknown binary first.
- **The ESP Trick is reliable for UPX** — `PUSHAD → unpack → POPAD → JMP OEP` is UPX's standard pattern; a hardware BP on ESP−4 catches it every time.
- **Runtime serials require full algorithm reversal** — you cannot just grep for the key or dump it from memory at the wrong time; you must understand and replicate the generation logic.
- **LCG constants `0x19660D` / `0x3C6EF35F` are `glibc rand()`** — recognising standard PRNG constants in disassembly speeds up reversing significantly.
- **SHL + RCL chains spread entropy across registers via carry** — `eax → edx → esi → rdi` acts as a 128-bit shift register; carry flag is the bridge.
- **ROT-12 on hex strings is a layered obfuscation** — applying a Caesar cipher on top of hex-encoded values makes the output look random at a glance.

---

*Solved and written up after reversing the unpacked binary in x32dbg and Binary Ninja.*
