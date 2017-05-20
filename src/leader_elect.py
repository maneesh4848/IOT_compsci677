import time,sys,operator
import pdb
import logging,datetime
import threading

#Logging
logger = logging.getLogger("leader_logger")
logger.setLevel(logging.DEBUG)

h = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
h.setFormatter(formatter)
logger.addHandler(h)

import Pyro4,Queue
from node import node
from multiprocessing.pool import ThreadPool

# Leader election and physical time synchronization class
@Pyro4.expose
class leader_elect(node):
	# Initialization function
	def __init__(self,name,proxy):
		node.__init__(self,name,proxy)
		self.leader_name = None
		self.wait_time = 5
		self.sync_time_offset = datetime.timedelta()
		
	def get_leader_name(self):
		return self.leader_name
	
	# Start bully election process
	def start_election(self,devices=None):
		# Stops flooding
		if self.leader_name != None:
			return
		#Only used by server_gateway in first call
		if devices == None:
			devices = self.backend_proxy.device_db_request()

		print devices
		bullies = []
		for key in devices:
			if key > self.dev_id:
				bullies.append(devices[key])
		print bullies
		count = 0
		for bully in bullies:
			bully_proxy = Pyro4.Proxy("PYRONAME:example.network."+bully+'@'+self.getIP(bully)+':9090')
			#bully_proxy = Pyro4.Proxy("PYRONAME:example.network."+bully)
			#Sending messages to processes of higher IDs
			try:
				bully_proxy.election_message(devices)
				self.wait_for_leader()
				break
			except Exception as e:
				print str(e)
				count += 1
		# No process with higher ID or all processes are not responding
		if count == len(bullies):
			self.broadcast_victory(devices)
		return

	# Waiting for higher ID process to become leader
	def wait_for_leader(self):
		time.sleep(self.wait_time)
		if self.leader_name == None:
			self.start_election()
		
	def leader_message(self,name):
		self.leader_name = name
	
	# Broadasting victory message
	def broadcast_victory(self,devices):
		#print devices
		# Updating leader name and starting vector clock of all processes
		for device in devices:
			device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device]+'@'+self.getIP(devices[device])+':9090')
			#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device])
			if device_proxy.get_leader_name() == None:
				task1 = device_proxy.leader_message
				t1 = threading.Thread(target=task1,args=(self.name,))
				t1.start()
			if device_proxy.get_devices() == None:
				print "starting vector clock"
				task2 = device_proxy.update_device_data
				t2 = threading.Thread(target=task2,args=(devices,))
				t2.start()
		
		# Leader election completed, starting time sync
		time.sleep(self.wait_time)
		print "Election done"
		print "Leader:" , self.leader_name
		if self.leader_name == self.name:
			task1 = self.start_time_sync
			t1 = threading.Thread(target=task1,args=(devices,))
			t1.start() 

	# Message received from process with lower ID
	def election_message(self,devices):
		#print devices
		task1 = self.start_election
		t1 = threading.Thread(target=task1,args=(devices,))
		t1.start()
		return "Alive"
	
	# Time synchronization process
	def start_time_sync(self,devices):
		while(1):
			delays = []
			device_offsets = []
			# Getting physical clocks and delays
			for device in devices:
				if devices[device] != self.name:
					device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device]+'@'+self.getIP(devices[device])+':9090')
					#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device])
					init_time = datetime.datetime.now()
					offset_time_string = device_proxy.get_time_offset(init_time)
					offset_time=offset_time_string.split(':')[-1]
					seconds=float(offset_time)
					device_offsets.append(seconds)
					delays.append((datetime.datetime.now() - init_time).total_seconds())
			# Getting avg times and avg delay
			avg_delay = sum(delays)/len(delays)/2

			new_time = sum(device_offsets)/len(device_offsets)
			# Sending offset time to all processes
			for device in devices:
				#device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device])
				device_proxy = Pyro4.Proxy("PYRONAME:example.network."+devices[device]+'@'+self.getIP(devices[device])+':9090')
				date_time = round(new_time+avg_delay,6)
				device_proxy.receive_new_time(date_time)
			
			"""print "Time Sync Done."
			print "Time Offset: ", new_time+avg_delay"""
			time.sleep(8)
	
	# Returns time offset
	def get_time_offset(self,init_time):
		init_time = datetime.datetime.strptime(init_time, "%Y-%m-%dT%H:%M:%S.%f")
		return str(datetime.datetime.now()-init_time)
	
	# Update clock offset from arguments
	def receive_new_time(self,new_time_offset):
		self.sync_time_offset = datetime.timedelta(seconds = new_time_offset)
