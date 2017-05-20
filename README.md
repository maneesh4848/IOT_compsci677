# spring17-lab3
Names and emails of students working on the project:

Student 1: Sai Venkata Maneesh Tipirineni (stipirineni@umass.edu)

Student 2: Chandra Sekhar Mummidi (cmummidi@umass.edu)

Requirments
---------------
1. Python
2. Pyro4
3. screen

Files
----------------
1. node.py - Base class, contains functionality for starting server and maintaining clocks
2. leader_elect.py - Base of gateways, sensors and devices. Built on node class. Contains functionality for leader election and physical time synchronization.
3. server_backend.py - Maintains database. Needs replica number as argument
4. server_gateway.py - Interacts with sensors,devices. Works as an application interface between backend and sensors. Runs the security system algorithm. Needs replica number and cache size as argument
5. tempsensor.py - Temperature sensor (temperature value)
6. motionsensor.py - Motion sensor (state: motion/no_motion)
7. doorsensor.py - Door sensor (state: open/close)
8. presencesensor.py - Presence sensor (state: yes/no)
9. lightbulb.py - Smart Light Bulb (state: on/off)
10. smart_outlet.py - Smart Outlet (state: on/off)

Running
----------
1. Make sure that screen is installed
2. Run run.sh 'bash run.sh' (takes some time to start)

Note:we are using default port number 9090.host_name shouldn't include port number.
And config file contains names and IP addresses of all the processes and has to be modified accordingly to run on different machines.
