import sys,time
import logging,datetime
import threading

#Logging
logger = logging.getLogger("door_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

from server_gateway import server_gateway
from leader_elect import leader_elect
import Pyro4

# Door Sensor
@Pyro4.expose
class doorsensor(leader_elect):
	#Initialization function
	def __init__(self,name,proxy):
		leader_elect.__init__(self,name,proxy)
		self.state = "close"
		self.get_server()
		#self.server_proxy = Pyro4.Proxy("PYRONAME:example.network.server"+'@'+self.getIP("server")+':9090')
		time.sleep(1)
		self.registerwithserver()
		# Taking input in different thread
		task1 = self.take_input
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Getting Server with lesser load
	def get_server(self):
		server1_proxy = Pyro4.Proxy("PYRONAME:example.network.server1"+'@'+self.getIP("server1")+':9090')
		server2_proxy = Pyro4.Proxy("PYRONAME:example.network.server2"+'@'+self.getIP("server2")+':9090')
		dev_num1 = server1_proxy.get_num_devices()
		dev_num2 = server2_proxy.get_num_devices()
		if dev_num1 <= dev_num2:
			self.server_proxy = server1_proxy
		else:
			self.server_proxy = server2_proxy
		print self.server_proxy

	# Input Function
	# State change notified to server_gateway
	def take_input(self):
		while(1):
			temp = raw_input('Door ' + self.state + '. Change? ')
			if temp == "end":
				break
			else:
				#self.inc_vector()
				if self.state == "open":
					self.state = "close"
					self.server_proxy.request_state(self.dev_id,self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector)
				else:
					self.state = "open"
					self.server_proxy.request_state(self.dev_id,self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector)
		self.stop_device()
	
	# Input from user.py process
	# State change notified to server_gateway
	def user_change(self):
		#self.inc_vector()
		if self.state == "open":
			self.state = "close"
			self.server_proxy.request_state(self.dev_id,self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector)
		else:
			self.state = "open"
			self.server_proxy.request_state(self.dev_id,self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector)

	def get_state(self):
		return self.state
	
	# Register with server_gateway
	def registerwithserver(self):
		self.server_proxy.register_request_received("sensor",self.name)
		logger.info("Registered with server")

	# Query state process, sends door state, synchronized time and logical vector back as acknowledgement
	def query_state(self):
		return self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector

	# Change server in failure recovery state
	def change_server(self,proxy):
		self.server_proxy = proxy
		print "Server proxy changed to:", self.server_proxy

# Main Function
def main():
	name = "doorsensor"
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	door = doorsensor(name, device_proxy)

if __name__ == '__main__':
	main()
