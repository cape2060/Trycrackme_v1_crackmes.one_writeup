#!/usr/bin/python3

import string
def rcl(value, shift, carry, bits=32):
    '''Performs the operation rotate with carry left
    '''
    mask = (1 << bits) - 1
    
    for _ in range(shift):
        new_carry = (value >> (bits - 1)) & 1
        value = ((value << 1) | carry) & mask
        carry = new_carry
    
    return value, carry
def shl(value, shift, bits=32):
    """Perform operation shift left"""
    mask = (1 << bits) - 1
    
    # last bit shifted out becomes CF
    if shift > 0:
        new_cf = (value >> (bits - shift)) & 1
    else:
        new_cf = 0
    
    result = (value << shift) & mask   # shift left, chop overflow
    
    return result, new_cf
def rotating(length):
    """This function is use to generate the seed using the length of the name
    """
    multiplier = 0x19660d
    adder = 0x3c6ef35f
    divider = 0x5e
    t_rot = 0x40
    seed = ""
    eax = (length * multiplier) + adder
    for _ in range(length):    
        carry = 0
        esi = 0
        rdi = 0
        edx = 0
        ebp = 1
        for i in range(t_rot):
            eax,carry = shl(eax,1)
            edx,carry = rcl(edx,1,carry)
            esi,carry = rcl(esi,1,carry)
            rdi,carry = rcl(rdi,1,carry)
            if rdi < ebp:
                carry = 1
            else:
                carry = 0
            #print(f"{hex(eax)=},{hex(edx)=},{hex(esi)=}")
        eax = (((esi * multiplier) & 0xFFFFFFFF) + adder) & 0xFFFFFFFF
        seed += chr((esi % divider)+0x21)
    return seed

def convert_to_ascii(s):
    """this function convert the each letter of the seed into hex"""
    return [hex(ord(sh)).replace('0x','') for sh in s]

def addnumber(string1):
    """This function perform rot12 to only capital letters"""
    letters = string.ascii_letters
    string1 = list(string1)
    string2 = [s.replace(s,chr(((ord(s)-64+12)%26)+64)) if s in letters and (((ord(s)-64+12)%26)+64) != 64 else 'Z' if (((ord(s)-64+12)%26)+64) == 64 and s in letters else s for s in string1]
    return string2

def addhiphun(s):
    """This function add '-' after each 4 letter
example: if string is 12345678 then this function return 1234-5678
"""
    st = [f'{hs}-' if (i+1) % 4 == 0 else hs for i,hs in enumerate(s)]
    return "".join(st)

if __name__ == "__main__":
    Name = input('\033[32m[-] Enter Your Name: \033[0m')
    seed = rotating(len(Name))
#    print(seed)
    ball = list("".join(convert_to_ascii(seed)).upper())
    n = addnumber(ball)
    cat = addhiphun("".join(n))
    if cat[-1:] == "-":
        cat = cat[:-1]
    print("\033[33m[+] Your Serial key:",cat)
