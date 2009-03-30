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
import lightcount
from calendar import monthrange
from lib.fixed_datetime import datetime, timedelta # datetime has tz bugs 
from pytz import timezone
from time import mktime, time


def timezone_default():
    ''' Tries to get current timezone. '''
    try:
        return timezone(os.environ('TZ').strip())
    except:
        try:
            return timezone(file('/etc/timezone', 'r').read().strip())
        except:
            return timezone('UTC')

def parse_datetime(date_str, tz=None):
    ''' Converts a date/time string to a datetime object. '''
    try:
        if tz is not None and type(tz) == str:
            tz = timezone(tz)
    except Exception, e:
        raise ValueError('Invalid time zone: %s' % e)
    try:
        try:
            date_str, time_str = date_str.split(' ', 1)
            hour, min = time_str.split(':', 1)
        except ValueError:
            hour, min = 0, 0
        if '/' in date_str:
            month, day, year = date_str.split('/', 2)
        elif '-' in date_str:
            year, month, day = date_str.split('-', 2)
        else:
            raise ValueError('Date parse error')
        datetime_obj = datetime(year=int(year), month=int(month), day=int(day), hour=int(hour), minute=int(min), second=0, tzinfo=tz)
    except Exception, e:
        raise ValueError('Dates should be in this format: mm/dd/yyyy OR YYYY-mm-dd [HH:MM]')
    return datetime_obj

def known_periods():
    ''' Return all known 'period-of-time' types. '''
    return ('hour', '12h', 'day', 'week', 'month', 'year')

def datetime_round(datetime_obj, period, round_up=False):
    ''' Round the passed datetime to a suitable even number, based on the period.
        E.g. when period is 'month', the date gets rounded to the first day of the month. '''
    year, month, day, hour, minute, _, _, _, _ = datetime_obj.timetuple()

    # We must be INTERVAL_SECONDS aligned
    assert (lightcount.INTERVAL_SECONDS % 60) == 0
    if lightcount.INTERVAL_SECONDS <= 3600:
        minute -= minute % (lightcount.INTERVAL_SECONDS / 60)
    else:
        raise Exception('lightcount.INTERVAL_SECONDS must be <= 3600 and minute aligned')

    if period == 'year':
        plus_one = (0, 1)[round_up and (month != 1 or day != 1 or hour != 0 or minute != 0)]
        stamp = mktime((year + plus_one, 1, 1, 0, 0, 0, -1, -1, -1))
    elif period == 'month':
        plus_one = (0, 1)[round_up and (day != 1 or hour != 0 or minute != 0)]
        stamp = mktime((year, month + plus_one, 1, 0, 0, 0, -1, -1, -1))
    elif period == 'week':
        plus_one = (0, 1)[round_up and (hour != 0 or minute != 0)]
        stamp = mktime((year, month, day + plus_one, 0, 0, 0, -1, -1, -1))
    elif period == 'day' or period == '12h':
        plus_one = (0, 1)[round_up and minute != 0]
        stamp = mktime((year, month, day, hour + plus_one, 0, 0, -1, -1, -1))
    elif period == 'hour':
        stamp = mktime((year, month, day, hour, minute, 0, -1, -1, -1))
    return datetime.fromtimestamp(stamp, datetime_obj.tzinfo)

def datetimes_from_datetime_and_period(begin_date=None, end_date=None, period=None):
    def period_add(period, in_date, multiplier):
        year, month, day, hour, minute, _, _, _, _ = in_date.timetuple()
        if period == 'hour': stamp = mktime((year, month, day, hour + multiplier, minute, 0, -1, -1, -1))
        elif period == '12h': stamp = mktime((year, month, day, hour + multiplier * 12, minute, 0, -1, -1, -1))
        elif period == 'day': stamp = mktime((year, month, day + multiplier, hour, minute, 0, -1, -1, -1))
        elif period == 'week': stamp = mktime((year, month, day + multiplier * 7, hour, minute, 0, -1, -1, -1))
        elif period == 'month': stamp = mktime((year, month + multiplier, day, hour, minute, 0, -1, -1, -1))
        elif period == 'year': stamp = mktime((year + multiplier, month, day, hour, minute, 0, -1, -1, -1))
        return datetime.fromtimestamp(stamp, in_date.tzinfo)
        
    if (begin_date != None and end_date != None and period != None) \
            or (begin_date == end_date == None) \
            or (begin_date == period == None) \
            or (end_date == period == None):
        raise Exception('Exactly two of begin_date, end_date and period are required')

    if begin_date == None:
        end_date = datetime_round(end_date, period, round_up=True)
        begin_date = period_add(period, end_date, -1)
    elif end_date == None:
        begin_date = datetime_round(begin_date, period, round_up=False)
        end_date = period_add(period, begin_date, 1)

    return begin_date, end_date
