# vim: set ts=8 sw=4 sts=4 et:
import MySQLdb as db, lightcount, math
from lightcount import bits
from lightcount.timeutil import *


class Data(object):
    ''' LightCount data reader. Reads data from the SQL database found in the supplied Config object. '''

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

    def get_nodes(self):
        ''' Get all available nodes from the database. '''
        cursor = self.conn.cursor()
        cursor.execute('SELECT node_id, node_name FROM node_tbl ORDER BY node_name')
        ret = {}
        for row in cursor.fetchall():
            ret[int(row[0])] = row[1]
        return ret
    
    def get_raw_values(self, what, begin_date, end_date, node_id=None, vlan_id=None, ip=None):
        ''' Get values written to database. Select only the 'what'-field, which can be ony of:
            'in_pps', 'in_bps', 'out_pps', 'out_bps', 'in_pps + out_pps' or 'in_bps + out_bps'.
            The begin_date and end_date must be datetime objects. node_id, vlan_id and ip are
            optional. Use get_values instead of this. '''
        assert what in ('in_pps', 'in_bps', 'out_pps', 'out_bps', 'in_pps + out_pps', 'in_bps + out_bps')

        # Create query (MySQLdb does not like %i/%d... %s should work fine though)
        # Get "inclusive" end_date.. we want both fence posts on the graph.
        q = ['''SELECT unixtime, SUM(%s)
                FROM sample_tbl
                WHERE %%(begin_date)s <= unixtime AND unixtime <= %%(end_date)s''' % (what,)]
        d = {'begin_date': mktime(begin_date.timetuple()), 'end_date': mktime(end_date.timetuple())}

        # Add optional query restrictions
        ip = ip and bits.inet_atol(ip) # ip string to numeric
        for (id, name) in ((node_id, 'node_id'), (vlan_id, 'vlan_id'), (ip, 'ip')):
            if id != None:
                q.append('AND %(name)s = %%(%(name)s)s' % {'name': name})
                d[name] = long(id)

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

    def get_values_name(self, node_id=None, vlan_id=None, ip=None):
        if ip != None:
            name = str(ip)
            if vlan_id != None: 
                name += ' with vlan# %u' % (vlan_id,)
            if node_id != None:
                name += ' MON %s (%u)' % (self.get_nodes()[node_id], node_id)
        elif vlan_id != None:
            name = 'vlan# %u' % (vlan_id,)
            if node_id != None:
                name += ' MON %s (%u)' % (self.get_nodes()[node_id], node_id)
        elif node_id != None:
            name = 'MON %s (%u)' % (self.get_nodes()[node_id], node_id)
        else:
            name = 'everything'
        return name

    def calculate_percentile(self, nth_percentile, what, begin_date, end_date, **kwargs):
        ''' Calculate the Nth percentile over the provided period. Usually ISPs use 95 as the percentile
            and a full month as the sampling period. '''
        assert nth_percentile > 0 and nth_percentile < 100
        values = self.get_values(what, begin_date, end_date, **kwargs)
        values = values.values()
        values.sort()

        # Remove all 'None'-values from the future
        try:
            while True:
                values.remove(None)
        except:
            pass

        return values[int(math.ceil(len(values) / 100.0 * float(nth_percentile))) - 1]

    def calculate_billing_value(self, month_date, **kwargs):
        ''' Calculate the 95th percentile over the provided period. Use the highest of the two
            (inbound and outbound) values. Keyword arguments are the same as get_raw_values takes. '''
        begin_date = datetime(month_date.year, month_date.month, 1, tzinfo=month_date.tzinfo)
        end_date = datetime.fromtimestamp(mktime((month_date.year, month_date.month + 1, 1, 0, 0, 0, -1, -1, -1)) - 1, month_date.tzinfo)
        return max(
            self.calculate_percentile(95, 'in_bps', begin_date, end_date, **kwargs),
            self.calculate_percentile(95, 'out_bps', begin_date, end_date, **kwargs)
        )

