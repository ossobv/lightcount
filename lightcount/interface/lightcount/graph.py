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
from numpy import ndarray


class StandardGraph:
    ''' A graphical representation of the the list of results. '''

    def __init__(self, width=640, height=280, result_list=None, show_billing_line=False, log_scale=False, use_packets_not_bytes=False):
        ''' Pass at least a result_list (list of Data.Result objects) and optionally width, height, show_billing_line, log_scale. '''
        assert width >= 100 and height >= 50 and result_list, 'Please supply proper parameters (width/height/result_list)'
        self.period = result_list[0].get_period() # all periods are the same (optimization?)
        self.width = int(width)
        self.height = int(height)
        self.dpi = 72.0
        self.result_list = result_list
        self.show_billing_line = bool(show_billing_line)
        self.log_scale = bool(log_scale)
        self.use_packets_not_bytes = bool(use_packets_not_bytes)

    def create_figure(self):
        def plot_lines(ax, xvalues, result_list, high_res=False):
            def fix_data(x, y, is_log=False):
                # Drop trailing None's (happens when querying "current" graphs because we align on sensible periods)
                x, y = list(x), list(y)
                while len(y) and y[-1] is None:
                    x.pop()
                    y.pop()
                # If we're in log-mode, we can't draw on 0, so we change that to 1.
                if is_log:
                    y = map(lambda y: (y, 1)[y==0], y)
                
                return x, y
                
            # If only one query is specified, we can show both input and output in the same graph.
            show_input_output_separately = len(result_list) == 1

            if show_input_output_separately:
                colors = ['#008800', '#000088', '#ff0000'] # in, out, billing
            else:
                colors = ['#383838','#90ae61','#ffb400','#e70a8c','#00a2d0']

            color_n = 0
            lines = []

            # In the high resolution case, we draw pretty pluses on every data point.
            if high_res:
                marker = '+'
            else:
                marker = ''
            
            for result_n, result in enumerate(result_list):
                label_append = (' (%i)' % (result_n + 1), '')[len(result_list)==1]
                if show_input_output_separately:
                    lines.append({'x': xvalues, 'y': result.get_in_bps(), 'label': 'input%s' % label_append, \
                                  'alpha': 0.5, 'color': colors[color_n % len(colors)], 'linewidth': 2.0, \
                                  'marker': marker})
                    color_n += 1
                    lines.append({'x': xvalues, 'y': result.get_out_bps(), 'label': 'output%s' % label_append, \
                                  'alpha': 0.5, 'color': colors[color_n % len(colors)], 'linewidth': 2.0, \
                                  'marker': marker})
                    color_n += 1
                else:
                    lines.append({'x': xvalues, 'y': result.get_io_bps(), 'label': 'in/out%s' % label_append, \
                                  'alpha': 0.5, 'color': colors[color_n % len(colors)], 'linewidth': 2.0, \
                                  'marker': marker})
                    color_n += 1

                if self.period.get_period() == 'month' and self.show_billing_line:
                    x = (
                        max(xvalues[0], date2num(self.period.get_begin_date())),
                        min(xvalues[-1], date2num(self.period.get_end_date()))
                    )
                    billing_in, billing_out, billing_estimate = result.get_billing_values()
                    y_point = max(billing_in, billing_out)
                    if show_input_output_separately:
                        color = colors[color_n % len(colors)]
                        color_n += 1
                    else:
                        color = colors[(color_n - 1) % len(colors)]
                    lines.append({'x': x, 'y': (y_point, y_point), 'label': '95p%s' % label_append, \
                                  'color': color, 'linewidth': 1.0, 'linestyle': ('-', '--')[billing_estimate]})

            # Draw the traffic lines
            for line in lines:
                # Draw the line, unless there are only None-values
                if len(set(line['y']) - set((None,))) != 0:
                    x, y = fix_data(line.pop('x'), line.pop('y'), is_log=(ax.get_yscale()=='log'))
                    ax.plot(x, y, **line)

        def format_x_axis(ax):
            ''' Draw vertical lines and line identifiers. '''
            period = self.period
            date_diff = period.get_interval()
            tzinfo = period.get_tzinfo()

            if date_diff <= 14400:
                loc = graphutil.MinuteLocator(byminute=(0, 30), tz=tzinfo)
                fmt = graphutil.DateFormatter('%H:%M %z', tz=tzinfo)
            elif date_diff <= 43200:
                loc = graphutil.HourLocator(interval=1, tz=tzinfo)
                fmt = graphutil.DateFormatter('%H:%M', tz=tzinfo)
            elif date_diff <= 90000:
                loc = graphutil.HourLocator(interval=2, tz=tzinfo)
                fmt = graphutil.DateFormatter('%Hh', tz=tzinfo)
            elif date_diff <= 7 * 86400:
                loc = graphutil.HourLocator(interval=24, tz=tzinfo)
                fmt = graphutil.DateFormatter('%d/%m', tz=tzinfo)
            elif date_diff <= 50 * 86400:
                loc = graphutil.WeekdayLocator(graphutil.MONDAY, tz=tzinfo)
                fmt = graphutil.DateFormatter('%a %d %b', tz=tzinfo)
            else:
                loc = graphutil.MonthLocator(tz=tzinfo)
                fmt = graphutil.DateFormatter('%b \'%y', tz=tzinfo)
            ax.xaxis.set_major_locator(loc)
            ax.xaxis.set_major_formatter(fmt)
            ax.xaxis.set_ticks_position('top')
            ax.set_xlim(xmin=date2num(period.get_begin_date()), xmax=date2num(period.get_end_date()))
            for label in ax.get_xticklabels():
                label.set_fontsize(10)
            for tick in ax.yaxis.get_major_ticks():
                tick.set_pad(10)

        def format_y_axis(ax):
            ''' Draw horizontal lines and line identifiers. '''
            # Set limits to be at least a range (else the line would be centered)
            try:
                ymin, ymax = ax.dataLim.intervaly().get_bounds() # old matplotlib
            except TypeError:
                ymin, ymax = ax.get_ybound() # new matplotlib

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
            legend = ax.legend(loc='best')
            legend.draw_frame(True)
            for text in legend.get_texts():
                text.set_fontsize(10)


        # Initialize figure
        fig = Figure(figsize=(self.width / self.dpi, self.height / self.dpi), dpi=self.dpi)
        canvas = FigureCanvas(fig)
        ax = fig.add_axes([4 / self.dpi, 4 / self.dpi, 60 / self.dpi, 60 / self.dpi], frame_on=False)

        # Select log/normal scale
        if self.log_scale:
            ax.set_yscale('log')

        # Draw lines, axes, legend and grid
        plot_lines(ax, self.period.get_mpl_sample_times(), self.result_list, self.period.is_high_res())
        format_x_axis(ax)
        format_y_axis(ax)
        format_legend(ax)
        ax.grid(True, color='#cccccc')
        
        # It is done
        return fig

    def output(self):
        ''' Return the image data as binary png data. '''
        import os
        tmpfile = os.tmpfile()
        self.write(tmpfile)
        tmpfile.seek(0)
        return tmpfile.read() # destructor will clean up any would-be temporary files

    def write(self, filename_or_fileobj):
        ''' Write the image to filename on the local file system or to a file object. '''
        f = self.create_figure()
        f.savefig(filename_or_fileobj, dpi=self.dpi)
