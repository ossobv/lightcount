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
from lightcount import bits, graphutil
from lightcount.timeutil import *
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import date2num


if not 'drange' in dir():
    def drange(begin_date, end_date, interval):
        ''' Does what matplotlib.dates.drange does but does not choke on daylight saving. '''
        tz = begin_date.tzinfo
        bu, eu = int(mktime(begin_date.timetuple())), int(mktime(end_date.timetuple()))
        ival = interval.days * 86400 + interval.seconds
        ret = []
        for i in range(bu, eu, ival):
            ret.append(date2num(datetime.fromtimestamp(i)))
        return ret



class StandardGraph:
    ''' A graphical representation of the data. The graph_parameters object defines what to show. '''    

    def __init__(self, data, graph_parameters):
        ''' Pass a valid data object and graph_parameters. The graph_parameters get validate()ed before use. '''
        graph_parameters.validate()
        self.data = data
        self.params = graph_parameters

    def __create_figure(self):
        def plot_lines(ax, xvalues, lines):
            ''' Draw lines from lines parameter on the graph. '''
            for line in lines:
                # If we're in log-mode, we can't draw on 0, so we change that to 1.
                if ax.get_yscale() == 'log':
                    yvalues = line['yvalues'][:]
                    for i, y in enumerate(yvalues):
                        if y == 0:
                            yvalues[i] = 1
                else:
                    yvalues = line['yvalues']
                # Draw the line, unless there are only None-valus
                if len(set(yvalues) - set((None,))) != 0:
                    ax.plot(
                        xvalues,
                        yvalues, color=line['color'],
                        linewidth=2.00,
                        alpha=0.5,
                        label=line['name']
                    )

            # Draw 95th percentile line if we only show one IN/OUT graph
            if self.params.only_one_value_source:
                billing_begin, billing_end, billing_value = self.data.calculate_billing_value(
                    self.params.begin_date, 
                    node_id=self.params.node_ids[0],
                    vlan_id=self.params.vlan_ids[0],
                    ip=self.params.ips[0]
                )
                xbegin = max(xvalues[0], date2num(billing_begin))
                xend = min(xvalues[-1], date2num(billing_end))

                label = '95th P is at %s' % (graphutil.BitsPerSecondFormatter()(billing_value),)
                if ax.get_yscale() == 'log' and billing_value == 0:
                    billing_value = 1
                ax.plot((xbegin, xend), (billing_value, billing_value), color='#ff0000', linewidth='1.00', label=label)

        def format_x_axis(ax):
            ''' Draw vertical lines and line identifiers. '''
            if self.params.date_diff <= 43200:
                loc = graphutil.MinuteLocator(byminute=(0, 30), tz=self.params.begin_date.tzinfo)
                fmt = graphutil.DateFormatter('%H:%M %z', tz=self.params.begin_date.tzinfo)
            elif self.params.date_diff <= 90000:
                loc = graphutil.HourLocator(interval=2, tz=self.params.time_zone)
                fmt = graphutil.DateFormatter('%Hh', tz=self.params.begin_date.tzinfo)
            elif self.params.date_diff <= 7 * 86400:
                loc = graphutil.HourLocator(interval=24)
                fmt = graphutil.DateFormatter('%d/%m', tz=self.params.begin_date.tzinfo)
            elif self.params.date_diff <= 50 * 86400:
                loc = graphutil.WeekdayLocator(graphutil.MONDAY)
                fmt = graphutil.DateFormatter('%a %d %b', tz=self.params.begin_date.tzinfo)
            else:
                loc = graphutil.MonthLocator()
                fmt = graphutil.DateFormatter('%b \'%y', tz=self.params.begin_date.tzinfo)
            ax.xaxis.set_major_locator(loc)
            ax.xaxis.set_major_formatter(fmt)
            ax.xaxis.set_ticks_position('top')
            ax.set_xlim(xmin=date2num(self.params.begin_date), xmax=date2num(self.params.end_date))
            for label in ax.get_xticklabels():
                label.set_fontsize(10)
            for tick in ax.yaxis.get_major_ticks():
                tick.set_pad(10)

        def format_y_axis(ax):
            ''' Draw horizontal lines and line identifiers. '''
            # Set limits to be at least a range (else the line would be centered)
            # Note! In the future intervaly might become a 2tuple-property.
            ymin, ymax = ax.dataLim.intervaly().get_bounds()
            # Use base2 loglocator on logarithmic output
            if ax.get_yscale() == 'log':
                if ymax == 1:
                    ax.set_ylim(ymin=1, ymax=8)
                ax.yaxis.set_major_locator(graphutil.LogBitsLocator())
                ax.yaxis.set_minor_locator(graphutil.LogBitsLocator(minor=True))
            # Try to find a suitable multiplier for multiplelocator
            else:
                if ymax == 0:
                    ax.set_ylim(ymin=0, ymax=8)
                ax.yaxis.set_major_locator(graphutil.LinearBitsLocator(peak=ymax))
                ax.yaxis.set_minor_locator(graphutil.LinearBitsLocator(peak=ymax, minor=True))
            ax.yaxis.set_major_formatter(graphutil.BitsPerSecondFormatter()) 
            ax.yaxis.set_ticks_position('right')
            for label in ax.get_yticklabels():
                label.set_fontsize(10)
                label.set_color('#007700')
            for tick in ax.xaxis.get_major_ticks():
                tick.set_pad(10)

        def format_legend(ax):
            ''' Create a legend from the labeled lines. '''
            legend = ax.legend(loc='upper left')
            legend.draw_frame(True)
            for text in legend.get_texts():
                text.set_fontsize(10)


        # Initialize figure
        fig = Figure(
            figsize=(self.params.width / self.params.dpi, self.params.height / self.params.dpi),
            dpi=self.params.dpi
        )
        canvas = FigureCanvas(fig)
        ax = fig.add_axes([4 / self.params.dpi, 4 / self.params.dpi, 60 / self.params.dpi, 60 / self.params.dpi], frame_on=False)

        # Select log/normal scale
        if self.params.logarithmic_scale:
            ax.set_yscale('log')

        # Draw lines, axes, legend and grid
        plot_lines(
            ax,
            drange(
                self.params.begin_date,
                self.params.end_date + timedelta(seconds=1), # +1 to get "inclusive" end_date
                timedelta(seconds=self.params.sample_size)
            ),
            self.__params_to_lines()
        )
        format_x_axis(ax)
        format_y_axis(ax)
        format_legend(ax)
        ax.grid(True, color='#cccccc')
        
        # It is done
        return fig

    def __params_to_lines(self):
        def get_data(what, node_id, vlan_id, ip, keys):
            # Get the I/O values
            values = self.data.get_values(
                what,
                self.params.begin_date, self.params.end_date, self.params.sample_size,
                node_id=node_id, vlan_id=vlan_id, ip=ip
            )
            # Convert to fig-values
            if len(keys) == 0:
                keys.extend(values.keys())
                keys.sort()
            yvalues = []
            for key in keys:
                if values[key] != None:
                    yvalues.append(values[key] * 8) # *8 to get bits
                else:
                    yvalues.append(None)
            # Get name
            return yvalues

        # Keys are the same for each line
        keys = []
        # The list of lines
        lines = []

        # If no or only one of IP/node/vlan is specified, we can show both input and output in the same graph.
        if self.params.only_one_value_source:
            assert len(self.params.ips) == 1 and len(self.params.node_ids) == 1 and len(self.params.vlan_ids) == 1
            colors = ['#008800', '#000088']
            name = self.data.get_values_name(node_id=self.params.node_ids[0], vlan_id=self.params.vlan_ids[0], ip=self.params.ips[0])
            for what, name_suffix in (('in_bps', ' IN'), ('out_bps', ' OUT')):
                lines.append({
                    'name': name + name_suffix,
                    'color': colors[len(lines)],
                    'yvalues': get_data(what, self.params.node_ids[0], self.params.vlan_ids[0], self.params.ips[0], keys),
                })
        # .. else, show multiple lines
        else:
            colors = ['#383838','#90ae61','#ffb400','#e70a8c','#00a2d0']
            for node_id in self.params.node_ids:
                for vlan_id in self.params.vlan_ids:
                    for ip in self.params.ips:
                        name = self.data.get_values_name(node_id=node_id, vlan_id=vlan_id, ip=ip)
                        lines.append({
                            'name': name,
                            'color': colors[len(lines) < len(colors) and len(lines) or 0],
                            'yvalues': get_data('in_bps + out_bps', node_id, vlan_id, ip, keys),
                        })
        # Return all lines
        return lines

    def output():
        ''' Return the image data as binary png data. '''
        import os
        tmpfile = os.tmpfile()
        self.write(tmpfile)
        tmpfile.seek(0)
        return tmpfile.read()

    def write(self, filename):
        ''' Write the image to filename on the local file system. '''
        f = self.__create_figure()
        f.savefig(filename, dpi=self.params.dpi)



