import logging
import sys

def ble_sense_uuid(id):
    """Helper function to ease the read of UUIDs.

    Parameters
    ----------
    id : std
        ID of the sensor.

    Returns
    -------
    str
        Full ID of the sensor.
    """
    return f"19b10000-{id}-537e-4f6c-d104768a1214"

def setup_logging(name,path):
    """Custom logger which prints both on stdout and file.

    Parameters
    ----------
    name : str
        Name of the logger.
    path : str
        Path where to log to.
    
    Returns
    -------
    Logger
        Logger object to be used.
    """
    log_root = logging.getLogger(name)
    log_root.setLevel(logging.INFO)
    log_format = "%(asctime)s [%(threadName)s] [%(levelname)s]  %(message)s"
    filepath_log = path
    # file
    log_filehandler = logging.FileHandler(filepath_log)
    log_filehandler.setLevel(logging.INFO)
    log_formatter = logging.Formatter(log_format)
    log_filehandler.setFormatter(log_formatter)
    log_root.addHandler(log_filehandler)
    # stdout
    log_streamhandler = logging.StreamHandler(sys.stdout)
    log_streamhandler.setLevel(logging.INFO)
    log_streamhandler.setFormatter(log_formatter)
    log_root.addHandler(log_streamhandler)
    return log_root