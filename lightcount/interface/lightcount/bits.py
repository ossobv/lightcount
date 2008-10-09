# vim: set ts=8 sw=4 sts=4 et:

def inet_atol(ip):
    ''' Converts the Internet host address IP from the standard numbers-and-dots notation into a long integer. '''
    ip_long = 0L
    for byte in [int(byte) << (8 * (3 - pos)) for pos, byte in enumerate(ip.split('.'))]:
        ip_long |= byte
    return ip_long

def bitfloor(number):
    ''' Rounds down to the nearest number with only one active bit. '''
    number = long(number)
    for i in range(32):
        if (number >> (i + 1)) == 0:
            return (number >> i) << i

