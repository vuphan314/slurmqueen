import ast
import io
import json
import os
import pandas as pd
import pandas.io.sql
import sqlite3


class Experiment:
    def __init__(self, command, changing_args):
        self.command = command
        self.changing_args = changing_args

    def instance(self, local_directory):
        return ExperimentInstance(self, local_directory)


class ExperimentInstance:
    def __init__(self, experiment_base, local_directory):
        """
        Create .in files for this experiment in the provided directory

        :param local_directory: The directory to place .in files and read .out files (created if does not exist)
        """
        self._exp = experiment_base
        self._local_directory = local_directory

    def setup(self):
        """
        Create .in files for this experiment in the provided directory

        :param experiment_directory: The directory to place .in files (created if does not exist)
        :return:
        """
        # Create the local directory structure
        if not os.path.exists(self._local_directory):
            os.makedirs(self._local_directory)

        # Craft input files for each worker
        input_files = []
        for count, args in enumerate(self._exp.changing_args):
            args = dict(args)

            number = str(count).zfill(len(str(len(self._exp.changing_args))))  # Prepend with padded zeros

            args['output'] = "./" + number + '.out'

            input_file = io.open(self._local_directory + '/' + number + '.in', 'w', newline='\n')

            # Write the arguments as the first line of the output file
            input_file.write('echo "' + json.dumps(args).replace('"', '\\"') + '" > ' + args['output'])
            input_file.write('\n')

            input_file.write(self._exp.command)

            if '' in args:
                for positional_arg in args['']:
                    input_file.write(' "' + str(positional_arg) + '"')
            for arg_key in args:
                if arg_key == '':  # named argument
                    continue
                if '|' in arg_key:  # private argument
                    continue

                input_file.write(' --' + str(arg_key) + '="' + str(args[arg_key]) + '"')
            input_file.write(' &> ' + './' + number + '.log')
            input_file.write('\n')
            input_file.close()

    def output_filenames(self):
        """
        Get all files that were output by this experiment.

        :param config: The runtime server configuration.
        :return: A list of full paths, each one an output file of this experiment.
        """
        result = []
        for filename in os.listdir(self._local_directory):
            if filename.endswith('.out'):
                result.append(self._local_directory + '/' + filename)
        return result

    def __len__(self):
        return len(self._exp.changing_args)

    def query(self, query):
        """
        Query the database of results.

        :param config: The runtime server configuration.
        :param query: An SQL query to run
        :return: A pandas dataframe with the results of the query
        """
        with self.get_database() as db:
            data = pd.read_sql_query(query, db)
            return data

    def get_database(self):
        """
        Open a connection to the database used to cache results.

        The "headers" database will contain the parameters used for each task.
        The "data" database will contain the data generated as a result of each task.

        :param config: The runtime server configuration.
        :return: A connection to the database used to cache results.
        """
        return SQLiteConnection(self._local_directory + "/_results.db")

    def create_database(self):
        """
        Save data from output files into the database, overwriting the existing _results.db file if it exists

        These output files must have a particular format. The first line should contain a dictionary, representing
        the parameters of the task. All remaining lines should be of the form "Key: Value"

        :return: None
        """
        print("Reading all output data into SQL table")

        output_files = self.output_filenames()
        if len(output_files) == 0:
            raise FileNotFoundError('No output files found in ' + self._local_directory)

        # Gather the results from all output files
        data = []
        for filename in output_files:
            with open(filename) as input_file:
                lines = input_file.readlines()

                if len(lines) == 0:
                    continue

                try:
                    file_id = int(filename[filename.rfind('/') + 1:].replace(".out", ""))
                    datum = ast.literal_eval(lines[0])
                    datum.pop('', None)  # remove the list of positional arguments
                    datum['file'] = file_id

                    for line in lines[1:]:
                        print(line)
                        if len(line) == 1: continue
                        if ":" not in line: continue

                        key_value_pair = line.split(":")
                        if key_value_pair[1] is "inf" or key_value_pair[1] is "nan":
                            key_value_pair[1] = "-1"

                        try:
                            datum[key_value_pair[0].strip()] = ast.literal_eval(key_value_pair[1].strip())
                        except ValueError: # Treat as string value
                            datum[key_value_pair[0].strip()] = key_value_pair[1].strip()

                    data.append(datum)
                except SyntaxError:
                    raise SyntaxError('EOL while scanning ' + filename)
                except ValueError:
                    raise ValueError('Malformed value while scanning ' + filename)

        # Save the results to the database
        with self.get_database() as db:
            # We want to set PRIMARY KEY to be the file column, but pd.DataFrame.to_sql does not support primary keys
            # See https://stackoverflow.com/questions/30867390/python-pandas-to-sql-how-to-create-a-table-with-a-primary-key
            pandas_sql = pd.io.sql.pandasSQL_builder(db)
            table = pd.io.sql.SQLiteTable("data", pandas_sql, frame=pd.DataFrame(data), index=False,
                                          if_exists="replace", keys='file')
            table.create()
            table.insert()


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
