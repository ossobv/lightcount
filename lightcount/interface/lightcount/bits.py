# vim: set ts=8 sw=4 sts=4 et:
#=======================================================================
# Copyright (C) 2008, OSSO B.V.
# This file is part of LightCount.
# 
# LightCount is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# LightCount is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with LightCount.  If not, see <http://www.gnu.org/licenses/>.
#=======================================================================

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

