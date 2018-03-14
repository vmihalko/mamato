#!/usr/bin/python

import sys
from os.path import basename
from math import ceil, floor

if (sys.version_info > (3, 0)):
    from http.server import SimpleHTTPRequestHandler
else:
    from SimpleHTTPServer import SimpleHTTPRequestHandler

from brv.datamanager import DataManager
from .. utils import dbg

try:
    from quik import FileLoader
except ImportError:
    print('Sorry, need quik framework to work.')
    print('Run "pip install quik" or check "http://quik.readthedocs.io/en/latest/"')
    sys.exit(1)

# the tools manager object -- it must be globals,
# since handler is created for each request and we do
# not want to create it again and again
datamanager = DataManager('database.conf')

def _render_template(wfile, name, variables):
    loader = FileLoader('html/templates/')
    template = loader.load_template(name)
    wfile.write(template.render(variables,
                                loader=loader).encode('utf-8'))

def getDescriptionOrVersion(toolr):
    descr = toolr.run_description()
    if descr is None:
        return toolr.tool_version()
    else:
        return descr

def _parse_args(args):
    opts = {}
    for a in args:
        tmp = a.split('=', 1)
        if len(tmp) != 2:
            print('ERROR: unhandled GET arg: {0}'.format(a))
            continue
        if tmp[0] in opts:
                opts[tmp[0]].append(tmp[1])
        else:
                opts[tmp[0]] = [tmp[1]]

    return opts

def _get(p, idx):
    return p[idx]

def showRoot(wfile, args):
    tools = datamanager.getTools()
    tools_sorted = {}
    for t in tools:
        # tools is a list of tool runs where each of the
        # tools has a unique name+version+options attributes
        # We want to divide them to groups according to names
        # and versions. So we have a mapping name -> version -> tools
        nkey = tools_sorted.setdefault(t.name(), {})
        nkey.setdefault(t.version(), []).append(t)
    tools_final = []
    for t in tools_sorted.items():
        tools_final.append((t[0], list(t[1].items())))
    _render_template(wfile, 'index.html',
                     {'tools' : tools_final,
                      'get' : _get,
                      'descr' : getDescriptionOrVersion})


def showResults(wfile, args):
    opts = _parse_args(args)
    if not 'run' in opts:
        wfile.write(b'<h2>No runs of tools given</h2>')
        return

    class BSet(object):
        def __init__(self, name, bid):
            self.name = name
            self.id = bid

        def __hash__(self):
            return self.id

        def __eq__(self, oth):
            return self.id == oth.id

    _showTimes = 'show_times' in opts
    _showTimesOnlySolved = 'show_times_only_solved' in opts

    # list of ToolRunInfo objects
    run_ids = list(map(int, opts['run']))
    runs = datamanager.getToolRuns(run_ids)
    categories = set()
    # there's few of classifications usually, it will be faster in list
    classifications = []
    for run in runs:
        run._stats = datamanager.getToolInfoStats(run.getID())
        for stats in run._stats.getAllStats().values():
            stats.accumulateTime(_showTimesOnlySolved)
            stats.prune()
            # a pair (name, id)
            categories.add(BSet(stats.getBenchmarksName(), stats.getBenchmarksID()))
            for c in stats.getClassifications():
                if c not in classifications:
                    classifications.append(c)

    # give it some fixed order
    cats = [x for x in categories]

    def _toolsGETList():
        s = ''
        for x in opts['run']:
            s += '&run={0}'.format(x)
        return s

    def _getStats(run, bset_id):
        assert not run is None
        assert not bset_id is None

        return run.getStats().getStatsByID(bset_id)

    def _getCount(stats, classif):
        if stats:
            return stats.getCount(classif)
        else:
            return 0

    def _getTime(stats, classif):
        if stats:
            return ceil(stats.getTime(classif))
        else:
            return 0

    def _formatTime(time):
        "Transform time in seconds to hours, minutes and seconds"
        if not time:
            return '0 s'
        ret = ''
        time = ceil(time)
        if time >= 3600:
            hrs = time // 3600
            time = time - hrs*3600
            ret = '{0} h'.format(int(hrs))
        if time >= 60 or ret != '':
            mins = time // 60
            time = time - mins*60
            ret += ' {0} min'.format(int(mins))
        if ret != 0:
            return ret + ' {0} s'.format(int(time))
        else:
            return ret + '{0} s'.format(int(time))

    _render_template(wfile, 'results.html',
                     {'runs':runs, 'benchmarks_sets' : cats,
                      'toolsGETList' : _toolsGETList,
                      'getStats' : _getStats,
                      'getCount' : _getCount,
                      'getTime' : _getTime,
                      'get' : _get,
                      'showTimes' : _showTimes,
                      'showTimesOnlySolved' : _showTimesOnlySolved,
                      'formatTime' : _formatTime,
                      'descr' : getDescriptionOrVersion,
                      'classifications' : classifications })


def manageTools(wfile, args):
    tools = datamanager.getTools()
    tools_sorted = {}
    for t in tools:
        # tools is a list of tool runs where each of the
        # tools has a unique name+version+options attributes
        # We want to divide them to groups according to names
        # and versions. So we have a mapping name -> version -> tools
        nkey = tools_sorted.setdefault(t.name(), {})
        nkey.setdefault(t.version(), []).append(t)
    tools_final = []
    for t in tools_sorted.items():
        tools_final.append((t[0], list(t[1].items())))
    _render_template(wfile, 'manage.html',
                     {'tools' : tools_final,
                      'get' : _get,
                      'descr' : getDescriptionOrVersion})

