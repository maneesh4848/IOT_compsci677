# spring17-lab2
Names and emails of students working on the project:

Student 1: Sai Venkata Maneesh Tipirineni (stipirineni@umass.edu)

Student 2: Chandra Sekhar Mummidi (cmummidi@umass.edu)

Requirments
---------------
1. Python
2. Pyro4

Files
----------------
1. node.py - Base class, contains functionality for starting server and maintaining vector clocks
2. leader_elect.py - Base of gateways, sensors and devices. Built on node class. Contains functionality for leader election and physical time synchronization.
3. server_backend.py - Maintains database.
4. server_gateway.py - Interacts with sensors,devices. Works as an application interface between backend and sensors. Runs the security system algorithm.
5. tempsensor.py - Temperature sensor (temperature value)
6. motionsensor.py - Motion sensor (state: motion/no_motion)
7. doorsensor.py - Door sensor (state: open/close)
8. presencesensor.py - Presence sensor (state: yes/no)
9. lightbulb.py - Smart Light Bulb (state: on/off)
10. smart_outlet.py - Smart Outlet (state: on/off)
11. user.py - User interface to give commands to other processes

Running
----------
1. Run pyro nameserver -> python -m Pyro4.naming -n "host_name"
2. First run server_backend.py -> python server_backend.py
3. Then python server_gateway.py
4. Then all 4 sensors and 2 devices -> python tempsensor.py, python motionsensor.py, python doorsensor.py, python presencesensor.py, python smart_outlet.py, python lightbulb.py
5. Then run user.py and give commands from menu

Note:we are using default port number 9090.host_name shouldn't include port number.
And config file contains names and IP addresses of all the processes and has to be modified accordingly to run on different machines.
Also note that all sensors and devices accept inputs too for state changes but it gets messy due to the output messages.
And input for presencesensor cannot be given through user.py interface and will have to be given directly to the process.
