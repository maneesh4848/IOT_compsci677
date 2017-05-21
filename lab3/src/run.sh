#!/bin/bash
cache1=5
cache2=6
pkill screen
screen -AdmS myshell -t tab0 bash
screen -S myshell -X screen -t pyro-server pyro4-ns -n 128.119.243.175
screen -S myshell -X screen -t backend1 python server_backend.py 1
screen -S myshell -X screen -t backend2 python server_backend.py 2
sleep 1
screen -S myshell -X screen -t gateway1 python server_gateway.py 1 $cache1
screen -S myshell -X screen -t gateway2 python server_gateway.py 2 $cache2
sleep 1
screen -S myshell -X screen -t temp python tempsensor.py
sleep 2
screen -S myshell -X screen -t door python doorsensor.py
sleep 2
screen -S myshell -X screen -t motion python motionsensor.py
sleep 2
screen -S myshell -X screen -t presence python presencesensor.py
#sleep 2
screen -r myshell
