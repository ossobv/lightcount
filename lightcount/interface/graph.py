#!/usr/bin/env python
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


class ParameterError(Exception):
    pass
    
            
def main(cli_arguments):
    from getopt import gnu_getopt as getopt
    from lightcount import Config, graphutil
    from lightcount.timeutil import timezone_default, known_periods
    from lightcount.data import Data
    from lightcount.graph import StandardGraph
    scratchpad = {'date': {}, 'queries': []}

    optlist, args = getopt(
        cli_arguments,
        'c:q:g:t:z:h',
        ('config-file=', 'query=', 'write-graph=', 'time-zone=', 'period=', 'begin-date=',
                'end-date=', 'log', 'linear', 'help', 'version')
    )

    for key, val in optlist:
        if key in ('-c', '--config-file'):
            if 'config_file' in scratchpad:
                raise GetoptError('Configuration file name already specified!')
            scratchpad['config_file'] = val
        elif key in ('-q', '--query'):
            scratchpad['queries'].append(val)
        elif key in ('-g', '--write-graph'):
            if 'graph_file' in scratchpad:
                raise GetoptError('Output graph file name already specified!')
            scratchpad['graph_file'] = val
        elif key in ('-z', '--time-zone'):
            if 'time_zone' in scratchpad:
                raise GetoptError('Time zone already specified!')
            try:
                scratchpad['time_zone'] = pytz.timezone(val)
            except:
                raise GetoptError('Invalid or unknown time zone specified!')
        elif key in ('-t', '--period'):
            if 'period' in scratchpad['date']:
                raise GetoptError('Period already specified!')
            if val not in known_periods():
                raise GetoptError('Specify one of %s as period.' % (', '.join(known_periods())))
            scratchpad['date']['period'] = val
        elif key == '--begin-date':
            if 'begin_date' in scratchpad['date']:
                raise GetoptError('Begin date already specified!')
            scratchpad['date']['begin_date'] = val
        elif key == '--end-date':
            if 'end_date' in scratchpad['date']:
                raise GetoptError('End date already specified!')
            scratchpad['date']['end_date'] = val
        elif key in ('--linear', '--log'):
            if 'log_scale' in scratchpad:
                raise GetoptError('Specify either --linear or --log and do it once.')
            scratchpad['log_scale'] = key == '--log'
        elif key in ('-h', '--help'):
            print '''Usage: FIXME.py OPTIONS
Does some XXX YYY with the lightcount data.. blah.

File selection:
  -c, --config-file=F   read config file F (dfl: ./lightcount.conf)
  -g, --draw-graph=F    write output png as F (it normally only writes
                        statistics to stdout)

Period selection:
  -t, --period=P        period P: %(Ps)s (dfl: month)
      --begin-date=D    the begin date D as YYYY-mm-dd
      --end-date=D      the end date D as YYYY-mm-dd (dfl: now)
  -z, --time-zone=Z     use time zone name Z (dfl: %(Z)s)

Value selection:
  -q, --query=Q         specify an expression Q using (ip, net, node,
                        vlan) and the operators (and, or, not and
                        the parentheses) (may be specified multiple
                        times)

Automatic selection (you may specify at most one query):
  -I, --top-ips=N       show the top N byte users by IP address
  -N, --top-nodes=N     show the top N byte users by node
  -V, --top-vlans=N     show the top N byte users by VLAN

Graph options:
      --linear          display the graph with a linear scale (default)
      --log             display the graph with a logarithmic scale

Nodes may specified as a node name or a node id. IP addresses may be specified
in the normal numbers-and-dots notation or as an unsigned integer. Nets are
specified as IP addresses with a trailing slash and a netmask number.
''' % {'Ps': ', '.join(known_periods()), 'Z': timezone_default()}
            sys.exit(0)
        elif key == '--version':
            print 'FIXME.py v0.1'
        else:
            assert False, 'Programming error'

    # Check invalid options
    if len(args) != 0:
        raise GetoptError('This program does not take non-option arguments.')
    if len(scratchpad['date']) == 3:
        raise GetoptError('Specify at most one date and a period or two dates.')
        
    # Set defaults
    if 'config_file' not in scratchpad:
        scratchpad['config_file'] = 'lightcount.conf'
    if 'time_zone' not in scratchpad:
        scratchpad['time_zone'] = timezone_default()
    for name in ('begin_date', 'end_date', 'period'):
        if name not in scratchpad['date']:
            scratchpad['date'][name] = None
    if 'log_scale' not in scratchpad:
        scratchpad['log_scale'] = False
        
    # Get data object
    try:
        data = Data(Config(scratchpad['config_file']))
    except IOError, e:
        raise ParameterError('Error reading config file: %s' % e)
    
    # Get period object (fills in default values if necessary: P=month, E=now)
    try:
        period = data.parse_period(
            begin_date=scratchpad['date']['begin_date'], 
            end_date=scratchpad['date']['end_date'], 
            period=scratchpad['date']['period'], 
            time_zone=scratchpad['time_zone']
        )
    except ValueError, e:
        raise ParameterError('Error parsing time/period: %s' % e)


    # XXX add select-packet-count instead of bytes option
    # XXX fit modpython example to be in sync with current version

    if True:
        try:
            result_list = data.parse_queries(period=period, queries=scratchpad['queries'])
        except (AssertionError, ValueError), e:
            raise ParameterError('Error parsing query: %s' % e)
    else:
        # XXX add checking for Top-N stuff..
        pass

    print 'Selected period (%s) between %s and %s:' % (period.get_period(), period.get_begin_date(), period.get_end_date())
    bps_formatter = graphutil.BitsPerSecondFormatter()
    for result in result_list:
        print ' * %s:' % result.human_query
        t, i, o = result.get_max_io_bps()
        print '   max bps at %s: in %s (%s), out %s (%s)' % (t, bps_formatter(i), i, bps_formatter(o), o)
        print '   max pps at %s: in %s, out %s' % result.get_max_io_pps()
        if period.get_period() == 'month':
            b = result.get_billing_value()
            print '   billing value (95th percentile): %s (%s)' % (bps_formatter(b), b)
    
    if 'graph_file' in scratchpad:
        print 'Writing %s graph to file %s ... ' % (('linear', 'logarithmic')[scratchpad['log_scale']], scratchpad['graph_file']),
        graph = StandardGraph(result_list=result_list, log_scale=scratchpad['log_scale'], show_billing_line=True)
        graph.write(scratchpad['graph_file'])
        print 'done.'



if __name__ == '__main__':
    import sys
    from getopt import GetoptError
    try:
        main(sys.argv[1:])
    except (GetoptError, ParameterError), e:
        print e 
