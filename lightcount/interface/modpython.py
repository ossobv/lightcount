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
from lightcount.graph import StandardGraph, GraphParameters

# The root of the handler in the request uri. (E.g. if you've defined
# <Location /traffic/> in your apache configuration, you want to set
# this to '/traffic/'.)
WEB_ROOT = '/'


def handler(req):
    is_debug = bool(req.server.get_config()['PythonDebug'])
    uri = req.uri[len(WEB_ROOT):]

    # This is an example obviously. I could write "example.com" here,
    # but having a working example in SVN makes my life easy.
    # You will want to read graph.py and lightcount/graph.py to see
    # exactly which GraphParameters you can define.

    if uri == 'code.osso.nl-current-day-linear.png':
        return current_day(req, ip='91.194.225.81', log=False)
    elif uri == 'code.osso.nl-current-day-log.png':
        return current_day(req, ip='91.194.225.81', log=True)

    req.content_type = 'text/plain'
    req.write('Try:\n%scode.osso.nl-current-day-linear.png' % (WEB_ROOT,))
    return 0


def current_day(req, ip, log=False):
    graph_parameters = GraphParameters()
    graph_parameters.logarithmic_scale = log
    graph_parameters.time_zone = timezone('UTC') #timezone_default() # does not work properly with python2.4
    graph_parameters.begin_date, graph_parameters.end_date = datetimes_from_datetime_and_period(
        begin_date=None,
	end_date=datetime.now(graph_parameters.time_zone),
	period='day'
    )
    graph_parameters.ips.append(ip)

    req.content_type = 'image/png'
    req.write(StandardGraph(Data(Config(os.path.dirname(__file__) + '/lightcount.conf')), graph_parameters).output())
    return 0
