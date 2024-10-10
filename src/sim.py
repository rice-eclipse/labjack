from unittest.mock import patch
import mock_ljm
from labjack import ljm
import configparser

# Mock behavior for ConfigParser's read method
def mock_read(self, filenames, encoding=None):
    # Simulate reading from config_sim.ini
    return super(configparser.ConfigParser, self).read('config_sim.ini', encoding)

# Mock ljm when running on a non-LabJack machine
with patch('labjack.ljm', new=mock_ljm.SimLJM()):
    with patch.object(configparser.ConfigParser, 'read', mock_read):
        import main
        main.main()