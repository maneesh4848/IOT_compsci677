import sys 
import logging
import threading
import pdb

#Logging
logger = logging.getLogger("backend_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

import Pyro4
from leader_elect import leader_elect

# Server Backend
@Pyro4.expose
class server_backend(leader_elect):
	#Initialization function
	def __init__(self,name,proxy,inp):
		leader_elect.__init__(self,name,proxy)
		self.inp = inp
		#self.server_proxy = Pyro4.Proxy("PYRONAME:example.network.server")
		self.server_proxy = Pyro4.Proxy("PYRONAME:example.network.server"+str(inp)+'@'+self.getIP("server" + str(inp))+':9090')
		self.init_db()

	# Adding device to database in different thread
	def add_device_to_db_request_recieved(self,devicedata):
		#pdb.set_trace()
		self.add_device(int(devicedata["id"]),devicedata["name"])
		task1 = self.add_device_to_db
		devid = devicedata["id"]
		devtype = devicedata["type"]
		name = devicedata["name"]
		t1 = threading.Thread(target=task1,args=(devid,devtype,name))
		t1.start()

	# Initializing database
	def init_db(self):
		logger.info("Initializing database")
		F = open("devices" + str(self.inp) + ".txt","w")
		F.close()
		F2 = open('events' + str(self.inp) + '.txt',"w")
		F2.close()
		F = open("events_latest"+str(self.inp)+".txt","w")
		F.close()

	# Adding device to database
	def add_device_to_db(self,devid,devtype,name):
		logger.info("Stored device data")
		F = open("devices"+str(self.inp)+".txt","a")
		textToStore = devid + "\t" + devtype + "\t" + name + "\n"
		F.write(textToStore)
		F.close()
			
	# Getting and returning device database
	def device_db_request(self):
		toreturn = {}
		F = open("devices"+str(self.inp)+".txt","r")
		for line in F.readlines():
			temp = line[:-1].split('\t')
			toreturn[int(temp[0])] = temp[2]
		return toreturn
		
	# Adding event to database
	def add_event_to_db(self,devid,state,phy_clock,logic_clock):
		#pdb.set_trace()
		#self.inc_vector()
		#self.send_vector_clock_to_server()
		logger.info("Stored event data of " + self.devices[int(devid)] + ": " + state)
		#print phy_clock,type(phy_clock)
		F = open("events"+str(self.inp)+".txt","a")
		desc = ""
		desc += self.devices[int(devid)] + "," +state
		textToStore = str(devid) + "\t" + desc + "\t" + phy_clock + "\t" + ','.join(map(str,logic_clock)) + "\n"
		F.write(textToStore)
		F.close()

	# Adding event to latest_database
	def add_latest_event_to_db(self,devid,state,phy_clock,logic_clock):
		#pdb.set_trace()
		logger.info("Stored latest event data of " + self.devices[int(devid)] + ": " + state)
		#print phy_clock,type(phy_clock)
		F = open("events_latest"+str(self.inp)+".txt","a")
		desc = ""
		desc += self.devices[int(devid)] + "," +state
		textToStore = str(devid) + "\t" + desc + "\t" + phy_clock + "\t" + ','.join(map(str,logic_clock)) + "\n"
		F.write(textToStore)
		F.close()

	# Refreshing latest event database
	def remove_latest_event_entry(self):
		F = open("events_latest"+str(self.inp)+".txt","w")
		F.close()

	# Getting and returning latest event of device id = devid
	def get_latest_event(self,devid):
		logger.info("Getting latest event of: " + self.devices[int(devid)])
		F = open("events_latest"+str(self.inp)+".txt","r")
		lines = F.readlines()[::-1]
		for line in range(len(lines)):
			temp = lines[line].split('\t')
			if temp[0] == str(devid):
				return lines[line][:-1]
		return None
	
	# Sending vector clock to server
	def send_vector_clock_to_server(self):
		self.server_proxy.update_server_vector(self.dev_id,self.vector)
	
# Main Function
def main():
	#inp = int(raw_input('choose 1 or 2 '))
	inp = int(sys.argv[1])
	name = "serverbackend"+str(inp)
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	backend = server_backend(name, device_proxy, inp)

if __name__ == '__main__':
	main()
