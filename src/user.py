import sys,time
import pdb
import logging,datetime
import threading

#Logging
logger = logging.getLogger("temp_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

import Pyro4

# User interface process
@Pyro4.expose
class user(object):
	#Initialization function
	def __init__(self,name,proxy):
		self.name = name
		self.proxy = proxy
		self.running = True
		self.server_proxy = Pyro4.Proxy("PYRONAME:example.network.server"+'@'+self.getIP("server")+':9090')
		self.backend_proxy = Pyro4.Proxy("PYRONAME:example.network.serverbackend"+'@'+self.getIP("serverbackend")+':9090')
		self.temp_proxy = Pyro4.Proxy("PYRONAME:example.network.tempsensor"+'@'+self.getIP("tempsensor")+':9090')
		self.door_proxy = Pyro4.Proxy("PYRONAME:example.network.doorsensor"+'@'+self.getIP("doorsensor")+':9090')
		self.motion_proxy = Pyro4.Proxy("PYRONAME:example.network.motionsensor"+'@'+self.getIP("motionsensor")+':9090')
		self.presence_proxy = Pyro4.Proxy("PYRONAME:example.network.presencesensor"+'@'+self.getIP("presencesensor")+':9090')
		self.bulb_proxy = Pyro4.Proxy("PYRONAME:example.network.lightbulb"+'@'+self.getIP("lightbulb")+':9090')
		self.outlet_proxy = Pyro4.Proxy("PYRONAME:example.network.smartoutlet"+'@'+self.getIP("smartoutlet")+':9090')

		# Starting server in different thread 
		task2 = self.start_server
		t2 = threading.Thread(target=task2,args=())
		t2.start()
		# Taking input in different thread
		task1 = self.take_input
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Get IP of node with name = name from config file
	def getIP(self,name):
		ip = None
		config_file = open('config.txt','r')
		for line in config_file.readlines():
			temp = line.split(' ')
			if temp[0] == name:
				ip = temp[1].rstrip('\n')
				config_file.close()
				return ip

	# Starting daemon loop
	def start_server(self):
		with Pyro4.Daemon() as daemon:
			self.daemon = daemon
			server_uri = daemon.register(self)
			with Pyro4.locateNS() as ns: 
				ns.register("example.network."+self.name, server_uri)
			daemon.requestLoop(loopCondition = self.device_running)
			print "stopped running"
	
	def stop_device(self):
		self.running = False

	def device_running(self):
		return self.running
	
	# Function to take input from user and make necessary changes
	def take_input(self):
		ans = raw_input("Is Physical clock is used for synchronization - Yes(Y) or Vector clock - No(n)")
		if ans == 'Y' or ans == 'y':
			print 'y'
			self.server_proxy.user_selection_event_order_clock(True)
		else:
			print 'n'
			self.server_proxy.user_selection_event_order_clock(False)
		menu = {"1":"Change Temperature", "2":"Change Door State", "3":"Move", "4":"Change Light Bulb State", "5":"Change Outlet State"}
		while(1):
			for key in sorted(menu.keys()):
				print key+": " + menu[key]
			ans = raw_input("What would you like to do? ")
			if ans=="1": 
				temp = raw_input("Enter new temperature: ")
				self.temp_proxy.user_change(temp)	
			elif ans=="2":
				temp = raw_input('Door ' + self.door_proxy.get_state() + '. Change? ')
				self.door_proxy.user_change()
			elif ans=="3":
				self.motion_proxy.user_change()
			elif ans=="4":
				temp = raw_input('Light Bulb ' + self.bulb_proxy.get_state() + '. Change? ')
				self.bulb_proxy.user_change()
			elif ans=="5":
				temp = raw_input('Door ' + self.outlet_proxy.get_state() + '. Change? ')
				self.outlet_proxy.user_change()
			elif ans !="":
				print "Sorry, user cannot do that"

# Main function
def main():
	name = "user"
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	temp = user(name, device_proxy)

if __name__ == '__main__':
	main()
