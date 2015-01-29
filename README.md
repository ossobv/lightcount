LIGHTCOUNT
----------

LightCount is a light-weight IP traffic counting tool developed by Walter
Doekes at OSSO B.V. in 2008.

BEWARE: This is old code, migrated to git. Previously, this was found at:
https://code.osso.nl/projects/lightcount


SUMMARY
-------

LightCount consists of a daemon (in C) that keeps track of all IP traffic on
specified ethernet interfaces and an interface (in python) that reads the data
from the MySQL database. Use this to monitor bandwidth usage per IP address.


PORTABILITY
-----------

Currently, the lightcount daemon needs the pthread library for threading and
the mysqlclient library for storage. It has been compiled with the gcc -ansi
flag, but has not been extensively tested outside (Debian/Ubuntu) Linux 2.6
systems. Most importantly, non-Linux systems will not have a PF\_PACKET
socket interface, so you'll need to write your own sniff.c on a non-Linux box.

The interface was created with python version 2.5 and common modules:
 * pytz (python-tz)
 * MySQLdb (python-mysqldb)
 * matplotlib (python-matplotlib)


FURTHER READING
---------------

See the INSTALL file. And when you've completed building the daemon, run it
with the -h (help) option to see help about how it does what it does and which
preprocessor options you can change to modify its behaviour.
