SendyRSSPub
===========

[Sendy](https://sendy.co/) is an excellent piece of software written for
sending out newsletters via Amazon SES. One current limitation of Sendy is
that it does not have the ability to read an RSS feed and use the contents of
that feed for generating newsletters.

SendyRSSPub is a script that pulls an Atom/RSS feed and generates a newsletter
using the Sendy API.

Basic Usage
===========

Prerequisites
-------------

This software requires Python. It has been tested and is currently in active
use with Python 2.7. It may work with older or newer versions, however it has
not been tested in those environments.

In order to install the rest of the prerequisites, you need Pip. The most
recent versions of Python (2.7.9+) come with Pip by default. If you don't
already have it, then you need to install it. Installation instructions can
be found at [https://pip.pypa.io/](https://pip.pypa.io/).

Once pip is installed, the remaining prequisites can be installed as follows:

    pip install -r requirements.txt

SendyRSSPub can be run from anywhere, it does not need to run on the same
system as your RSS feed or your Sendy installation. As long as the system has
network access to both, everything should work.

SendyRSSPub does not take responsibility for scheduling. If you want it to
run on a periodic basis, you will need to run it via a job scheduling system
such as cron.

The Basics
----------

The sendyrsspub.py command is the only command you need to use in order to use
this software. There are, however, a few supporting files that are required
in order for everything to work:

- **settings.py:** the default settings, which can be overridden on the
                   command line.
- **templates:**   the directory which contains the text and html templates
                   used for rendering newsletters.
- **feed_log.db:** a database of feed items that have been processed. This
                   is required to prevent duplicate messages from being sent.
                   This file is automatically created on first use.

Getting Help
------------

Most commands are documented via help on the command line. For example, to
see the top level commands, you can type the following:

    python sendyrsspub.py -h

To see additional help about a specific command (i.e. in this case, the
test_feed command), you can type the following:

    python sendyrsspub.py test_feed -h

Now onto getting the software setup...

1. Configure Default Settings
-----------------------------

Edit the file settings.py and change the settings to match your current
environment. Generally, you can leave the default database name (feed_log.db)
as-is - there are very few cases when you will need to change this. For
testing, you can also leave the default template names as-is.

2. Test Reading the Feed URL
----------------------------

Enter the following command on the command line:

    python sendyrsspub.py test_feed

This will read the RSS feed and output the contents as a Python data structure.
You will need this information for creating your newsletter templates. If you
like, you can output this data to a text file by as follows:

    python sendyrsspub.py test_feed > feed_data.txt

3. Test the Newsletter Templates
--------------------------------

You can test the currently configured newsletter templates by typing the
following on the command line:

    python sendyrsspub.py test_template

This command will read the feed and use the data from that feed to render the
templates configured in settings.py to stdout. To render a specific template,
other than those configured in settings.py, you can type the following instead:

   python sendyrsspub.py test_template --template template_name.html

You can create your own newsletter templates, using the example ones as
a basic reference. Templates are rendered using the Jinja 2 templating engine.
For more info on how this templating engine works, you can visit the
documentation at [http://jinja.pocoo.org/docs/dev/](http://jinja.pocoo.org/docs/dev/).

The data supplied to the templates comes from the data from the feed, as was
tested in step 2. Once you create your own custom templates, you can configure
those templates to be used by default in the settings.py file.

4. Send the Newsletter
----------------------

Once the template rendering is working as expected, you can send a newsletter
as follows:

    python sendyrsspub.py send_newsletter

You can run this command via cron at any interval you like to have a
newsletter sent automatically. If there are no new items in the feed, no
newsletter will be sent.

5. Maintaining the Database
---------------------------

The database can be cleaned and/or pruned using the *db_clean* and *db_prune*
commands. See the command-line documentation for more details.

Getting More Help
=================

If you need help getting this software up and running in your environment, or
need technical support, [contact us at Peak Data](http://peakdata.io/contact-us/).