def performDelete(wfile, args):
    opts = _parse_args(args)

    # XXX: this should be done in datamanager
    from .. database.writer import DatabaseWriter
    writer = DatabaseWriter('database.conf')

    run_ids = list(map(int, opts['run']))
    runs = datamanager.getToolRuns(run_ids)

    for run in runs:
        print("Deleting tool run '{0}'".format(run.getID()))
        writer.deleteTool(run.getID())
        # adjust data locally
        datamanager.toolsmanager.remove(run)

    print("Commiting changes")
    writer.commit()

def setToolsAttr(wfile, args):
    opts = _parse_args(args)

    # XXX: this should be done in datamanager
    from .. database.writer import DatabaseWriter
    writer = DatabaseWriter('database.conf')

    run_ids = list(map(int, opts['run']))
    runs = datamanager.getToolRuns(run_ids)

    for run in runs:
        print("Deleting tool run '{0}'".format(run.getID()))
        writer.deleteTool(run.getID())
        # adjust data locally
        datamanager.toolsmanager.remove(run)

    print("Commiting changes")
    writer.commit()

    # XXX: show again
    manageTools(wfile, [])



def showFiles(wfile, args):
    opts = _parse_args(args)
    if not 'run' in opts:
        wfile.write(b'<h2>No runs of tools given</h2>')
        return

    if not 'benchmarks' in opts:
        wfile.write(b'<h2>No benchmarks to show given</h2>')
        return

    run_ids = list(map(int, opts['run']))
    run_ids.sort()
    runs = datamanager.getToolRuns(run_ids)

    try:
        bset_id = int(opts['benchmarks'][0])
    except ValueError or KeyError:
        wfile.write(b'<h2>Invalid benchmarks</h2>')
        return

    def _getBenchmarkURL(name):
        base='https://github.com/sosy-lab/sv-benchmarks/tree/master'
        try:
            return base + name[name.index('/c/'):]
        except ValueError:
            return None

    def _getShortName(name):
        return basename(name)

    _showDifferent = 'different_only' in opts
    _filter = opts.setdefault('filter', [])

    results = datamanager.getRunInfos(bset_id, run_ids).getRows().items()
    if _showDifferent:
        def some_different(x):
            L = x[1]
            if L[0] is None:
                status = None
            else:
                status = L[0].status()

            for r in L:
                if r is None:
                    if status is not None:
                        return True
                elif r.status() != status:
                    return True

            return False

        results = filter(some_different, results)

    if _filter:
        from re import compile
        filters = []
        for f in _filter:
            try:
                rf = compile(f)
            except Exception as e:
                print('ERROR: Invalid regular expression given in filter: ' + str(e))
                continue
            filters.append((f, lambda x : rf.search(x)))

        for (pattern, f) in filters:
            def match(x):
                L = x[1]
                for r in L:
                    if r and f(r.status()):
                        return True
                return False

            print('Applying {0}'.format(pattern))
            results = filter(match, results)

    results = list(results)
    assert len(runs) == len(results[0][1])
    _render_template(wfile, 'files.html',
                     {'runs' : runs,
                      'get' : _get,
                      'getBenchmarkURL' : _getBenchmarkURL,
                      'getShortName' : _getShortName,
                      'showDifferent' : _showDifferent,
                      'descr' : getDescriptionOrVersion,
                      'filters' : _filter,
                      'results': results})

def sendFile(wfile):
    f = open('html/style.css', 'rb')
    wfile.write(f.read())
    f.close()

handlers = {
    'root'              : showRoot,
    'results'           : showResults,
    'files'             : showFiles,
    'manage'            : manageTools,
    'delete'            : performDelete,
    'set'               : setToolsAttr,
    'style.css'         : None, # we handle this specially
    'js/brv.js'         : None, # we handle this specially
}

# see http://www.acmesystems.it/python_httpd
class Handler(SimpleHTTPRequestHandler):
    def _parsePath(self):
        args = []

        tmp = self.path.split('?')
        path = None
        if len(tmp) == 2:
            path = tmp[0].strip()
            args = tmp[1].split('&')
        elif len(tmp) == 1:
            path = tmp[0]

        if not path:
            return (None, [])

        if path == '' or path == '/':
            return ('root', args)
        else:
            path = path[1:]

        global handlers
        if path in handlers.keys():
            return (path, args)
        else:
            return (None, [])

    def _send_headers(self, mimetype = 'text/html'):
        self.send_response(200)
        self.send_header('Content-type', mimetype)
        self.end_headers()

    def do_GET(self):
        act, args = self._parsePath()

        if act is None:
            self._send_headers()
            self.send_error(404, 'Unhandled request')
            print(self.path)
            return
        elif act == 'style.css':
            self._send_headers('text/css')
            sendFile(self.wfile)
            return
        elif act == 'js/brv.js':
            self._send_headers('text/javascript')
            sendFile(self.wfile)
            return

        global handlers
        assert act in handlers.keys()

        self._send_headers()
        handlers[act](self.wfile, args)

