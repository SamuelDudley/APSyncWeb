#!/usr/bin/python
# when run from this entry point, you don't need to explicity set your PYTHONPATH to have the APSyncFramework/ folder in it.

from APSyncFramework import APSync

if __name__ == '__main__':
    apsync_state = APSync.APSync()
    apsync_state.main_loop()