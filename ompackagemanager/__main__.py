import argparse

from ompackagemanager import updateinfo
from ompackagemanager import genindex
from ompackagemanager import generate_cache
from ompackagemanager import check_missing
from ompackagemanager import check_uses


def main(argv=None):
    """Run one of the Python scripts."""
    parser = argparse.ArgumentParser(prog='OMPackageManager')
    subparsers = parser.add_subparsers(dest='script', required=True)

    # updateinfo command
    parser1 = subparsers.add_parser(
        'updateinfo', help='Generate up-to-date `rawdata.json`.')
    parser1.set_defaults(func=updateinfo.main)

    # genindex command
    parser2 = subparsers.add_parser(
        'genindex', help='Generate `index.json` from `rawdata.json`.')
    parser2.set_defaults(func=genindex.main)

    # generate-cache command
    parser3 = subparsers.add_parser(
        'generate-cache',
        help='Cache indexed libraries in directory `destination`.')
    parser3.add_argument('--clean', action='store_true')
    parser3.add_argument('destination', help='Directory to cache packages in.')
    parser3.set_defaults(func=generate_cache.main)

    # check-missing command
    parser4 = subparsers.add_parser(
        'check-missing',
        help='Print all GitHub repositories missing from modelica-3rdparty for packages from `repos.json`.')
    parser4.set_defaults(func=check_missing.main)

    # check-uses
    parser5 = subparsers.add_parser('check-uses', help='Some help')
    parser5.set_defaults(func=check_uses.main)

    args = parser.parse_args(argv)
    print(args.script)
    match args.script:
        case 'generate-cache':
            args.func(args.destination, args.clean)
        case _:
            args.func()


if __name__ == '__main__':
    main()
