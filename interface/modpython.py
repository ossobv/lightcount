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

import os, sys
if __name__ != '__main__':
    os.environ['HOME'] = '/tmp' # matplotlib
from lightcount import Config
from lightcount.timeutil import *
from lightcount.data import Data
from lightcount.graph import StandardGraph

# The root of the handler in the request uri. (E.g. if you've defined
# <Location /traffic/> in your apache configuration, you want to set
# this to '/traffic/'.)
WEB_ROOT = '/'


def handler(req):
    try:
        is_debug = bool(req.server.get_config()['PythonDebug'])
    except KeyError:
        is_debug = False

    uri = req.uri[len(WEB_ROOT):]

    # This is an example obviously. I could write "example.com" here,
    # but having a working example in SVN makes my life easy.
    # You will want to read lightcount.py and lightcount/graph.py to see
    # exactly which parameters you can define.

    if uri == 'code.osso.nl-current-day-linear.png':
        return current_day(req, ip='91.194.225.81', log=False)
    elif uri == 'code.osso.nl-current-day-log.png':
        return current_day(req, ip='91.194.225.81', log=True)
    elif uri == 'wjd.osso.nl-current-day-linear.png':
        return current_day(req, ip='91.194.225.75', log=False)
    elif uri == 'wjd.osso.nl-current-day-log.png':
        return current_day(req, ip='91.194.225.75', log=True)

    req.content_type = 'text/plain'
    req.write('Try:\n%scode.osso.nl-current-day-linear.png' % (WEB_ROOT,))
    return 0


def current_day(req, ip, log=False):
    tz = timezone_default() # timezone('UTC') for python2.4
    data = Data(Config(os.path.dirname(__file__) + '/lightcount.conf'))
    period = data.parse_period(begin_date=None, end_date=datetime.now(tz), period='day', time_zone=tz)
    result_list = data.parse_queries(period=period, queries=['ip %s' % ip])

    req.content_type = 'image/png'
    req.write(StandardGraph(result_list=result_list, log_scale=log).output())
    return 0
