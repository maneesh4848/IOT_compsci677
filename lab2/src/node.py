import time,sys,operator
import logging
import threading

#Logging
logger = logging.getLogger("my_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)

logger.addHandler(h)

import Pyro4

# Base class
@Pyro4.expose
class node(object):
	# Initialization function
	def __init__(self,name,proxy):
		self.name = None
		self.proxy = None
		self.uri = None
		self.devices = None
		self.vector = None
		self.dev_id = None
		self.running = True
		self.dev_status = None
		self.set_name_and_proxy(name,proxy)

		#Starting server in different thread 
		task1 = self.start_server
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
			ip = None
			config_file = open('config.txt','r')
			for line in config_file.readlines():
				temp = line.split(' ')
				if temp[0] == self.name:
					ip = temp[1]
					break    
			Pyro4.config.HOST = ip
			server_uri = daemon.register(self)
			with Pyro4.locateNS() as ns: 
				ns.register("example.network."+self.name, server_uri)
			daemon.requestLoop(loopCondition = self.device_running)
			print "stopped running"
	
	# Update devices and start vector clock
	def update_device_data(self,devices):
		self.devices = devices
		self.start_vector()
	  
	def stop_device(self):
		self.running = False

	def device_running(self):
		return self.running
	
	def setId(self,dev_id):
		self.dev_id = dev_id

	# Starting vector clock
	def start_vector(self):
		logger.info("started vector clock") 
		self.vector = [0] * len(self.devices)
		if self.dev_id == 1:
			self.initialize_dev_status()

	def get_devices(self):
		return self.devices

	def initialize_dev_status(self):
		self.status = ['0'] * len(self.devices)
	 
	def set_name_and_proxy(self,name,proxy):
		self.name = name
		self.proxy = proxy
	
	def set_uri(self,uri):
		self.uri = uri

	# Updating vector clock from others clock
	def update_vector_clock(self,vector):
		if self.dev_id == 0:
			pass
		else:
			#print "updating clock"
			for i in range(0,len(vector)):
				if i != self.dev_id:
					self.vector[i] = vector[i]

	# Updating vector clock due to own event
	def inc_vector(self):
		self.vector[self.dev_id] = self.vector[self.dev_id] + 1