class GraphParameters:
    ''' Chart generation parameters/options. Modify/append to the parameters to customize the
        generated graph. '''

    def __init__(self):
        ''' Does not take any arguments. Modify the following parameters of the constructed object:
            width, height, begin_date, end_date, ips, node_ids and vlan_ids. '''
        self.width = 640
        self.height = 280
        self.dpi = 72.0
        self.date_diff = None
        self.time_zone = timezone_default()
        self.begin_date = None
        self.end_date = datetime.now(self.time_zone)
        self.sample_size = lightcount.INTERVAL_SECONDS
        self.node_ids = [] # list of node_id's, [None] means "any"
        self.vlan_ids = [] # list of vlan_id's, [None] means "any"
        self.ips = [] # list of IP's, [None] means "any"
        # Show a logarithmic scale
        self.logarithmic_scale = True
        # When False, there is only one list of values, so we can show both in and out and the percentile
        self.only_one_value_source = True

    def validate(self):
        ''' Call this before reading the values. It will 'normalize' the values so certain
            assumptions about the parameters hold. Read from the validated ChartParameters
            when you wish to display what the 'real' parameters used for the Chart are. '''
        assert (self.sample_size % lightcount.INTERVAL_SECONDS) == 0

        # If begin time is not set, assume period of a month and set end_date on the next month
        if self.begin_date == None:
            self.begin_date = datetime(self.end_date.year, self.end_date.month, 1, tzinfo=self.time_zone)
            self.end_date = datetime(self.begin_date.year, self.begin_date.month + 1, 1, tzinfo=self.time_zone)

        # Set date difference
        self.date_diff = long(mktime(self.end_date.timetuple())) - long(mktime(self.begin_date.timetuple()))
        assert (self.date_diff % self.sample_size) == 0
        assert self.begin_date < self.end_date

        # Check IPs/nodes/vlans combinations (remove None's first)
        for name in ('ips', 'node_ids', 'vlan_ids'):
            obj = self.__dict__[name]
            while None in obj:
                obj.remove(None)
            if len(obj) == 0:
                obj.append(None)
        # If there's only one line to show, set only_one_value_source to True.
        if len(self.ips) == 1 and len(self.node_ids) == 1 and len(self.vlan_ids) == 1:
            self.only_one_value_source = True
        else:
            self.only_one_value_source = False

