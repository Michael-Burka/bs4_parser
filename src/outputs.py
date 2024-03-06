import csv
import datetime as dt
import logging
from typing import List, Tuple, Any, Optional

from prettytable import PrettyTable

from constants import BASE_DIR


DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S'


def control_output(results: List[Tuple[Any, ...]],
                   cli_args: Optional[Any]) -> None:
    """
    Directs output based on CLI args: pretty table, file save, or default.

    Args:
        results: The results to output.
        cli_args: Command line arguments provided by the user.
    """
    output = cli_args.output
    if output == 'pretty':
        pretty_output(results)
    elif output == 'file':
        file_output(results, cli_args)
    else:
        default_output(results)


def default_output(results: List[Tuple[Any, ...]]) -> None:
    """
    Print results in a simple format to the console.

    Args:
        results: The results to print.
    """
    for row in results:
        print(*row)


def pretty_output(results: List[Tuple[Any, ...]]) -> None:
    """
    Print results in a formatted table using PrettyTable.

    Args:
        results: The results to print in a table.
    """
    table = PrettyTable()
    table.field_names = results[0]
    table.align = 'l'
    table.add_rows(results[1:])
    print(table)


def file_output(results: List[Tuple[Any, ...]],
                cli_args: Optional[Any]) -> None:
    """
    Save results to a CSV file in the 'results' directory.

    Args:
        results: The results to save.
        cli_args: The command line arguments.
    """
    results_dir = BASE_DIR / 'results'
    results_dir.mkdir(exist_ok=True)
    parser_mode = cli_args.mode
    now = dt.datetime.now()
    now_formatted = now.strftime(DATETIME_FORMAT)
    file_name = f'{parser_mode}_{now_formatted}.csv'
    file_path = results_dir / file_name
    with open(file_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(f, dialect='unix')
        writer.writerows(results)
    logging.info(f'Файл с результатами был сохранён: {file_path}')
