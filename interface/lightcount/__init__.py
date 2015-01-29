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

INTERVAL_SECONDS = 300 # hardcoded define from lightcount daemon (timer.c)


class Config:
    ''' LightCount configuration file parser. Construct with config file name as argument.
        Read the values as attributes. E.g.: c = Config('lightcount.conf') : print c.storage_host) '''

    def __init__(self, filename):
        ''' Supply a file name to read values from. '''
        f = open(filename, 'r')
        d = {
            'storage_host': 'localhost',
            'storage_port': 3306,
            'storage_user': 'root',
            'storage_pass': '',
            'storage_dbase': 'lightcount',
        }
        for line in f:
            k, v = line.split('=', 1)
            d[k.strip()] = v.strip()
        self.config = d

    def __getattr__(self, name):
        return self.config[name]

