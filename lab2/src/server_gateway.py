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
	def __init__(self,name,proxy,backendname):
		leader_elect.__init__(self,name,proxy)
		self.latest_id = 0
		self.physicalClock = True
		self.dev_id = self.latest_id
		self.state = 0
		self.waiting_for_presence = False
		self.ispolling = False
		self.backend_proxy = Pyro4.Proxy("PYRONAME:example.network." + backendname+'@'+self.getIP(backendname)+':9090')
		
		# Registering server processes and waiting for election
		self.process_register_request("gateway",name,1)
		self.process_register_request("gateway",backendname)
		task1 = self.wait_for_election
		t1 = threading.Thread(target=task1,args=())
		t1.start()

	# Starts election when all processes come alive
	def wait_for_election(self):
		while(1):
			if self.latest_id >= 8:
				break
		self.start_election()

	def start_backend(self):
		self.backend = server_backend()

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

	# Processing device registration request
	def process_register_request(self,devtype,name,gateway_flag=0):
		#pdb.set_trace()
		#processing register request
		logger.info("Processing register request...")

		# generates unique id and add device to database
		devid = self.generate_id()
		devicedata = {"id":str(devid),"type":devtype,"name":name}
		self.backend_proxy.add_device_to_db_request_recieved(devicedata)
		logger.info("added device to db...")

		return_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+self.getIP(name)+':9090')
		#return_proxy = Pyro4.Proxy("PYRONAME:example.network."+name)
		if not gateway_flag:
			return_proxy.setId(devid)

	# Generates unique ID
	def generate_id(self):
		self.latest_id = self.latest_id + 1
		return self.latest_id-1
	
	# Request state function, called by push notifications
	def request_state(self,dev_id,state,time,vector):
		#pdb.set_trace()
		logger.info("Pushed state to server")
		#print dev_id, state
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
			self.event_ordering_with_physical_clock(dev_id,state)
		else:
			self.event_ordering_with_vector_clock(dev_id,state)

		# Updating server vector and adding event to database
		self.update_server_vector(dev_id,vector)
		#print self.sync_time_offset, type(self.sync_time_offset)
		#self.backend_proxy.add_event_to_db(dev_id,state,datetime.datetime.now()+self.sync_time_offset,vector)
		self.backend_proxy.add_event_to_db(dev_id,state,time,vector)

	# Event ordering function with synchronized physical clock
	def event_ordering_with_physical_clock(self,dev_id,state):
		# End reached, clearing latest database and moving to idle state on door close
		if self.state == 6 or self.state == 4 or self.state == 3 and self.devices[dev_id]=='doorsensor' and state == 'close':
			self.backend_proxy.remove_latest_event_entry()
			logger.info('**********STATE IDLE***********')
			self.state = 0
		# IDLE state, waiting for sensors
		elif self.state == 0:
			if self.devices[dev_id] == 'doorsensor':
				logger.info('Door sensor data received')
			else:
				logger.info('Motion sensor data received')
			self.state = 1
		elif self.state == 1:
			if self.devices[dev_id] == 'doorsensor':
				logger.info('Door sensor data received')
			else:
				logger.info('Motion sensor data received')
			motionline = None
			doorline = None
			for i in self.devices:
				if self.devices[i] == 'motionsensor':
					motionline = self.backend_proxy.get_latest_event(i)
				elif self.devices[i] == 'doorsensor':
					doorline = self.backend_proxy.get_latest_event(i)
			if motionline == None or doorline == None:
				pass
			else:
				phy_motion_sec = '0.'+((motionline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
				phy_door_sec   = '0.'+((doorline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
				phy_motion_mins = (((motionline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1]
				phy_door_mins   = (((doorline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1]

				logger.info('Door sensor data received at'+ str(float(phy_door_sec)+60.00*float(phy_door_mins)))
				logger.info('Motion sensor data received at'+ str(float(phy_motion_sec)+60.00*float(phy_motion_mins)))
				#print "***************motion"+str(float(phy_motion_sec)+60.00*float(phy_motion_mins))
				#print "***************door"+str(float(phy_door_sec)+60.00*float(phy_door_mins))
				if  float(phy_motion_sec)+60.00*float(phy_motion_mins)>float(phy_door_sec)+60.00*float(phy_door_mins) :
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
			self.waiting_for_presence = False
			presenceline = None
			for i in self.devices:
				if self.devices[i] == 'presencesensor':

					logger.info('Presence sensor data received')
					presenceline = self.backend_proxy.get_latest_event(i)
			# ALERT STATE
			if presenceline == None:

				logger.info('presence sensor data is not received')
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

	# Event ordering function with vector clock
	def event_ordering_with_vector_clock(self,dev_id,state):
		# End reached, clearing latest database and moving to idle state on door close
		if self.state == 6 or self.state == 4 or self.state == 3 and self.devices[dev_id]=='doorsensor' and state == 'close':
			self.backend_proxy.remove_latest_event_entry()
			self.state = 0
			logger.info("*********STATE IDLE************")
		# IDLE state, waiting for sensors
		elif self.state == 0:
			if self.devices[dev_id] == 'doorsensor':
				logger.info('Door sensor data received')
			else:
				logger.info('Motion sensor data received')
			self.state = 1
		elif self.state == 1:
			motionline = None
			doorline = None
			if self.devices[dev_id] == 'doorsensor':
				logger.info('Door sensor data received')
			else:
				logger.info('Motion sensor data received')
			for i in self.devices:
				if self.devices[i] == 'motionsensor':
					motionline = self.backend_proxy.get_latest_event(i)
				elif self.devices[i] == 'doorsensor':
					doorline = self.backend_proxy.get_latest_event(i)
			if motionline == None or doorline == None:
				#print "test1"
				pass
			else:
				vector_time_motion = motionline.split('\t')[3]
				vector_time_door   = doorline.split('\t')[3]
				
				logger.info('motion occured at '+vector_time_motion)

				logger.info('door occured at '+vector_time_door)
				istimed = self.istimefirst(vector_time_motion,vector_time_door)
				if istimed==1:
					#print "state 2"
					self.state = 2
					self.waiting_for_presence = True
					self.wait_for_presence()
				#AWAY STATE
				elif istimed==0:
					#print "state 6"
					self.state = 6
					print "**********USER LEAVES HOME************"
					# Switching off bulb and outlet
					for device in self.devices:
						if self.devices[device] == 'lightbulb':
							#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
							device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
							device_proxy.change_state('off')
							logger.info("Switching off Bulbs")
					
						if self.devices[device] == 'smartoutlet':
							#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
							device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
							device_proxy.change_state('off')
							logger.info("Switching off Outlets")

				else:
					
					phy_motion_sec = '0.'+((motionline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
					phy_door_sec   = '0.'+((doorline.split('\t')[2]).split(' ')[-1]).split('.')[-1]
					phy_motion_mins = (((motionline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1]
					phy_door_mins   = (((doorline.split('\t')[2]).split(' ')[-1]).split('.')[0]).split(':')[-1]

					#print "***************motion"+str(float(phy_motion_sec)+60.00*float(phy_motion_mins))
					#print "***************door"+str(float(phy_door_sec)+60.00*float(phy_door_mins))
					if  float(phy_motion_sec)+60.00*float(phy_motion_mins)>float(phy_door_sec)+60.00*float(phy_door_mins) :
						#print "state 2"
						self.state = 2
						self.waiting_for_presence = True
						self.wait_for_presence()
					#AWAY STATE
					else :
						#print "state 6"
						self.state = 6
						print "**********USER LEAVES HOME************"
						 # Switching off bulb and outlet
						for device in self.devices:
							if self.devices[device] == 'lightbulb':
								#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
								device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
								device_proxy.change_state('off')
					
							if self.devices[device] == 'smartoutlet':
								#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
								device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
								device_proxy.change_state('off')

		elif self.state == 2:
			self.waiting_for_presence = False
			presenceline = None
			for i in self.devices:
				if self.devices[i] == 'presencesensor':
					logger.info("Presencesensor detected beacon")
					presenceline = self.backend_proxy.get_latest_event(i)
			# ALERT STATE
			if presenceline == None:

				logger.info("Preseencesensor detected no beacon")
				print "**********INTRUDER ALERT************"
				self.state = 4
				# Switching on bulb and off outlet
				for device in self.devices:
					if self.devices[device] == 'lightbulb':
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('on')
						logger.info("Switching on Bulbs")
					
					if self.devices[device] == 'smartoutlet':
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('off')
						logger.info("Switching off Outlets")
			
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
						
						logger.info("Switching on Bulbs")
					if self.devices[device] == 'smartoutlet':
						#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+self.devices[device])
						device_proxy = Pyro4.Proxy("PYRONAME:example.network." + self.devices[device]+'@'+self.getIP(self.devices[device])+':9090')
						device_proxy.change_state('on')
						logger.info("Switching on Outlets")

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
					self.backend_proxy.add_event_to_db(str(device),temp_state,temp_clock,temp_logic)
					time.sleep(17)

# Main Function
def main():
	name = "server"
	ip = None
	config_file = open('config.txt','r')
	for line in config_file.readlines():
		temp = line.split(' ')
		if temp[0] == name:
			ip = temp[1].rstrip('\n')
			config_file.close()
			break
	device_proxy = Pyro4.Proxy("PYRONAME:example.network." + name+'@'+ip+':9090')
	gateway = server_gateway(name, device_proxy,"serverbackend")

if __name__ == '__main__':
	main()
