#!/usr/bin/env python
# _*_ encoding: utf-8 _*_


import os
import sys
import code
import inspect
import argparse


class InvalidCommand(Exception):
    """\
        This is a generic error for "bad" commands.
        It is not used in Flask-Script itself, but you should throw
        this error (or one derived from it) in your command handlers,
        and your main code should display this error's message without
        a stack trace.

        This way, we maintain interoperability if some other plug-in code
        supplies Flask-Script hooks.
        """
    pass


class Group(object):
    """
    Stores argument groups and mutually exclusive groups for
    `ArgumentParser.add_argument_group <http://argparse.googlecode.com/svn/trunk/doc/other-methods.html#argument-groups>`
    or `ArgumentParser.add_mutually_exclusive_group <http://argparse.googlecode.com/svn/trunk/doc/other-methods.html#add_mutually_exclusive_group>`.

    Note: The title and description params cannot be used with the exclusive
    or required params.

    :param options: A list of Option classes to add to this group
    :param title: A string to use as the title of the argument group
    :param description: A string to use as the description of the argument
                        group
    :param exclusive: A boolean indicating if this is an argument group or a
                      mutually exclusive group
    :param required: A boolean indicating if this mutually exclusive group
                     must have an option selected
    """

    def __init__(self, *options, **kwargs):
        self.option_list = options

        self.title = kwargs.pop("title", None)
        self.description = kwargs.pop("description", None)
        self.exclusive = kwargs.pop("exclusive", None)
        self.required = kwargs.pop("required", None)

        if ((self.title or self.description) and
                (self.required or self.exclusive)):
            raise TypeError("title and/or description cannot be used with "
                            "required and/or exclusive.")

        super(Group, self).__init__(**kwargs)

    def get_options(self):
        """
        By default, returns self.option_list. Override if you
        need to do instance-specific configuration.
        """
        return self.option_list


