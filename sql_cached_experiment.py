from ast import literal_eval
import sqlite3
import pandas as pd
from experiment import Experiment
from itertools import chain


class SQLCachedExperiment(Experiment):
    """
    A type of Experiment that can process all results into an SQL database for easy access.
    """

    def results_db(self):
        """
        Open a connection to the database used to cache results.

        The "headers" database will contain the parameters used for each task.
        The "data" database will contain the data generated as a result of each task.

        :return: A connection to the database used to cache results.
        """
        return SQLiteConnection(self.local_experiment_path("_results.db"))

    def _save_data(self, data_columns, primary_key):
        """
        Save data from output files into the database.

        These output files must have a particular format. The first line should contain a dictionary, representing
        the parameters of the task. All remaining lines should be tuples of data generated by the task.

        :param data_columns: A list of (column name, column type) tuples indicating the structure of each data point.
        :param primary_key: A primary key to use for the "data" database. Note a "file" column is available.
        :return: None
        """
        print("Reading all output data into SQL table")
        headers = []
        data = []

        # Create the table for the data (so that we can set a primary key)
        query = 'CREATE TABLE data (' + \
                ', '.join([' '.join(col) for col in (data_columns + [("file", "integer")])]) + \
                ', PRIMARY KEY(' + primary_key + '));'
        with self.results_db() as db:
            db.execute('DROP TABLE IF EXISTS data;')
            db.execute(query)

        # Read the data from all input files
        for filename in self.output_filenames():
            with open(filename) as input_file:
                lines = input_file.readlines()

                if len(lines) == 0:
                    continue

                try:
                    file_id = int(filename[filename.rfind('/')+1:].replace(".out", ""))
                    headers.append(dict(file=file_id, **literal_eval(lines[0])))

                    data.extend(
                        [{col[0]: val for col, val in chain(zip(data_columns, tup), [(("file", ""), file_id)])}
                         for tup in map(literal_eval, lines[1:])])
                except SyntaxError:
                    raise SyntaxError('EOL while scanning ' + filename)
                except ValueError:
                    raise ValueError('Malformed value while scanning ' + filename)
        # Save the results to the database
        with self.results_db() as db:
            pd.DataFrame(headers).to_sql("headers", db, index=False, if_exists="replace")
            pd.DataFrame(data).to_sql("data", db, index=False, if_exists="append")


class SQLiteConnection:
    """
    A connection to an SQLite database that supports using the *with* keyword.
    (unlike using sqlite3.connect directly, which does not support the *with* keyword).

    From https://stackoverflow.com/questions/19522505/using-sqlite3-in-python-with-with-keyword
    """
    def __init__(self, file):
        self.file = file

    def __enter__(self):
        self.conn = sqlite3.connect(self.file)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def __exit__(self, exit_type, value, traceback):
        self.conn.commit()
        self.conn.close()
