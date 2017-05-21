#!/usr/bin/python
# when run from this entry point, you don't need to explicity set your PYTHONPATH to have the APSyncFramework/ folder in it.

from APSyncFramework import APSync
from APSyncFramework.modules.lib import APSync_module
from APSyncFramework.utils.common_utils import Connection
from APSyncFramework.utils.json_utils import json_wrap_with_target

apsync_state = None

if __name__ == '__main__':
    apsync_state = APSync.APSync()
    apsync_state.main_loop()

