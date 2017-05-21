import sys,time
import logging,datetime
import threading
import pdb

#Logging
logger = logging.getLogger("motion_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

from server_gateway import server_gateway
from leader_elect import leader_elect
import Pyro4

# Motion Sensor
@Pyro4.expose
class motionsensor(leader_elect):
	#Initialization function
	def __init__(self,name,proxy):
		leader_elect.__init__(self,name,proxy)
		self.state = "no_motion"
		self.server_proxy = Pyro4.Proxy("PYRONAME:example.network.server"+'@'+self.getIP("server")+':9090')
		time.sleep(1)
		self.registerwithserver()
		# Taking input in different thread
		task1 = self.take_input
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Input Function
	def take_input(self):
		while(1):
			temp = raw_input('Detect Motion? ')
			if temp == "end":
				break
			else:
				self.state = "motion"
				self.inc_vector()
				logger.info(str(self.vector))
				self.send_data_to_server()
				self.state = "no_motion"
		self.stop_device()

	# Input from user.py process, sends push notification to server
	def user_change(self):
		self.state = "motion"
		self.inc_vector()
		logger.info(str(self.vector))
		self.send_data_to_server()
		self.state = "no_motion"

	# Push data to server on event - notification
	def send_data_to_server(self):
		#pdb.set_trace()
		vector_str = ','.join(map(str,self.vector))
		state_str = str(self.state)
		sync_str = str(datetime.datetime.now()+self.sync_time_offset)
		self.server_proxy.request_state(self.dev_id,state_str,sync_str,self.vector)
	
	# Register with server_gateway
	def registerwithserver(self):
		self.server_proxy.register_request_received("sensor",self.name)
		logger.info("Registered with server")

	def setId(self,dev_id):
		self.dev_id = dev_id
	
	# Query state process, sends state, synchronized time and logical vector back as acknowledgement
	def query_state(self):
		return self.state,str(datetime.datetime.now()+self.sync_time_offset),self.vector

# Main Function
def main():
	name = "motionsensor"
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	motion = motionsensor(name, device_proxy)

if __name__ == '__main__':
	main()
