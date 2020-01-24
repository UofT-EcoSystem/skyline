import logging

from skyline.initialization import (
    check_skyline_preconditions,
    initialize_skyline,
)

logger = logging.getLogger(__name__)


def register_command(subparsers):
    parser = subparsers.add_parser(
        "memory",
        help="Generate a memory usage report.",
    )
    parser.add_argument(
        "entry_point",
        help="The entry point file in this project that contains the Skyline "
             "provider functions.",
    )
    parser.add_argument(
        "-o", "--output",
        help="The location where the memory report should be stored.",
        required=True,
    )
    parser.add_argument(
        "--log-file",
        help="The location of the log file.",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Log debug messages.")
    parser.set_defaults(func=main)


def actual_main(args):
    from skyline.analysis.session import AnalysisSession
    from skyline.config import Config
    from skyline.exceptions import AnalysisError

    try:
        session = AnalysisSession.new_from(
            Config.project_root, Config.entry_point)
        session.generate_memory_usage_report(
            save_report_to=args.output,
        )
    except AnalysisError:
        logger.exception(
            "Skyline encountered an error when profiling your model.")


def main(args):
    check_skyline_preconditions(args)
    initialize_skyline(args)
    actual_main(args)