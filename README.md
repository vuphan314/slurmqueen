# SlurmQueen
A Python 3 library for automatically running experiments on a black-box tool using a Slurm cluster.
In particular, this harness allows you to:
 1. Define an experiment by declaring a list of tasks to run on a tool.
 2. Generate bash scripts that run each task.
 3. Run those bash scripts on a Slurm cluster and download the results.
 4. Analyze the results through an SQL interface.

See [this jupyter notebook](example/example_experimental_setup.ipynb) for detailed usage.

## Required libraries:
* paramiko
* pandas
* ipywidgets
* click (to run the example)
* notebook (to run the example)

See [requirements.txt](requirements.txt) for detailed version information, if needed.