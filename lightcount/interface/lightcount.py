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

from getopt import GetoptError, gnu_getopt as getopt
from lightcount import Config, graphutil
from lightcount.timeutil import timezone_default, known_periods
from lightcount.data import Data
from lightcount.graph import StandardGraph


class ParameterError(GetoptError):
    pass
    

def main(cli_arguments):
    def set_or_raise(dict, key, value, friendly_name):
        if key in dict:
            raise ParameterError('Option \'%s\' already specified' % friendly_name)
        dict[key] = value

    # Read command line options
    optlist, args = getopt(
        cli_arguments,
        'c:q:g:t:z:h',
        ('config-file=', 'query=', 'write-graph=', 'time-zone=', 'period=', 'begin-date=',
                'end-date=', 'log', 'linear', 'help', 'version')
    )
    scratchpad = {
        'date': {},
        'queries': [],
    }

    for key, value in optlist:
        if key in ('-c', '--config-file'): set_or_raise(scratchpad, 'config_file', value, 'configuration filename')
        elif key in ('-q', '--query'): scratchpad['queries'].append(value)
        elif key in ('-g', '--write-graph'): set_or_raise(scratchpad, 'graph_file', value, 'graph filename')
        elif key in ('-z', '--time-zone'): set_or_raise(scratchpad, 'time_zone', value, 'time zone') # XXX of pytz.timezone(value)
        elif key in ('-t', '--period'):
            set_or_raise(scratchpad['date'], 'period', value, 'period')
            if value not in known_periods(): raise ParameterError('Specify one of %s as period' % (', '.join(known_periods())))
        elif key == '--begin-date': set_or_raise(scratchpad['date'], 'begin_date', value, 'begin date')
        elif key == '--end-date': set_or_raise(scratchpad['date'], 'end_date', value, 'end date')
        elif key in ('--linear', '--log'): 
            if 'log_scale' in scratchpad:
                raise ParameterError('Specify either --linear or --log and do it once')
            scratchpad['log_scale'] = key == '--log'
        elif key in ('-h', '--help'): do_help() ; sys.exit(0)
        elif key == '--version': do_version() ; sys.exit(0)
        else: assert False, 'Programming error'

    # Check parameters
    if len(args) == 0: raise ParameterError('Please supply a command or -h for help')
    elif len(args) == 1 and args[0] == 'stat': command = args[0]
    elif len(args) == 2 and args[0] in ('dump', 'graph', 'statgraph'): command = args[0]
    else: raise ParameterError('Invalid command or too many/few parameters')

    # Check invalid option combinations
    if len(scratchpad['date']) == 3: raise ParameterError('Specify at most one date and a period or two dates')
    
    # Set defaults
    if 'config_file' not in scratchpad: scratchpad['config_file'] = 'lightcount.conf'
    if 'log_scale' not in scratchpad: scratchpad['log_scale'] = False
    if 'time_zone' not in scratchpad: scratchpad['time_zone'] = timezone_default()
    for name in ('begin_date', 'end_date', 'period'):
        if name not in scratchpad['date']:
            scratchpad['date'][name] = None
        
    # Get data object
    try: data = Data(Config(scratchpad['config_file']))
    except IOError, e: raise ParameterError('Error reading config file: %s' % e)
    
    # Get period object (fills in default values if necessary: P=month, E=now)
    try: period = data.parse_period(begin_date=scratchpad['date']['begin_date'], end_date=scratchpad['date']['end_date'], \
            period=scratchpad['date']['period'], time_zone=scratchpad['time_zone'])
    except ValueError, e: raise ParameterError('Error parsing time/period: %s' % e)

    # Process request
    if command == 'dump': do_dump(data=data, period=period, options=scratchpad, file=args[1])
    elif command == 'graph': do_statgraph(data=data, period=period, options=scratchpad, graph=args[1])
    elif command == 'stat': do_statgraph(data=data, period=period, options=scratchpad, stat='-')
    elif command == 'statgraph': do_statgraph(data=data, period=period, options=scratchpad, stat='-', graph=args[1])


