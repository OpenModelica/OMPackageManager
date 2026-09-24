import argparse
import importlib


def main(argv=None):
    """Run one of the Python scripts."""
    parser = argparse.ArgumentParser(prog='OMPackageManager')
    subparsers = parser.add_subparsers(dest='script', required=True)

    # Each command imports only its own module, so a command whose dependencies are installed
    # works even when another command's (e.g. OMPython for updateinfo) are missing.

    # updateinfo command
    parser1 = subparsers.add_parser(
        'updateinfo', help='Generate up-to-date `rawdata.json`.')
    parser1.set_defaults(module='updateinfo')

    # genindex command
    parser2 = subparsers.add_parser(
        'genindex', help='Generate `index.json` from `rawdata.json`.')
    parser2.set_defaults(module='genindex')

    # generate-cache command
    parser3 = subparsers.add_parser(
        'generate-cache',
        help='Cache indexed libraries in directory `destination`.')
    parser3.add_argument('--clean', action='store_true')
    parser3.add_argument('destination', help='Directory to cache packages in.')
    parser3.set_defaults(module='generate_cache')

    # check-missing command
    parser4 = subparsers.add_parser(
        'check-missing',
        help='Print all GitHub repositories missing from modelica-3rdparty for packages from `repos.json`.')
    parser4.set_defaults(module='check_missing')

    # check-uses
    parser5 = subparsers.add_parser('check-uses', help='Some help')
    parser5.set_defaults(module='check_uses')

    args = parser.parse_args(argv)
    print(args.script)
    func = importlib.import_module('ompackagemanager.' + args.module).main
    match args.script:
        case 'generate-cache':
            func(args.destination, args.clean)
        case _:
            func()


if __name__ == '__main__':
    main()