class Option(object):
    """
    Stores positional and optional arguments for `ArgumentParser.add_argument
    <http://argparse.googlecode.com/svn/trunk/doc/add_argument.html>`_.

    :param name_or_flags: Either a name or a list of option strings,
                          e.g. foo or -f, --foo
    :param action: The basic type of action to be taken when this argument
                   is encountered at the command-line.
    :param nargs: The number of command-line arguments that should be consumed.
    :param const: A constant value required by some action and nargs selections.
    :param default: The value produced if the argument is absent from
                    the command-line.
    :param type: The type to which the command-line arg should be converted.
    :param choices: A container of the allowable values for the argument.
    :param required: Whether or not the command-line option may be omitted
                     (optionals only).
    :param help: A brief description of what the argument does.
    :param metavar: A name for the argument in usage messages.
    :param dest: The name of the attribute to be added to the object
                 returned by parse_args().
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Command(object):
    """
    Base class for creating commands.

    :param func:  Initialize this command by introspecting the function.
    """

    option_list = ()
    help_args = None

    def __init__(self, func=None):
        if func is None:
            if not self.option_list:
                self.option_list = []
            return

        args, varargs, keywords, defaults = inspect.getargspec(func)
        if inspect.ismethod(func):
            args = args[1:]

        options = []

        # first arg is always "app" : ignore

        defaults = defaults or []
        kwargs = dict(zip(*[reversed(l) for l in (args, defaults)]))

        for arg in args:

            if arg in kwargs:

                default = kwargs[arg]

                if isinstance(default, bool):
                    options.append(Option('-%s' % arg[0],
                                          '--%s' % arg,
                                          action="store_true",
                                          dest=arg,
                                          required=False,
                                          default=default))
                else:
                    options.append(Option('-%s' % arg[0],
                                          '--%s' % arg,
                                          dest=arg,
                                          type=str,
                                          required=False,
                                          default=default))

            else:
                options.append(Option(arg, type=str))

        self.run = func
        self.__doc__ = func.__doc__
        self.option_list = options

    @property
    def description(self):
        description = self.__doc__ or ''
        return description.strip()

    def add_option(self, option):
        """
        Adds Option to option list.
        """
        self.option_list.append(option)

    def get_options(self):
        """
        By default, returns self.option_list. Override if you
        need to do instance-specific configuration.
        """
        return self.option_list

    def create_parser(self, *args, **kwargs):
        func_stack = kwargs.pop('func_stack',())
        parent = kwargs.pop('parent',None)
        parser = argparse.ArgumentParser(*args, add_help=False, **kwargs)
        help_args = self.help_args
        while help_args is None and parent is not None:
            help_args = parent.help_args
            parent = getattr(parent,'parent',None)

        if help_args:
            from sanic_script import add_help
            add_help(parser, help_args)

        for option in self.get_options():
            if isinstance(option, Group):
                if option.exclusive:
                    group = parser.add_mutually_exclusive_group(
                        required=option.required,
                    )
                else:
                    group = parser.add_argument_group(
                        title=option.title,
                        description=option.description,
                    )
                for opt in option.get_options():
                    group.add_argument(*opt.args, **opt.kwargs)
            else:
                parser.add_argument(*option.args, **option.kwargs)

        parser.set_defaults(func_stack=func_stack+(self,))

        self.parser = parser
        self.parent = parent
        return parser

    def __call__(self, app=None, *args, **kwargs):
        """
        Handles the command with the given app.
        Default behaviour is to call ``self.run`` within a test request context.
        """
        # with app.test_request_context():
        return self.run(*args, **kwargs)

    def run(self):
        """
        Runs a command. This must be implemented by the subclass. Should take
        arguments as configured by the Command options.
        """
        raise NotImplementedError


class Shell(Command):
    """
    Runs a Python shell inside Flask application context.

    :param banner: banner appearing at top of shell when started
    :param make_context: a callable returning a dict of variables
                         used in the shell namespace. By default
                         returns a dict consisting of just the app.
    :param use_ipython: use IPython shell if available, ignore if not.
                        The IPython shell can be turned off in command
                        line by passing the **--no-ipython** flag.
    """

    banner = ''

    help = description = 'Runs a Python shell.'

    def __init__(self, banner=None, make_context=None, use_ipython=True,
                 use_bpython=True, use_ptipython=True, use_ptpython=True):

        self.banner = banner or self.banner
        self.use_ipython = use_ipython
        self.use_bpython = use_bpython
        self.use_ptipython = use_ptipython
        self.use_ptpython = use_ptpython

        self.make_context = make_context

    def get_options(self):
        return (
            Option('--no-ipython',
                action="store_true",
                dest='no_ipython',
                default=not(self.use_ipython),
                help="Do not use the IPython shell"),
        )

    def get_context(self):
        """
        Returns a dict of context variables added to the shell namespace.
        """
        return

    def run(self, no_ipython):
        """
        Runs the shell.
        If no_ipython is False or use_python is True then a IPython shell is run (if installed).
        """

        context = self.get_context()

        if not no_ipython:
            # Try IPython
            try:
                from IPython import embed
                embed(banner1=self.banner, user_ns=context)
                return
            except ImportError:
                pass

        # Use basic python shell
        code.interact(self.banner, local=context)


class Server(Command):
    """
    Runs the Flask development server i.e. app.run()

    :param host: server host
    :param port: server port
    :param use_debugger: Flag whether to default to using the Werkzeug debugger.
                         This can be overriden in the command line
                         by passing the **-d** or **-D** flag.
                         Defaults to False, for security.

    :param use_reloader: Flag whether to use the auto-reloader.
                         Default to True when debugging.
                         This can be overriden in the command line by
                         passing the **-r**/**-R** flag.
    :param threaded: should the process handle each request in a separate
                     thread?
    :param processes: number of processes to spawn
    :param passthrough_errors: disable the error catching. This means that the server will die on errors but it can be useful to hook debuggers in (pdb etc.)
    :param ssl_crt: path to ssl certificate file
    :param ssl_key: path to ssl key file
    :param options: :func:`werkzeug.run_simple` options.
    """
    banner = ''

    help = description = 'Runs the Flask development server i.e. app.run()'

    def __init__(self, host='127.0.0.1', port=5000, debug=None,
                 auto_reload=None, **options):

        self.port = port
        self.host = host
        self.debug = debug
        self.auto_reload = auto_reload if auto_reload is not None else debug
        self.server_options = options


    def get_options(self):

        options = (
            Option('-h', '--host',
                   dest='host',
                   default=self.host),

            Option('-p', '--port',
                   dest='port',
                   type=int,
                   default=self.port),

            Option('-d', '--debug',
                   action='store_true',
                   dest='debug',
                   help='enable the Werkzeug debugger (DO NOT use in production code)',
                   default=self.debug),

            Option('-D', '--no-debug',
                   action='store_false',
                   dest='debug',
                   help='disable the Werkzeug debugger',
                   default=self.debug),

            Option('-r', '--reload',
                   action='store_true',
                   dest='auto_reload',
                   help='monitor Python files for changes (not 100%% safe for production use)',
                   default=self.auto_reload),

            Option('-R', '--no-reload',
                   action='store_false',
                   dest='auto_reload',
                   help='do not monitor Python files for changes',
                   default=self.auto_reload),

        )

        return options

    def __call__(self, app, host, port, debug, auto_reload):
        # we don't need to run the server in request context
        # so just run it directly

        if debug is None:
            debug = app.debug
            if debug is None:
                debug = True
                if sys.stderr.isatty():
                    print("Debugging is on. DANGER: Do not allow random users to connect to this server.", file=sys.stderr)
        if auto_reload is None:
            auto_reload = debug

        app.run(host=host,
                port=port,
                debug=debug,
                auto_reload=auto_reload,
                **self.server_options)


class Clean(Command):
    "Remove *.pyc and *.pyo files recursively starting at current directory"
    def run(self):
        for dirpath, dirnames, filenames in os.walk('.'):
            for filename in filenames:
                if filename.endswith('.pyc') or filename.endswith('.pyo'):
                    full_pathname = os.path.join(dirpath, filename)
                    print('Removing %s' % full_pathname)
                    os.remove(full_pathname)
