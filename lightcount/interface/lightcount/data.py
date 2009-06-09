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
import MySQLdb as db, lightcount, math, re
from _mysql_exceptions import ProgrammingError
from lightcount import bits
from lightcount.timeutil import *


def mpl_range(begin_date, end_date, interval):
    ''' Does what matplotlib.dates.drange does but does not choke on daylight saving. '''
    from matplotlib.dates import date2num
    timezone = begin_date.tzinfo
    beginsec, endsec = int(mktime(begin_date.timetuple())), int(mktime(end_date.timetuple()))
    intervalsecs = interval.days * 86400 + interval.seconds
    ret = []
    for i in range(beginsec, endsec, intervalsecs):
        ret.append(date2num(datetime.fromtimestamp(i)))
    return ret


class Data(object):
    ''' LightCount data reader. Reads data from the SQL database found in the supplied Config object. '''

    class Storage(object):
        ''' Minor database abstraction. '''
        def __init__(self, type, host, port, user, passwd, dbase):
            assert type == 'my', 'Only MySQL storage support is implemented'
            self.conn = db.connect(host=host, port=int(port), user=user, passwd=passwd, db=dbase, connect_timeout=30)
        def execute(self, *args, **kwargs):
            cursor = self.conn.cursor()
            try:
                cursor.execute(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit):
                # Catch a programming error ;)
                try: cursor.close()
                except ProgrammingError: cursor.connection = None
                raise
            return cursor
        def fetch_all(self, *args, **kwargs):
            cursor = self.execute(*args, **kwargs)
            return cursor.fetchall()
        def fetch_atom(self, *args, **kwargs):
            row = self.fetch_atom_row(*args, **kwargs)
            assert len(row) == 1, 'Now exactly one column was returned'
            return row[0]
        def fetch_atom_row(self, *args, **kwargs):
            cursor = self.execute(*args, **kwargs)
            assert cursor.rowcount == 1 or cursor.rowcount == -1, 'Not exactly one row was returned'
            return cursor.fetchone()


    class Units(object):
        ''' Conversion to and from internal units. '''
        def __init__(self, storage):
            self.storage = storage
            self.cannodemap = {}
            self.humnodemap = {}
        def canonicalize_host4(self, host):
            from socket import getaddrinfo, gethostbyaddr, gaierror, herror, AF_INET, SOCK_RAW
            try:
                ips = getaddrinfo(host, None, AF_INET, 0) # AI_CANONNAME does not work :(
                ip4 = ips[0][4][0]
                try: rev = gethostbyaddr(ip4)[0]
                except herror: rev = self.canonicalize_ip4(host4)[1]
            except gaierror:
                return self.canonicalize_ip4(host)
            return bits.inet_atol(ip4), rev
        def canonicalize_ip4(self, ip):
            try: ip = long(ip)
            except (TypeError, ValueError): ip = bits.inet_atol(ip)
            return ip, bits.inet_ltoa(ip)
        def canonicalize_net4(self, net):
            try: ip, mask = net.split('/')
            except ValueError: raise ValueError('Specify IPv4 net as ip/mask')
            ip, mask = bits.inet_atol(ip), long(mask)
            if mask > 32: raise ValueError('Netmask cannot be higher than 32 for IPv4 addresses')
            maskkeep = ~((1 << (32 - mask)) - 1) & 0xffffffff
            maskedip = ip & maskkeep
            return maskedip, maskkeep, '%s/%s' % (bits.inet_ltoa(maskedip), mask) #maskedip + maskaway
        def canonicalize_node(self, node):
            try: node_id = int(node)
            except (TypeError, ValueError):
                node = str(node)
                if node not in self.cannodemap:
                    self.cannodemap[node] = long(self.storage.fetch_atom('SELECT node_id FROM node_tbl WHERE node_name = %s', (node,)))
                node_id = self.cannodemap[node]
            if node_id not in self.humnodemap:
                self.humnodemap[node_id] = self.storage.fetch_atom('SELECT node_name FROM node_tbl WHERE node_id = %s', (node_id,))
            return node_id, self.humnodemap[node_id]
        def canonicalize_vlan(self, vlan):
            return int(vlan), int(vlan)


    class ExpressionParser(object):
        ''' Parser for the custom queries (restrictions) on specific ip's, nets, nodes and vlans. '''
        def __init__(self, units):
            self.units = units
            self.parsere = re.compile(r'(?:(\(|\)|[^\s()]+)\s*)')

        def parse(self, expression):
            ''' Rewrites an expression like 'net 1.2.3.4/5 and not vlan 4' to the appropriate SQL. '''
            if expression == '':
                return None, 'everything'
    
            args, state, is_not, parens, query, human = self.parsere.findall(expression), None, None, 0, [], []

            for arg in args:
                lowarg = arg.lower()
                if state == None:
                    if lowarg == 'not': is_not = not is_not
                    elif lowarg in ('host', 'ip', 'net', 'node', 'vlan'): state = lowarg
                    elif lowarg == '(': query.append('(') ; human.append('(') ; parens += 1
                    else: assert False, 'Unexpected keyword %s' % arg
                elif state in ('host', 'ip', 'net', 'node', 'vlan'):
                    cmp_oper, cmp_name = (('=', ''), ('<>', 'not '))[bool(is_not)]
                    if state == 'host':
                        ip, humhost = self.units.canonicalize_host4(arg)
                        query.append('ip %s %s' % (cmp_oper, ip))
                        human.append('%shost %s' % (cmp_name, humhost))
                    elif state == 'ip':
                        ip, humip = self.units.canonicalize_ip4(arg)
                        query.append('ip %s %s' % (cmp_oper, ip))
                        human.append('%sip %s' % (cmp_name, humip))
                    elif state == 'net':
                        ip, mask, humipmask = self.units.canonicalize_net4(arg)
                        query.append('(ip & %s) %s %s' % (mask, cmp_oper, ip))
                        human.append('%snet %s' % (cmp_name, humipmask))
                    elif state == 'node':
                        node, humnode = self.units.canonicalize_node(arg)
                        query.append('node_id %s %s' % (cmp_oper, node))
                        human.append('%snode %s' % (cmp_name, humnode))
                    elif state == 'vlan':
                        vlan, humvlan = self.units.canonicalize_vlan(arg)
                        query.append('vlan_id %s %s' % (cmp_oper, vlan))
                        human.append('%svlan %s' % (cmp_name, humvlan))
                    state, is_not = 'oper', None
                elif state == 'oper':
                    if lowarg == ')': assert parens > 0, 'Uneven parentheses' ; query.append(')') ; human.append(')') ; parens -= 1
                    elif lowarg in ('and', 'or'): query.append(lowarg.upper()) ; human.append(lowarg) ; state = None
                    else: assert False, 'Unexpected keyword %s' % arg
                else:
                    assert False, 'Programming error'

            assert state is 'oper' and parens == 0 and is_not is None, 'Unexpected end of expression'
            return ' '.join(query), ' '.join(human)


    class Period(object):
        def __init__(self, begin_date=None, end_date=None, period=None, time_zone=None):
            if time_zone == None:
                time_zone = timezone_default()
            if begin_date is not None and 'timetuple' not in dir(begin_date):
                begin_date = parse_datetime(begin_date, time_zone)
            if end_date is not None and 'timetuple' not in dir(end_date):
                end_date = parse_datetime(end_date, time_zone)
            
            # We can't have all three values set
            none_count = len([n for n in (begin_date, end_date, period) if n is None])
            assert none_count >= 1, 'Only two of begin_date/end_date/period may be set.'
            # Set at least two
            while none_count > 1:
                if period is None: period = 'month' ; none_count -= 1
                elif end_date is None: end_date = datetime.now(time_zone) ; none_count -= 1 ; assert none_count == 1
        
            self.time_zone = time_zone
            self.period = period
            self.begin_date, self.end_date = datetimes_from_datetime_and_period(begin_date, end_date, period)
            self.now = datetime.now(time_zone)
        def canonical_begin_date(self):
            return long(mktime(self.begin_date.timetuple()))
        def canonical_end_date(self):
            return long(mktime(self.end_date.timetuple()))
        def canonical_now(self):
            return long(mktime(self.now.timetuple()))
        def get_begin_date(self):
            return self.begin_date
        def get_end_date(self):
            return self.end_date
        def get_now(self):
            return self.now
        def get_period(self):
            return self.period
        def get_interval(self):
            return self.canonical_end_date() - self.canonical_begin_date()
        def get_tzinfo(self):
            return self.begin_date.tzinfo
        def get_sample_times(self):
            return range(self.canonical_begin_date(), self.canonical_end_date() + 1, lightcount.INTERVAL_SECONDS)
        def get_mpl_sample_times(self):
            return mpl_range(self.begin_date, self.end_date + timedelta(seconds=1), timedelta(seconds=lightcount.INTERVAL_SECONDS))
        def __str__(self):
            return '<period (%s) between %s and %s>' % (self.period, self.begin_date, self.end_date)

            
    class Result(object):
        def __init__(self, storage, expression_parser, query, period): # append calc_95p option here
            self.storage = storage
            self.query, self.human_query = expression_parser.parse(query)
            self.period = period
            self.values = None
            self.billing_percentile = 95
            self.cache = {}
        def get_period(self):
            return self.period
        def load_values(self):
            if self.values is None:
                self.values = self.get_values_from_db()
        def get_values_from_db(self):
            ''' Get values from database. '''
            # Create query (MySQLdb does not like %i/%d... %s should work fine though)
            # Get "inclusive" end_date.. we want both fence posts on the graph.
            q = ['''SELECT unixtime, SUM(in_pps), SUM(out_pps), SUM(in_bps), SUM(out_bps)
                    FROM sample_tbl
                    WHERE (%(begin_date)s <= unixtime AND unixtime <= %(end_date)s)''']
            d = {'begin_date': self.period.canonical_begin_date(), 'end_date': self.period.canonical_end_date()}
            # Add optional query restrictions
            if self.query != None:
                q.append('AND (%s)' % self.query)
            # Add query order
            q.append('''GROUP BY unixtime ORDER BY unixtime''')
            # Execute query
            values = self.storage.fetch_all(' '.join(q), d)
            #print '\n(', re.sub(r'\s+', ' ', ' '.join(q) % d), ' -- ', self.human_query, ')\n'
            # Make sure every sample in the period interval exists (0 if not found)
            now = time() - lightcount.INTERVAL_SECONDS # can't predict data in future
            new_values = [
                (long(t), (0L, None)[t >= now], (0L, None)[t >= now], (0L, None)[t >= now], (0L, None)[t >= now])
                for t in self.period.get_sample_times()
            ]
            i = 0
            for t, in_pps, out_pps, in_bps, out_bps in values:
                while new_values[i][0] < t: i += 1
                assert new_values[i][0] == t
                new_values[i] = (long(t), long(in_pps), long(out_pps), long(in_bps), long(out_bps))
            # Return the values
            return new_values

        def get_times(self):
            if 'times' not in self.cache:
                self.load_values()
                self.cache['times'] = tuple([t for t, _, _, _, _ in self.values])
            return self.cache['times']

        def get_in_bps(self):
            if 'in_bps' not in self.cache:
                self.load_values()
                in_bps = [i for t, _, _, i, o in self.values]
                for i in range(len(in_bps)):
                    if in_bps[i] is not None: in_bps[i] <<= 3 # bits => *8
                self.cache['in_bps'] = tuple(in_bps)
            return self.cache['in_bps']
        def get_out_bps(self):
            if 'out_bps' not in self.cache:
                self.load_values()
                out_bps = [o for t, _, _, i, o in self.values]
                for i in range(len(out_bps)):
                    if out_bps[i] is not None: out_bps[i] <<= 3 # bits => *8
                self.cache['out_bps'] = tuple(out_bps)
            return self.cache['out_bps']
        def get_io_bps(self):
            if 'io_bps' not in self.cache:
                self.load_values()
                io_bps = []
                input, output = self.get_in_bps(), self.get_out_bps()
                for i in range(len(input)):
                    if input[i] is None or output[i] is None: io_bps.append(None)
                    else: io_bps.append(input[i] + output[i])
                self.cache['io_bps'] = tuple(io_bps)
            return self.cache['io_bps']

        def get_in_pps(self):
            if 'in_pps' not in self.cache:
                self.load_values()
                self.cache['in_pps'] = tuple([i for t, i, o, _, _ in self.values])
            return self.cache['in_pps']
        def get_out_pps(self):
            if 'out_pps' not in self.cache:
                self.load_values()
                self.cache['out_pps'] = tuple([o for t, i, o, _, _ in self.values])
            return self.cache['out_pps']
        def get_io_pps(self):
            if 'io_pps' not in self.cache:
                self.load_values()
                io_pps = []
                input, output = self.get_in_pps(), self.get_out_pps()
                for i in range(len(input)):
                    if input[i] is None or output[i] is None: io_pps.append(None)
                    else: io_pps.append(input[i] + output[i])
                self.cache['io_pps'] = tuple(io_pps)
            return self.cache['io_pps']

        def get_max_io_bps(self):
            io_bps = max(self.get_io_bps())
            self.load_values()
            for t, _, _, i, o in self.values:
                if (i + o) << 3 == io_bps:
                    return datetime.fromtimestamp(t, self.period.get_tzinfo()), i << 3, o << 3
            assert False, 'Programming error'
        def get_max_io_pps(self):
            io_pps = max(self.get_io_pps())
            self.load_values()
            for t, i, o, _, _ in self.values:
                if i + o == io_pps:
                    return datetime.fromtimestamp(t, self.period.get_tzinfo()), i, o
            assert False, 'Programming error'
            
        def get_billing_values(self):
            if self.period.get_period() != 'month': return None
            if 'billing_value' not in self.cache:
                self.load_values()

                estimate = self.period.get_end_date() > self.period.get_now()

                results = [] # holds in/out
                for y in (list(self.get_in_bps()), list(self.get_out_bps())):
                    if not estimate:
                        # drop fencepost for next month
                        y.pop()
                    else:
                        # drop all future values
                        for i in range(self.period.canonical_now(), self.period.canonical_end_date(), lightcount.INTERVAL_SECONDS):
                            y.pop()
                    y.sort()
                    results.append(y)

                sample95 = int(math.ceil(len(results[0]) * float(self.billing_percentile) / 100.0) - 1)
                yin95, yout95 = results[0][sample95], results[1][sample95]
                if yin95 is None: yin95 = 0L
                if yout95 is None: yout95 = 0L
                self.cache['billing_value'] = (yin95, yout95, estimate)
            return self.cache['billing_value']

        def __str__(self):
            return '<result for query \'%s\' over period %s>' % (self.human_query, self.period)


    def __init__(self, config):
        ''' Supply a Config object to get configuration from. '''
        self.storage = Data.Storage('my', config.storage_host, config.storage_port, config.storage_user, config.storage_pass, config.storage_dbase)
        self.units = Data.Units(self.storage)
        self.expparser = Data.ExpressionParser(self.units)

    def parse_period(self, begin_date=None, end_date=None, period=None, time_zone=None):
        return Data.Period(begin_date=begin_date, end_date=end_date, period=period, time_zone=time_zone)

    def parse_queries(self, period, queries=None):
        queries = queries or ['']
        result_list = []
        for query in queries:
            result_list.append(Data.Result(self.storage, self.expparser, query, period))
        return result_list

    def serialize(self, result, dest_file, progress_callback=None):
        where = ''
        if result.query: where = 'AND (%s)' % result.query

        # We do node_id => node_name and ip => dotted-ip conversion in python
        # to save bandwidth and sql resources
        query = '''
            SELECT unixtime, node_id, vlan_id, ip, in_pps, in_bps, out_pps, out_bps
            FROM sample_tbl
            WHERE (%%(begin_date)s <= unixtime AND unixtime < %%(end_date)s) %s
            ORDER BY unixtime, ip, vlan_id, node_id
        ''' % where

        begin_date = result.get_period().canonical_begin_date()
        end_date = result.get_period().canonical_end_date()
        seconds_at_a_time = 3 * 3600

        # Use a smaller period and several queries to get our results
        dest_file.write('unixtime,node,vlan,ip,in_pps,in_bps,out_pps,out_bps\n')
        for date in range(begin_date, end_date, seconds_at_a_time): # [begin_date, end_date)
            if progress_callback:
                progress_callback(date - begin_date, end_date - begin_date)
            for row in self.storage.fetch_all(query, {'begin_date': date, 'end_date': min(end_date, date + seconds_at_a_time)}):
                dest_file.write('%d,"%s",%d,"%s",%d,%d,%d,%d\n' % (
                    row[0],
                    self.units.canonicalize_node(row[1])[1].replace('"', '""'),
                    row[2],
                    self.units.canonicalize_ip4(row[3])[1].replace('"', '""'),
                    row[4], row[5], row[6], row[7]
                ))
        if progress_callback:
            progress_callback(end_date - begin_date, end_date - begin_date)
