"""Command-line tool to test the (de)serialisation live."""

from argparse import ArgumentParser
from sys import stdin, stdout

from spynl.main.serial import dumps, loads, negotiate_content_type


def main():
    """main function for converting between formats"""
    parser = ArgumentParser(description='Convert between data formats.')
    parser.add_argument(
        '--output',
        metavar='FILENAME',
        dest='output_filename',
        default=None,
        help='filename where output is stored, STDOUT by default',
    )
    parser.add_argument(
        '--output-type',
        metavar='TYPE',
        dest='output_type',
        default='json',
        help='output type e.g. JSON or XML etc.',
    )
    parser.add_argument(
        '--input-type',
        metavar='TYPE',
        dest='input_type',
        default=None,
        help='suggested input type. See --output-type',
    )
    args = parser.parse_args()

    request = stdin.read()

    request = loads(request, negotiate_content_type(request, args.input_type))
    response = dumps(request, negotiate_content_type('', args.output_type))

    output = open(args.output_filename, 'w') if args.output_filename else stdout
    output.write(response + '\n')

    if args.output_filename:
        output.close()
