#!/usr/bin/env python

from brv.runinfo import DirectRunInfo
from brv.toolrun import ToolRun
from brv.utils import err

import sys
import os

from xml.dom import minidom

def _parse_run_elem(run):
    " Parse a <run>...</run> elements from xml"

    r = DirectRunInfo(run.getAttribute('name'))
    r._property = run.getAttribute('properties')

    NUMBER_OF_ITEMS = 7
    n = 0
    for col in run.getElementsByTagName('column'):
        title = col.getAttribute('title')
        value = col.getAttribute('value')

        try:
            if title == 'status':
                r._status = value
                n += 1
            elif title == 'cputime':
                if value:
                    r._cputime = float(value[:-1])
                else:
                    r._cputime = None
                n += 1
            elif title == 'walltime':
                if value:
                    r._walltime = float(value[:-1])
                else:
                    r._walltime = None
                n += 1
            elif title == 'memUsage':
                r._memusage = value
                n += 1
            elif title == 'category':
                r._classification = value
                n += 1
            elif title == 'exitcode':
                r._exitcode = value
                n += 1
            elif title == 'returnvalue':
                r._returnvalue = value
                n += 1
        except ValueError as e:
            err('Error parsing xml: '\
                '{0}\nTitle: {1}, value: {2}'.format(str(e), title, value))
        #else:
        #    r.others[title] = value

            # do not go over all columns when we found
            # what we are looking for
        if n == NUMBER_OF_ITEMS:
            break

    return r

def _createToolRun(xmlfl, descr = None):
    """
    Parse xml attributes that contain the information
    about tool, property and so on
    """

    roots = xmlfl.getElementsByTagName('result')
    assert len(roots) == 1
    root = roots[0]

    tr = ToolRun()
    tr.tool = root.getAttribute('tool')
    tr.tool_version = root.getAttribute('version')
    tr.date = root.getAttribute('date')[:19]
    tr.options = root.getAttribute('options')
    tr.timelimit = root.getAttribute('timelimit')
    tr.memlimit = root.getAttribute('memlimit')
    tr.benchmarkname = root.getAttribute('benchmarkname')
    tr.block = root.getAttribute('block')

    tr.name = root.getAttribute('name')
    if tr.name.endswith(tr.block):
        tr.name = tr.name[:-(len(tr.block)+1)]

    tr.description = descr

    return tr

class XMLParser(object):
    """
    Parse xml files generated by benchexec and store the result
    into memory/database
    """

    def __init__(self, db_conf = None):
        if db_conf:
            from .. database.writer import DatabaseWriter
            self._db_writer = DatabaseWriter(db_conf)

    def parseToMem(self, filePath):
        """
        Return a ToolRun object created from a given xml file.
        """

        xmlfl = minidom.parse(filePath)
        ret = _createToolRun(xmlfl)

        for run in xmlfl.getElementsByTagName('run'):
            r = _parse_run_elem(run)
            ret.append(r)

        return ret

    def parseToDB(self, filePath, outputs = None, descr = None):
        writer = self._db_writer
        xmlfl = minidom.parse(filePath)

        tool_info = _createToolRun(xmlfl, descr)
        tool_run_id = writer.getOrCreateToolInfoID(tool_info, outputs)
        benchmarks_set_id = writer.getOrCreateBenchmarksSetID(tool_info.block)

        rcnt = writer.getRunCount(tool_run_id, benchmarks_set_id)
        if rcnt and rcnt > 0:
            print("Already have results for this xml file: {0}".format(filePath))
            return 0

        assert tool_run_id is not None
        assert benchmarks_set_id is not None

        cnt = 0;
        for run in xmlfl.getElementsByTagName('run'):
            r = _parse_run_elem(run)
            writer.writeRunInfo(tool_run_id, benchmarks_set_id, r)
            cnt += 1

        writer.commit()
        return cnt


if __name__ == "__main__":
    import sys
    tr = parse_xml(sys.argv[1])
    tr.dump()
