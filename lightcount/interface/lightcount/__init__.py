# vim: set ts=8 sw=4 sts=4 et:

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

