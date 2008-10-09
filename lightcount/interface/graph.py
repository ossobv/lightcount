#!/usr/bin/env python
# vim: set ts=8 sw=4 sts=4 et:
            
if __name__ == '__main__':
    import sys
    from lightcount import Config
    from lightcount.timeutil import *
    from lightcount.data import Data
    from lightcount.graph import StandardGraph, GraphParameters
    from getopt import gnu_getopt as getopt, GetoptError
    graph_parameters = GraphParameters()
    scratchpad = {'date': {}}

    optlist, args = getopt(
        sys.argv[1:],
        'c:i:n:v:o:t:z:h',
        ('config-file=', 'ip=', 'node=', 'vlan=', 'output-file=', 'period=', 'begin-date=', 'end-date=', 'time-zone=', 'log', 'linear', 'help', 'version')
    )

    for key, val in optlist:
        if key in ('-c', '--config-file'):
            if 'config_file' in scratchpad:
                raise GetoptError('Configuration file name already specified!')
            scratchpad['config_file'] = val
        elif key in ('-i', '--ip'):
            graph_parameters.ips.append(val)
        elif key in ('-n', '--node'):
            graph_parameters.node_ids.append(int(val))
        elif key in ('-v', '--vlan'):
            graph_parameters.vlan_ids.append(int(val))
        elif key in ('-o', '--output-file'):
            if 'output_file' in scratchpad:
                raise GetoptError('Output file name already specified!')
            scratchpad['output_file'] = val
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
            if val not in periods():
                raise GetoptError('Specify one of %s as period.' % (', '.join(periods())))
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
            if 'logarithmic_scale' in scratchpad:
                raise GetoptError('Specify either --linear or --log and do it once.')
            scratchpad['logarithmic_scale'] = key == '--log'
        elif key in ('-h', '--help'):
            print '''Usage: graph.py OPTIONS
Draws a graph from the lightcount data.

File selection:
  -c, --config-file=F   read config file F (dfl: lightcount.conf)
  -o, --output-file=F   write output png as F (dfl: graph.png)

Period selection:
  -t, --period=P        period P: %(Ps)s (dfl: month)
      --begin-date=D    the begin date D as YYYY-mm-dd
      --end-date=D      the end date D as YYYY-mm-dd (dfl: now)
  -z, --time-zone=Z     use time zone name Z (dfl: %(Z)s)

Value selection:
  -n, --node=N          node_id N (may be specified multiple times)
  -v, --vlan=I          vlan_id V (may be specified multiple times)
  -i, --ip=I            IP address I (may be specified multiple times)

Graph options:
      --linear          display the graph with a linear scale (default)
      --log             display the graph with a logarithmic scale
''' % {'Ps': ', '.join(periods()), 'Z': timezone_default()}
            sys.exit(0)
        elif key == '--version':
            print 'chart.py v0.1'
        else:
            assert False

    # Check invalid options
    if len(args) != 0:
        raise GetoptError('This program does not take non-option arguments.')
    if len(scratchpad['date']) == 3:
        raise GetoptError('Specify either one date and a period, or two dates.')
        
    # Set defaults
    if 'config_file' not in scratchpad:
        scratchpad['config_file'] = 'lightcount.conf'
    if 'output_file' not in scratchpad:
        scratchpad['output_file'] = 'graph.png'
    if 'logarithmic_scale' not in scratchpad:
        scratchpad['logarithmic_scale'] = False
    if 'time_zone' not in scratchpad:
        scratchpad['time_zone'] = timezone_default()
    for name in ('begin_date', 'end_date'):
        if name in scratchpad['date']:
            scratchpad['date'][name] = parse_datetime(scratchpad['date'][name], scratchpad['time_zone'])
    while len(scratchpad['date']) < 2:
        if not 'period' in scratchpad['date']:
            scratchpad['date']['period'] = 'month'
        elif not 'end_date' in scratchpad['date']:
            scratchpad['date']['end_date'] = datetime.now(scratchpad['time_zone'])
    for name in ('begin_date', 'end_date', 'period'):
        if name not in scratchpad['date']:
            scratchpad['date'][name] = None
        
    # Set graph parameters
    graph_parameters.time_zone = scratchpad['time_zone']
    graph_parameters.logarithmic_scale = scratchpad['logarithmic_scale']
    graph_parameters.begin_date, graph_parameters.end_date = datetimes_from_datetime_and_period(
        begin_date=scratchpad['date']['begin_date'],
        end_date=scratchpad['date']['end_date'],
        period=scratchpad['date']['period']
    )

    # Print validated values
    graph_parameters.validate()
    print 'Begin date:', graph_parameters.begin_date
    print 'End date:', graph_parameters.end_date
    print 'Period:', graph_parameters.date_diff
    print 'Logarithmic scale:', graph_parameters.logarithmic_scale

    # Write the graph to file
    graph = StandardGraph(Data(Config(scratchpad['config_file'])), graph_parameters)
    print ' ... writing', scratchpad['output_file']
    graph.write(scratchpad['output_file'])

