import time,sys,operator
import logging,datetime
import threading
import pdb

#Logging
logger = logging.getLogger("server_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

from server_backend import server_backend
from leader_elect import leader_elect
import Pyro4

# Server Gateway
@Pyro4.expose
class server_gateway(leader_elect):
	#Initialization function
	def __init__(self,name,proxy,backendname,inp):
		leader_elect.__init__(self,name,proxy)
		self.latest_id = int(self.name.split('r')[2])
		self.physicalClock = True
		self.dev_id = self.latest_id
		self.state = 0
		self.waiting_for_presence = False
		self.ispolling = False
		self.inp = inp
		self.backend_proxy = Pyro4.Proxy("PYRONAME:example.network." + backendname+'@'+self.getIP(backendname)+':9090')
		self.cache = []
		self.connected_devices = {}
		#self.cache_length = int(raw_input("Enter cache length: "))
		self.cache_length = str(sys.argv[2])
		self.other_server_running = True
		
		# Registering server processes and waiting for election
		self.process_register_request("gateway",name,1)
		self.process_register_request("gateway",backendname)
		task1 = self.poll_other_server
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Starts election when all processes come alive
	def wait_for_election(self):
		while(1):
			if self.latest_id >= 8:
				break
		self.start_election()

	# Getting proxy of other server if it is running
	def get_other_server(self):
		if self.other_server_running:
			otherserver = "server2"
			if self.inp == 2:
				otherserver = "server1"
			otherserver = "server1" if self.inp == 2 else "server2"
			return Pyro4.Proxy("PYRONAME:example.network." + otherserver+'@'+self.getIP(otherserver)+':9090')
		return None
	
	# Received register request from a device
	def register_request_received(self,devtype,name):
		# Start new thread to process request
		task1 = self.process_register_request
		t1 = threading.Thread(target=task1,args=(devtype,name))
		t1.start()

	# User selection of clock from user.py process
	def user_selection_event_order_clock(self,isphysical):
		print "user selection clock"
		self.physicalClock = isphysical

	# Returns number of devices registered at this server
	def get_num_devices(self):
		return len(self.connected_devices.keys())

	# Processing device registration request
	def process_register_request(self,devtype,name,gateway_flag=0):
		#pdb.set_trace()
		#processing register request
		logger.info("Processing register request...")

		# generates unique id and add device to database
		devid = self.generate_id()
		devicedata = {"id":str(devid),"type":devtype,"name":name}
		if not gateway_flag:
			self.connected_devices[int(devicedata['id'])] = devicedata['name']
			self.add_device(int(devicedata['id']),devicedata['name'])
		self.backend_proxy.add_device_to_db_request_recieved(devicedata)
		if "server" not in name:
			if self.get_other_server() is not None:
				self.get_other_server().received_device_db_update_from_gateway(devicedata,"devices",False)
			logger.info("added device to db...")

		return_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+self.getIP(name)+':9090')
		#return_proxy = Pyro4.Proxy("PYRONAME:example.network."+name)
		if not gateway_flag:
			return_proxy.setId(devid)

	# Generates unique ID
	def generate_id(self):
		self.latest_id = self.latest_id + 2
		return self.latest_id-2

	# Message from other server (device or event)
	def received_device_db_update_from_gateway(self,entry,filename,poll):
		if filename == "devices":
			self.add_device(int(entry["id"]),entry["name"])
			self.backend_proxy.add_device_to_db_request_recieved(entry)
		else:
			#pdb.set_trace()
			logger.info(entry[0]+"-"+entry[1]+"-"+entry[2])
			self.backend_proxy.add_event_to_db(entry[0],entry[1],entry[2],entry[3])
			if poll == False:
				self.backend_proxy.add_latest_event_to_db(entry[0],entry[1],entry[2],entry[3])
				self.event_ordering_with_physical_clock(int(entry[0]),entry[1])

	# Request state function, called by push notifications
	def request_state(self,dev_id,state,time,vector):
		logger.info(self.devices[dev_id] + " pushed state of " + self.devices[dev_id] +": " + state +  " to server")
		# Polling door and temperature sensors
		if self.ispolling == False:
			task1 = self.poll_door_state
			t1 = threading.Thread(target=task1,args=())
			t1.start()
			task2 = self.poll_temp_state
			t2 = threading.Thread(target=task2,args=())
			t2.start()
			self.ispolling = True
		
		# Adding events to latest database
		self.backend_proxy.add_latest_event_to_db(dev_id,state,time,vector)
		# Starting event ordering
		if (self.physicalClock):
			before = datetime.datetime.now()
			self.event_ordering_with_physical_clock(dev_id,state)
			print "Response Time:",datetime.datetime.now() - before
		#else:
		#	self.event_ordering_with_vector_clock(dev_id,state)

		# Updating server vector and adding event to database
		#self.update_server_vector(dev_id,vector)
		self.add_event_to_cache(str(dev_id),state,time,vector)
		entry = [str(dev_id),state,time,vector]
		if self.get_other_server() is not None:
			self.get_other_server().received_device_db_update_from_gateway(entry,"events",False)
		self.backend_proxy.add_event_to_db(dev_id,state,time,vector)

	def event_ordering_with_physical_clock(self,dev_id,state):
		#print(dev_id,state)
		# End reached, clearing latest database and moving to idle state on door close
		if (self.state == 6 or self.state == 4 or self.state == 3) and (self.devices[dev_id]=='doorsensor' and state == 'close'):
			self.backend_proxy.remove_latest_event_entry()
			logger.info('**********STATE IDLE***********')
			self.state = 0
		# IDLE state, waiting for sensors
		elif self.state == 0:
			logger.info("state 0")
			if self.devices[dev_id] == 'doorsensor'  and state == 'open':
				logger.info('Door sensor data received')
				self.state = 1
			elif self.devices[dev_id] == 'motionsensor':
				self.state = 1
				logger.info('Motion sensor data received')
		elif self.state == 1:
			logger.info("state 1")
			if self.devices[dev_id] == 'doorsensor' and state == 'open':
				logger.info('Door sensor data received')
			elif self.devices[dev_id] == 'motionsensor':
				logger.info('Motion sensor data received')
			motionline = None
			doorline = None
			for i in self.devices:
				if self.devices[i] == 'motionsensor':
					be = datetime.datetime.now()
					motionline = self.get_event_from_cache(str(i))
					print "Cache Read Time:", datetime.datetime.now() - be
					if motionline == None:
						logger.info("CACHE MISS")
						be = datetime.datetime.now()
						motionline = self.backend_proxy.get_latest_event(i)
						print "Database Read Time:", datetime.datetime.now() - be
				elif self.devices[i] == 'doorsensor':
					be = datetime.datetime.now()
					doorline = self.get_event_from_cache(str(i))
					print "Cache Read Time:", datetime.datetime.now() - be
					if doorline == None:
						logger.info("CACHE MISS")
						be = datetime.datetime.now()
						doorline = self.backend_proxy.get_latest_event(i)
						print "Database Read Time:", datetime.datetime.now() - be
			if motionline == None or doorline == None:
				pass
			else:
				#pdb.set_trace()
				logger.info('motionline' + motionline)
				logger.info('doorline' + doorline)
				phy_motion_millisec = ((motionline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
				phy_door_millisec	= ((doorline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
				phy_motion_sec = (((motionline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1] + phy_motion_millisec
				phy_door_sec	= (((doorline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1] + phy_door_millisec

				phy_door_mins = (((doorline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[1]
				phy_motion_mins = (((motionline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[1]  
				logger.info('Door sensor data received at '+ str(float(phy_door_sec)+60.00*float(phy_door_mins)))
				logger.info('Motion sensor data received at '+ str(float(phy_motion_sec)+60.00*float(phy_motion_mins)))
				#print "***************motion"+str(float(phy_motion_sec)+60.00*float(phy_motion_mins))
				#print "***************door"+str(float(phy_door_sec)+60.00*float(phy_door_mins))
				if	float(phy_motion_sec)+60.00*float(phy_motion_mins)>float(phy_door_sec)+60.00*float(phy_door_mins) :
					#print "state 2"
					self.state = 2
					self.waiting_for_presence = True
					self.wait_for_presence()
				
				#AWAY STATE
				else :
					#print "state 6"
					self.state = 6
					print "**********USER LEAVES HOME************"
					for device in self.devices:
						 # Switching off bulb and outlet
						if self.devices[device] == 'lightbulb':

							logger.info('Switching off Bulbs')
							device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
							#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
							device_proxy.change_state('off')
							self.inc_vector()
						if self.devices[device] == 'smartoutlet':
							
							logger.info('Switching of Outlets')
							device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
							#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
							device_proxy.change_state('off')
							self.inc_vector()

		elif self.state == 2:
			logger.info("state 2")
			self.waiting_for_presence = False
			presenceline = None
			for i in self.devices:
				if self.devices[i] == 'presencesensor':

					logger.info('Presence sensor data received')
					be = datetime.datetime.now()
					presenceline = self.get_event_from_cache(str(i))
					print "Cache Read Time:", datetime.datetime.now() - be
					if presenceline == None:
						logger.info("CACHE MISS")
						be = datetime.datetime.now()
						presenceline = self.backend_proxy.get_latest_event(i)
						print "Database Read Time:", datetime.datetime.now() - be
			# ALERT STATE
			if presenceline == None:

				logger.info('Presence sensor data is not received')
				print "**********INTRUDER ALERT************"
				self.state = 4
				# Switching on bulb and off outlet
				for device in self.devices:
					if self.devices[device] == 'lightbulb':
						logger.info('Switching on lightbulb')
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy.change_state('on')
						self.inc_vector()
					if self.devices[device] == 'smartoutlet':
							
						logger.info('Switching off outlets')
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('off')
						self.inc_vector()
			
			# User comes back home
			else:
				print "**********USER ENTERS HOME************"
				self.state = 3
				# Switching on bulb and outlet
				for device in self.devices:
					if self.devices[device] == 'lightbulb':
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('on')
						logger.info('Switching on lightbulb')
						self.inc_vector()
					if self.devices[device] == 'smartoutlet':
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('on')
						logger.info('Switching on outlet')
						self.inc_vector()

	# Function to check if motion sensor activated first or door sensor activated first
	def istimefirst(self,time,motion):
		timearray = time.split(',')
		motionarray = motion.split(',')
		for i in range(0,len(timearray)):
			if timearray[i] > motionarray[i]:
				return 1
			elif timearray[i] < motionarray[i]:
				return 0
		return 2

	# Waiting for beacon from presence sensor
	def wait_for_presence(self):
		time.sleep(5)
		if self.waiting_for_presence == True:
			self.waiting_for_presence = False
			if(self.physicalClock):
				self.event_ordering_with_physical_clock(1,'open')
			else:
				self.event_ordering_with_vector_clock(1,'open')

	# Update server vector and start multicast
	def update_server_vector(self,dev_id,vector):
		self.vector[dev_id] = vector[dev_id]
		logger.info(str(vector))
		task1 = self.multicast_vector
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Multicast vector to all sensors,devices
	def multicast_vector(self):
		for device in self.devices:
			#dev_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
			dev_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
			dev_proxy.update_vector_clock(self.vector)

	# Pull state from devices, sensors
	def pull_state(self,dev_id,name):
		#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device])
		device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
		device_proxy.query_state()
		
	# Polling door sensor state
	def poll_door_state(self):
		while(1):
			for device in self.devices:
				if self.devices[device] == 'doorsensor':
					#pdb.set_trace()
					#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
					device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
					temp_state,temp_clock,temp_logic = device_proxy.query_state()
					entry = [str(device),temp_state,temp_clock,temp_logic]
					if self.get_other_server() is not None:
						try:
							self.get_other_server().received_device_db_update_from_gateway(entry,"events",True)
						except:
							pass
					#self.add_event_to_cache(str(device),temp_state,temp_clock,temp_logic)
					self.backend_proxy.add_event_to_db(str(device),temp_state,temp_clock,temp_logic)
					time.sleep(13)
		
	# Polling temerpature sensor state
	def poll_temp_state(self):
		while(1):
			for device in self.devices:
				if self.devices[device] == 'tempsensor':
					#pdb.set_trace()
					#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
					device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
					temp_state,temp_clock,temp_logic = device_proxy.query_state()
					entry = [str(device),temp_state,temp_clock,temp_logic]
					if self.get_other_server() is not None:
						try:
							self.get_other_server().received_device_db_update_from_gateway(entry,"events",True)
						except:
							pass
					#self.add_event_to_cache(str(device),temp_state,temp_clock,temp_logic)
					self.backend_proxy.add_event_to_db(str(device),temp_state,temp_clock,temp_logic)
					time.sleep(17)

	# Adding new event to cache
	def add_event_to_cache(self,devid,state,clock,logic):
		# Remove any redundant event
		self.check_and_remove_event(devid)
		# Remove based on LRU policy
		while len(self.cache) >= self.cache_length:
			self.delete_events_from_cache()
		# Insert at start of list
		self.cache.insert(0,[devid,state,clock,logic])

	# Delete from end of list
	def delete_events_from_cache(self):
		del self.cache[len(self.cache)-1]
	
	# Remove event which belongs to device devid
	def check_and_remove_event(self,devid):
		#pdb.set_trace()
		temp_cache = []
		#print self.cache, devid
		# Only recording events which do not belong to device devid
		for i in range(len(self.cache)):
			#print "****",i,"****",len(self.cache),"****"
			if self.cache[i][0] != str(devid):
				temp_cache.append(self.cache[i])
		self.cache = list(temp_cache)
		
	# Getting event from cache if present, else None
	def get_event_from_cache(self,devid):
		print "Cache:", self.cache, "DevID:", devid
		for entry in self.cache:
			if entry[0] == devid:
				logger.info("CACHE HIT!!!!!!!!!!")
				temp_entry = devid + "\t" + self.devices[int(devid)] + "," + entry[1] + "\t" + entry[2]
				return temp_entry
		return None

	# Polling other server and initiating failure recovery on failure of other server
	def poll_other_server(self):
		while(self.other_server_running):
			try:
				self.get_other_server().heartbeat()
				#print self.devices, self.connected_devices
			except Exception as inst:
				logger.info("Other server crashed")
				self.other_server_running = False
				self.failure_recovery()
			time.sleep(5)
	
	# Heartbeat message
	def heartbeat(self):
		return "Alive"
	
	# Failure recovery mechanism
	def failure_recovery(self):
		logger.info("Initiating failure recovery")
		for i in self.devices:
			# Changing server of devices connected to other server
			if i not in self.connected_devices:
				device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[i]+'@'+self.getIP(self.devices[i])+':9090')
				device_proxy.change_server(self.proxy)
				self.connected_devices[i] = self.devices[i]
			print self.devices, self.connected_devices
	
# Main Function
def main():
	#inp = int(raw_input('choose 1 or 2 '))
	inp = int(sys.argv[1])
	name = "server"+str(inp)
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	gateway = server_gateway(name, device_proxy,"serverbackend"+str(inp),inp)

if __name__ == '__main__':
	main()
