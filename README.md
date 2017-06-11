# APSyncWeb

## ---Work in progress--- 
This project is a work in progress. Please [raise an issue](https://github.com/SamuelDudley/APSyncWeb/issues/new) and include any ideas you might have / features you would like to see implemented. You can also join the chat about the [Ardupilot companion](https://github.com/ArduPilot/companion) (APSync) project [here](https://gitter.im/ArduPilot/companion).

## About
This is an attempt to create a unified web front end for the [Ardupilot companion](https://github.com/ArduPilot/companion) (APSync) project.

The project works as follows: 
A [master process](https://github.com/SamuelDudley/APSyncWeb/blob/master/APSyncFramework/APSync.py) is created that spawns modules as subprocesses. Arbitrary data is passed back and forth between these modules via queues. 
The master process is the end point for all of the modules and acts as a central router to pass data between modules as required.

The modules are built around an [inherited template class](https://github.com/SamuelDudley/APSyncWeb/blob/master/APSyncFramework/modules/lib/APSync_module.py) which has a few overloaded functions to perform the unique module functionality.

One example is a [MAVLink entry point module](https://github.com/SamuelDudley/APSyncWeb/blob/master/APSyncFramework/modules/APSync_mavlink/__init__.py) which receives MAVLink data forwards the  data to other modules.
Another example is the [webserver module](https://github.com/SamuelDudley/APSyncWeb/blob/master/APSyncFramework/modules/APSync_webserver/__init__.py) (using tornado) which implements bi-directional websocket communications and a currently serves a useless webpage :) . This module will be extended to become a centerlised landing page allowing a user to configure and monitor the companion computer + Ardupilot autopilot in real time.

## Implementation details
* The project uses the underlying file descriptors in order to preform blocking select calls on the python inter-module queues. While this reduces CPU usage and latency considerably, it has the side effect of __only being able to run on Linux-Like systems__. I personally do not see this as large issue, as all companion computer images are based on a Linux OS.  For the record, OSX is a linux-Like system, and the code currently run on OSX OK. 
* The module code is heavily leveraging the existing module format which is used by [MAVProxy](https://github.com/ArduPilot/MAVProxy) as a means to simplify future contributions / functionality.
* The structure and much of the other code is leveraged from the work by [davidbuzz](https://github.com/davidbuzz) and his [companion computer fork](https://github.com/davidbuzz/companion/tree/webconfig_wip/Common/WebConfigServer)