def do_dump(data, period, options, file):
    def print_percent(current, end):
        print '\b\b\b\b\b%3d%%' % (100.0 * float(current) / float(end)),
        
    # Filename suggestion: osso_traffic.0903amsterdamtz.csv
    if len(options['queries']) > 1: raise ParameterError('Dump command can take only one query')
    # Parse optional query or create the everything-query
    try: result = data.parse_queries(period=period, queries=options['queries'])[0]
    except (AssertionError, ValueError), e: raise ParameterError('Error parsing query: %s' % e)
    # Write it out
    csv = open(file, 'w')
    print 'Writing data to %s ...   0%%' % file,
    data.serialize(result=result, dest_file=csv, progress_callback=print_percent)
    print 'done'

def do_help(): 
    print '''Usage: lightcount.py COMMAND PARAMETERS OPTIONS
Perform analysis, backups or drawing of lightcount data.
Commands available are:
  dump          Dumps all data or only that supplied by a single query (-q) to
                a CSV file. Parameters: filename
  graph         Draws a graph of the optional queries (-q) to a PNG file.
                Parameters: graph filename
  stat          Write statistics about optional queries (-q) to standard out.
                Parameters: none
  statgraph     A combination of the stat and graph commands. Parameters: graph
                filename

File selection:
  -c, --config-file=F   read config file F (dfl: ./lightcount.conf)

Period selection:
  -t, --period=P        period P: %(Ps)s (dfl: month)
      --begin-date=D    the begin date D as YYYY-mm-dd
      --end-date=D      the end date D as YYYY-mm-dd (dfl: now)
  -z, --time-zone=Z     use time zone name Z (dfl: %(Z)s)

Value selection:
  -q, --query=Q         specify an expression Q using (host, ip, net, node,
                        vlan) and the operators (and, or, not and the
                        parentheses) (may be specified multiple times)

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

def do_statgraph(data, period, options, stat=None, graph=None):
    # XXX add select-packet-count instead of bytes option
    if True:
        try: result_list = data.parse_queries(period=period, queries=options['queries'])
        except (AssertionError, ValueError), e: raise ParameterError('Error parsing query: %s' % e)
    else:
        # XXX add checking for Top-N stuff..
        pass

    if stat is not None:
        print 'Selected period (%s) between %s and %s:' % (period.get_period(), period.get_begin_date(), period.get_end_date())
        bps_formatter = graphutil.BitsPerSecondFormatter()
        for result in result_list:
            print ' * %s:' % result.human_query
            t, i, o = result.get_max_io_bps()
            print '   max bps at %s: in %s (%s), out %s (%s)' % (t, bps_formatter(i), i, bps_formatter(o), o)
            print '   max pps at %s: in %s, out %s' % result.get_max_io_pps()
            if period.get_period() == 'month':
                b = result.get_billing_values()
                bmax = max(b[0], b[1])
                print '   billing value (95th percentile): %s (%s) [based on %sput]' % (bps_formatter(bmax), bmax, ('out', 'in')[b[0]==bmax])
    
    if graph is not None:
        print 'Writing %s graph to file %s ...' % (('linear', 'logarithmic')[options['log_scale']], graph),
        image = StandardGraph(result_list=result_list, log_scale=options['log_scale'], show_billing_line=True)
        image.write(graph)
        print 'done'

def do_version():
    print 'lightcount.py (svn-version)'


if __name__ == '__main__':
    import codecs, locale, os, sys
    # Replace stdout with an unbuffered recoder that uses the default locale
    try: sys.stdout = codecs.getwriter(locale.getdefaultlocale()[1])(os.fdopen(sys.stdout.fileno(), 'w', 0), 'replace')
    except: pass
    # Run main
    try:
        main(sys.argv[1:])
    except GetoptError, e:
        print >> sys.stderr, e 
        sys.exit(1)
    except KeyboardInterrupt:
        print >> sys.stderr, '\nInterrupted by user'
