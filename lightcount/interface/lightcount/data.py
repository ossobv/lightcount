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
from lightcount import bits
from lightcount.timeutil import *


class Data(object):
    ''' LightCount data reader. Reads data from the SQL database found in the supplied Config object. '''

    class Units(object):
        def __init__(self, conn):
            self.conn = conn
            self.cannodemap = {}
            self.humnodemap = {}
        def canonicalize_ip4(self, ip):
            try: ip = long(ip)
            except (TypeError, ValueError): ip = bits.inet_atol(ip)
            return ip, bits.inet_ltoa(ip)
        def canonicalize_net4(self, net):
            try: ip, mask = net.split('/')
            except ValueError: raise ValueError('Specify IPv4 net as ip/mask')
            ip, mask = bits.inet_atol(ip), long(mask)
            if mask > 32: raise ValueError('Netmask cannot be higher than 32 for IPv4 addresses')
            maskaway = ((1 << (32 - mask)) - 1)
            maskedip = ip & ~maskaway
            return maskedip, mask, '%s/%s' % (bits.inet_ltoa(ip), mask) #maskedip + maskaway
        def canonicalize_node(self, node):
            try: node_id = int(node)
            except (TypeError, ValueError):
                node = str(node)
                if node not in self.cannodemap:
                    cursor = self.conn.cursor()
                    cursor.execute('SELECT node_id FROM node_tbl WHERE node_name = %s', (node,))
                    self.cannodemap[node] = long(cursor.fetchone()[0])
                node_id = self.cannodemap[node]
            if node_id not in self.humnodemap:
                cursor = self.conn.cursor()
                cursor.execute('SELECT node_name FROM node_tbl WHERE node_id = %s', (node_id,))
                self.humnodemap[node_id] = cursor.fetchone()[0]
            return node_id, self.humnodemap[node_id]
        def canonicalize_vlan(self, vlan):
            return int(node), int(node)


    class ExpressionParser(object):
        def __init__(self, units):
            self.units = units
            self.parsere = re.compile(r'(?:(\(|\)|[^\s()]+)\s*)')

        def parse(self, expression):
            ''' Rewrites and expression like 'net 1.2.3.4/5 and not vlan 4' to the appropriate SQL. '''
            args, state, is_not, parens, query, human = self.parsere.findall(expression), None, None, 0, [], []

            for arg in args:
                lowarg = arg.lower()
                if state == None:
                    if lowarg == 'not': is_not = not is_not
                    elif lowarg in ('ip', 'net', 'node', 'vlan'): state = lowarg
                    elif lowarg == '(': query.append('(') ; human.append('(') ; parens += 1
                    else: assert False, 'Unexpected keyword %s' % arg
                elif state in ('ip', 'net', 'node', 'vlan'):
                    cmp_oper, cmp_name = (('=', ''), ('<>', 'not '))[bool(is_not)]
                    if state == 'ip':
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
                        query.append('vlan_id %s %s', (cmp_oper, vlan))
                        human.append('%svlan %s' % (cmp_name, humvlan))
                    state, is_not = 'oper', None
                elif state == 'oper':
                    if lowarg == ')': assert parens > 0, 'Uneven parentheses' ; query.append(')') ; human.append('(') ; parens -= 1
                    elif lowarg in ('and', 'or'): query.append(lowarg.upper()) ; human.append(lowarg) ; state = None
                    else: assert False, 'Unexpected keyword %s' % arg
                else:
                    assert False, 'Programming error'

            assert state is 'oper' and parens == 0 and is_not is None, 'Unexpected end of expression'
            return ' '.join(query), ' '.join(human)


    class Result(object):
        def __init__(self, conn, sql_query):
            self.conn = conn
            # FIXME


    def __init__(self, config):
        ''' Supply a Config object to get configuration from. '''
        self.conn = db.connect(
            host=config.storage_host,
            port=int(config.storage_port),
            user=config.storage_user,
            passwd=config.storage_pass,
            db=config.storage_dbase,
            connect_timeout=30
        )

        self.units = Data.Units(self.conn)
        self.expparser = Data.ExpressionParser(self.units)

    def get_raw_values(self, what, begin_date, end_date, query):
        ''' Get values written to database. Select only the 'what'-field, which can be ony of:
            'in_pps', 'in_bps', 'out_pps', 'out_bps', 'in_pps + out_pps' or 'in_bps + out_bps'.
            The begin_date and end_date must be datetime objects. Query may be empty.
            Use get_values instead of this. '''
        assert what in ('in_pps', 'in_bps', 'out_pps', 'out_bps', 'in_pps + out_pps', 'in_bps + out_bps')

        # Create query (MySQLdb does not like %i/%d... %s should work fine though)
        # Get "inclusive" end_date.. we want both fence posts on the graph.
        q = ['''SELECT unixtime, SUM(%s)
                FROM sample_tbl
                WHERE (%%(begin_date)s <= unixtime AND unixtime <= %%(end_date)s)''' % (what,)]
        d = {'begin_date': mktime(begin_date.timetuple()), 'end_date': mktime(end_date.timetuple())}

        # Add optional query restrictions
        if query != '':
            try:
                sql = self.expparser.parse(query)
            except Exception, e:
                raise Exception('Parse error: %s' % e)
            q.append('AND (%s)' % sql[0])
            print 'FIXME: supplied query (without date):', sql[1]

        # Add query order
        q.append('''GROUP BY unixtime ORDER BY unixtime''')

        # Execute query
        cursor = self.conn.cursor()
        cursor.execute(' '.join(q), d)
        return cursor.fetchall()

    def get_values(self, what, begin_date, end_date, sample_size=lightcount.INTERVAL_SECONDS, **kwargs):
        ''' Get values written to database with non-stored values set to zero. (When values are not in the DB,
            it means that they didn't do traffic. So zero is the correct value to return.)
            See get_raw_values for the arguments. Be aware that changing sample_size will flatten the graph. '''
        assert (sample_size % 300) == 0
        samples_divisor = float(sample_size / lightcount.INTERVAL_SECONDS) # want floating average
        begin_date_u, end_date_u = int(mktime(begin_date.timetuple())), int(mktime(end_date.timetuple()))
        assert (begin_date_u % sample_size) == 0

        # We can't predict lines in the future, compare times with now..
        # This will break when your time is not in sync >:-)
        now = time() - lightcount.INTERVAL_SECONDS

        # Init sampled_values (use "inclusive" end_date (+1))
        resampled_values = {}
        for date in range(begin_date_u, end_date_u + 1, sample_size):
            if date < now:
                resampled_values[date] = 0
            else:
                resampled_values[date] = None
        # Add values
        raw_values = self.get_raw_values(what, begin_date, end_date, **kwargs)
        for row in raw_values:
            while row[0] >= begin_date_u + sample_size:
                begin_date_u += sample_size
            if resampled_values[begin_date_u] != None: # Can happen when time is out of sync...
                resampled_values[begin_date_u] += long(row[1])
        # Average values
        if samples_divisor != 1:
            for key in resampled_values:
                resampled_values[key] /= samples_divisor

        return resampled_values

    def get_values_name(self, query):
        import random
        return 'FIXME %i' % random.randint(1, 200)
        x = '''
        node = self.humanize_node(node)
        vlan = self.humanize_vlan(vlan)
        ip = self.humanize_ip(ip)

        if ip != None:
            name = ip
            if vlan != None: 
                name += ' with vlan# %s' % (vlan,)
            if node != None:
                name += ' MON %s' % (node,)
        elif vlan != None:
            name = 'vlan# %s' % (vlan,)
            if node != None:
                name += ' MON %s' % (node,)
        elif node != None:
            name = 'MON %s' % (node,)
        else:
            name = 'everything'
        return name
        '''

    def calculate_percentile(self, nth_percentile, what, begin_date, end_date, query):
        ''' Calculate the Nth percentile over the provided period. Usually ISPs use 95 as the percentile
            and a full month as the sampling period. '''
        assert nth_percentile > 0 and nth_percentile <= 100
        assert what in ('in_bps', 'out_bps')

        # Don't use inclusive values for end_date here
        q = ['''SELECT SUM(%(what)s)
                FROM sample_tbl
                WHERE (%%(begin_date)s <= unixtime AND unixtime < %%(end_date)s)'''  % {'what': what}]
        d = {'begin_date': mktime(begin_date.timetuple()), 'end_date': mktime(end_date.timetuple())}

        # Add optional query restrictions
        if query != '':
            try:
                sql = self.expparser.parse(query)
            except Exception, e:
                raise Exception('Parse error: %s' % e)
            q.append('AND (%s)' % sql[0])
            print 'FIXME: supplied query (without date):', sql[1]

        # Add order by clause
        q.append('''GROUP BY unixtime ORDER BY SUM(%(what)s)''' % {'what': what})

        # Run query
        cursor = self.conn.cursor()
        cursor.execute(' '.join(q), d)

        # Take 95th entry
        period = mktime(end_date.timetuple()) - mktime(begin_date.timetuple())
        sample_size = lightcount.INTERVAL_SECONDS
        sample_count = int(round(period / sample_size)) # should be a nice int (except for leap secs?)
        real_count = cursor.rowcount # real_count <= sample_count because we might not see some 0 values
        sample95 = int(math.ceil(sample_count * float(nth_percentile) / 100.0) - 1) + real_count - sample_count
        if sample95 < 0:
            return 0
        
        cursor.scroll(sample95)
        value = long(cursor.fetchone()[0])
        return value

    def calculate_billing_value(self, month_date, **kwargs):
        ''' Calculate the 95th percentile over the provided period. Use the highest of the two
            (inbound and outbound) values. Keyword arguments are the same as get_raw_values takes. '''
        begin_date = datetime(month_date.year, month_date.month, 1, tzinfo=month_date.tzinfo)
        end_date = datetime.fromtimestamp(mktime((month_date.year, month_date.month + 1, 1, 0, 0, 0, -1, -1, -1)), month_date.tzinfo)
        valin = self.calculate_percentile(95, 'in_bps', begin_date, end_date, **kwargs)
        valout = self.calculate_percentile(95, 'out_bps', begin_date, end_date, **kwargs)
        print 'FIXME: 95th p is: max(%s, %s) => %s' % (valin, valout, max(valin, valout))
        return begin_date, end_date, max(valin, valout)
