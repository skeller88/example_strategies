# Local setup 

## Set up Python virtual environment

due to pip not working, install pip after creating venv: https://askubuntu.com/questions/488529/pyvenv-3-4-error-returned-non-zero-exit-status-1
```
cd <repo-dir>
./operations/bootstrap_venv.sh
```

## Set up database
Follow the instructions in the trading_platform README.md

## Set up Python environment for ipython notebooks
Due to ipython requiring different dependencies from the app, a separate environment is configured via an environment.yml
file. 

Install Anaconda.

[Create the "arbitrage" environment from the environment.yml file](https://conda.io/docs/user-guide/tasks/manage-environments.html#creating-an-environment-from-an-environment-yml-file)

Start the Anaconda application and select the "arbitrage" environment. Run any notebook in "notebooks".

## Set up Pycharm
Set the python binary in the virtual environment [as the project interpreter](https://www.jetbrains.com/help/pycharm/configuring-python-interpreter.html#local-interpreter). 

[Set Pytest as the test runner](https://www.jetbrains.com/help/pycharm/run-debug-configuration-nosetests.html) so 
that tests can be run from Pycharm. 


