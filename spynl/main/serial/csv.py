"""
This allows to receive data in csv format.

Note: The .csv format is limited in structure, so the assumption is that the
data is flat! For data querying, this works well for all queries which return a
list of documents with the same structure and no nested documents.
"""

import csv
import io

from spynl.main.serial import json as spynl_json
from spynl.main.serial import objects
from spynl.main.serial.exceptions import MalformedRequestException


def loads(body, headers=None, context=None):
    """
    Parse CSV input. Header fields can contain delimiter and quotechar info.
    Search queries need to remain powerful in structure, so we test for JSON
    first (this can go later, when SWPY-295 is done).
    """
    if spynl_json.sniff(body):
        return spynl_json.loads(body)

    # check x-spynl headers
    headers = {} if headers is None else headers
    delimiter = headers.get('x-spynl-delimiter')
    quotechar = headers.get('x-spynl-quotechar')
    # if not given, sniff delimiter and quotechar
    if not delimiter or not quotechar:
        try:
            dialect = csv.Sniffer().sniff(body[:3000])
        except Exception as err:
            if str(err) == 'Could not determine delimiter':
                dialect = csv.Sniffer().sniff(body[:6000], delimiters=',\t|')
            else:
                raise MalformedRequestException('text/csv', error_cause=str(err))

        if not delimiter:
            delimiter = dialect.delimiter
        if not quotechar:
            quotechar = dialect.quotechar

    data = body.split("\n")
    dict_data = [
        objects.SpynlDecoder(context=context)(dic)
        for dic in csv.DictReader(data, delimiter=delimiter, quotechar=quotechar)
    ]

    return {'data': dict_data}


class UnicodeStringCSVWriter:
    """A CSV writer to write rows to a string, which is encoded in UTF-8."""

    def __init__(self, dialect=csv.excel, **kwds):
        # Redirect output to a queue
        self.output = io.StringIO()
        self.writer = csv.writer(self.output, dialect=dialect, **kwds)

    def writerow(self, row):
        """Write a row."""
        self.writer.writerow([str(s) for s in row])

    def release(self):
        """Fetch the UTF-8 output from the `output` and decode it."""
        data = self.output.getvalue()
        self.output.truncate(0)  # empty queue
        return data

    def writerows(self, rows):
        """Write rows."""
        for row in rows:
            self.writerow(row)


def dumps(body, pretty=False):  # pylint: disable=unused-argument
    """
    Dump the passed body into JSON.

    CSV is a flat format, and eveything nested will be send as a
    quoted dumped JSON string. This is also why all other strings
    will be quoted.
    All content should be contained in a dictionary,
    in a list under the single key "data".
    If there is no "data" key, we render the whole response as JSON.
    """
    if body.get('data'):
        csv_writer = UnicodeStringCSVWriter(quoting=csv.QUOTE_MINIMAL, quotechar="'")
        json_data = body.get('data')
        keys = list(json_data[0].keys())
        csv_writer.writerow(keys)
        for doc in json_data:
            row = [spynl_json.dumps(doc.get(k, ' ')) for k in keys]
            csv_writer.writerow(row)
        return csv_writer.release()
    return spynl_json.dumps(body, pretty)


def sniff(body):
    """Not implemented for csv."""
    return False
