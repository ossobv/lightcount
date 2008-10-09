# vim: set ts=8 sw=4 sts=4 et:
from lightcount import bits
from matplotlib.ticker import Formatter, MultipleLocator, LogLocator
from matplotlib.dates import DateFormatter, MONDAY, \
        MinuteLocator, HourLocator, WeekdayLocator, MonthLocator, YearLocator


class BitsPerSecondFormatter(Formatter):
    ''' Formatter for Y-axis in bits/second. Passed to matplotlib set_major_formatter(). '''

    def __call__(self, x, pos=0):
        ''' Returns "%(num)u %(letter)bits/s" dependent on number x. '''
        if x <= 1024:
            letter = ''
        elif x <= 1048576:
            x /= 1024.0
            letter = 'k'
        elif x <= 1073741824:
            x /= 1048576.0
            letter = 'M'
        else:
            x /= 1073741824.0
            letter = 'G'

        # This feels like a non-optimal solution ;)
        if float(int(x)) == x:
            return '%.f %sbit/s' % (x, letter)
        elif float(int(x * 10)) == x * 10:
            return '%.1f %sbit/s' % (x, letter)
        return '%.2f %sbit/s' % (x, letter)



class LinearBitsLocator(MultipleLocator):
    ''' Linear Locator for Y-axis. '''

    def __init__(self, peak, minor=False):
        multiplier = max(bits.bitfloor(peak / 6), 8)
        if minor:
            multiplier /= 8
        MultipleLocator.__init__(self, multiplier)


class LogBitsLocator(LogLocator):
    ''' Logarithmic locator for Y-axis. '''

    def __init__(self, minor=False):
        if not minor:
            LogLocator.__init__(self, base=2)
        else:
            LogLocator.__init__(self, base=2, subs=range(1, 9))

