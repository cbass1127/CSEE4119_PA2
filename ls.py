import threading
import time
import os
from util import *
import sys
import random


ROUTING_INTERVAL = 30
TRIGGER_CHANGE  = 1.2*ROUTING_INTERVAL #timer for triggered link-cost change.
TRIGGERED = False
my_sock = None #socket to send messages
MAX_SEQ_NO = sys.maxsize 
SEQ_NO = -1 
LAST = False #LAST in CL input?
UPDATE_INTERVAL = -1 
shared_tbl = False
my_port = -1
TIMER = -1 #value link-cost change gets set to.
dv = dict()
lock = threading.Semaphore(1)


rtng_tbl = dict()
latest = dict()
peer_links = dict()
lsa = dict()
peers = set()
peers_rcvd = set()
peer_links = dict()
shortest_path = dict()

def display_rtng_tbl(dist):
        '''
        Prints routing table
        :return: None
        ''' 
        global my_port
        pmessage('Node {0} Routing Table\n'.format(my_port))
        for k in sorted(dist.keys()):
                if dist[k] == float('inf'):
                        continue
                if k == my_port:
                        continue
                print('- (' + str(dist[k])  + ') -> Node ' + str(k), end = '')
                if rtng_tbl[k] != k:
                        print('; Next hop -> Node ' + str(rtng_tbl[k]), end = ' ')
                print()

def display_ntwk_top():
        '''
        Prints known network topology
        :return: None
        ''' 
        global my_port
        pmessage('Node {0} Network topology\n'.format(my_port))
        for k in sorted(peer_links.keys()):
#                if k == my_port:
#                        continue
                if len(peer_links[k].keys()) == 0:
                        continue
                for d in sorted(peer_links[k].keys()):
                        print('- (' + str(peer_links[k][d])  + ') from Node  ' + str(k) + ' to Node ' + str(d), end = '')
                        print()

def update_lsa_info(msg, port):
        '''
        Updates known information about topology. If there is a change, run dijkstra
        :return: None
        ''' 
        global my_port
        changed = False
        if port not in peer_links.keys():
                peer_links[port] = dict()
                changed = True 
        for i in range(0, len(msg) - 1, 2):
                try:
                        p = Port(msg[i])
                        c = Cost(msg[i + 1])
                        if p in peer_links[port].keys() and c != peer_links[port][p]\
                        or p not in peer_links[port].keys():
                                changed = True
                        peer_links[port][p] = c
                except Exception as e:
                        return
        if changed:
                display_ntwk_top()
                dijkstra()

def link_change(msg):
        '''
        Updates local link-cost 
        :return: None
        ''' 
        try:
                peer = Port(msg[0], False)
                newcost = Cost(msg[1], False)      
                lsa[peer] = newcost
                pmessage('Node {} cost updated to {}'.format(peer, newcost))
        except:
                return

def vert_min_distance(verts, dist):
       '''
       Gets the destination w/ the minimum distance
       for dijkstras algo 
       :return: node with closest distance 
       ''' 
       minimum = float('inf')
       mvert = -1 
       for vert in verts:
                if dist[vert] <= minimum:
                        minimum = dist[vert]
                        mvert = vert
       return mvert


def dijkstra():
        '''
        Dijkstra's shortest path algorithm. Updates routing table
        with next hop in shortest path.
        :return: None 
        ''' 
        global my_port
        dist = dict()
        verts = set()
        for p in peers:  
                dist[p] = lsa[p]
                verts.add(p) 
        for peer in peer_links:
                for link in peer_links[peer].keys():        
                        dist[link] = float('inf')
                        verts.add(link)
        verts.add(my_port)
        dist[my_port] = 0
        while verts:
                u = vert_min_distance(verts, dist)
                if u == -1:
                        break
                verts.remove(u)
                if u not in peer_links.keys():
                        continue
                for v in peer_links[u].keys():
                        alt = dist[u] + peer_links[u][v]
                        if alt < dist[v]:
                                dist[v] = alt
                                if u != v and u != my_port:
                                        rtng_tbl[v] = rtng_tbl[u]           
                                                
        display_rtng_tbl(dist)
        #print(dist)
        #print(rtng_tbl)
        #print(peer_links)

def parse_peers_ls(argv):
        '''
        Take in CL args specifying link state settings and local network topology.
        :return: peer_ports and peer_costs specifying local topology
        ''' 
        global LAST, TIMER, UPDATE_INTERVAL
        peer_ports = []
        peer_costs = []
        ind = -1
        
        UPDATE_INTERVAL = Interval(argv[3])

        for i in range(5, len(argv), 2):
                ind = i
                if argv[i] == 'last':
                        LAST = True
                if LAST or i + 1 >= len(argv):
                        break
                peer_ports.append(Port(argv[i]))
                peer_costs.append(Cost(argv[i + 1]))
      
        if LAST and ind + 1 < len(argv) and argv[ind + 1].isnumeric():
                TIMER = int(argv[ind + 1])
        return peer_ports, peer_costs

def lsa_msg(trigger = False):
        '''
        Generates Link-state message to send over network.
        :return: Formatted message to send over network 
        ''' 
        global my_port, SEQ_NO
        seqno = str(time.time())
        if not trigger:
                s = str(my_port) + ' ' + seqno + ' '
                for k,v in lsa.items():
                        s+=(str(k) + ' ' + str(v) + ' ' )
        else:
                s = 'T ' + str(my_port) + ' ' + str(TIMER) + ' '
        return s.encode(), seqno

def send_lsa(omit = False, omits = None ):
        '''
        Send link state to all neigbors.
        :return: None
        ''' 
        global my_sock, my_port
        dgram, seqno = lsa_msg()
        for peer in peers:
                if not omit or peer not in omits:        
                        pmessage('''LSA of Node {} with sequence number {} sent to Node {}'''.format(my_port, seqno, peer))
                        Send(my_sock, dgram, ('127.0.0.1', peer))

def send_trigger_lsa(peer):
        '''
        Sends message notifying timed link-cost change.
        :return: None
        ''' 
        global my_sock, my_port
        dgram, seqno = lsa_msg(True)
        Send(my_sock, dgram, ('127.0.0.1', peer))
        pmessage('Link value message sent from Node {} to Node {}'.format(my_port, peer))

def init_state_info_ls(peer_ports, peer_costs):
        '''
        Intializes ls data structures.
        :return: None
        ''' 
        for i in range(len(peer_ports)):
                p_port = peer_ports[i]
                p_cost = peer_costs[i]
                peers.add(p_port)
                peer_links[p_port] = dict()
                lsa[p_port] = p_cost
                shortest_path[p_port] = p_cost
                rtng_tbl[p_port] = p_port
                latest[p_port] = time.time()
        peer_links[my_port] = lsa
        rtng_tbl[my_port] = my_port

def node_init_ls(argv):
        '''
        Initialzes this ls instance
        :return: None
        '''
        peer_ports, peer_costs = parse_peers_ls(argv)
        #print('PEER PORTS :', peer_ports)
        #print('PEER COSTS : ', peer_costs)
        #print('UPDATE INTERVAL: ', UPDATE_INTERVAL)
        #print('LAST: ', LAST)
        #print('LINK CHANGE: ', TIMER)
        init_state_info_ls(peer_ports, peer_costs)

def start_ls(argv):
        '''
        Called from routenode.py start ls mode
        :return: None
        '''
        main_ls(argv)

def relay_msg(sender_message, port, seqno, omit = False, omits = None):
        '''
        Passes on link-state message from peer to neigbors
        :return: None
        '''
        global my_sock
        dgram = sender_message.encode()
        for peer in peers:
                if not omit or peer not in omits:
                        pmessage('''LSA of Node {} with sequence number {} sent to Node {}'''.format(port, seqno, peer))
                        Send(my_sock, dgram, ('127.0.0.1', peer))

def message_proc(sender_message, s_port):
        '''
        Proccesses incoming message from network, updating ls and relaying messages if needed.
        Also makes sure same message not relayed twice by keeping set of messages recieved w/ their
        seqununce number
        :return: None
        '''
        global my_sock, shared_tbl, lock, peers_rcvd
        msg = sender_message.split()
        if msg[0] == 'T':
                pmessage('Link value message received at Node {} from Node {}'.format(my_port, s_port))
                link_change(msg[1:])
                display_ntwk_top()
                dijkstra()
                send_lsa()
                return
        try:
                msg = sender_message.split()
                port = Port(msg[0], False)
                seqno = float(msg[1])
        except Exception as e:
                return
        msg_tup = (port, seqno)

        lock.acquire()
        isstale = False
        if port in latest.keys():
                isstale = seqno < float(latest[port])
        if isstale:
                peers_rcvd.remove(msg_tup)
                lock.release()
                return
        if msg_tup in peers_rcvd:
                pmessage(
                '''DUPLICATE LSA packet Received, AND DROPPED:
                        - LSA of node {}
                        - Sequence number {}
                        - Received from {}'''.format(port, seqno, s_port))
                lock.release()
                return
        else:
                pmessage('''LSA of node {} with sequence number {} received from Node {}'''.format(port, seqno, s_port))
                latest[port] = seqno
                peers_rcvd.add(msg_tup)
                relay_msg(sender_message, port, seqno, True, [port])
        update_lsa_info(msg[2:], port) 
        lock.release()
        if not shared_tbl:
                shared_tbl = True
                send_lsa()
                
def trigger_cost_change():
        '''
        Begin link-cost change locally and eventually tell neigbor
        :return: None
        '''
        global TIMER
        largest = max(peers) 
        lsa[largest] = TIMER
        pmessage('Node {} cost updated to {}'.format(largest, TIMER))
        dijkstra()
        send_trigger_lsa(largest)
        send_lsa()

def timer_send():
        '''
        Send the link-state to all neigbors on a timer. Handled by specfic thread.
        :return: None
        '''
        global shared_tbl, UPDATE_INTERVAL
        while not shared_tbl:
                pass
        while True:
                time.sleep(UPDATE_INTERVAL + random.uniform(0, 1))
                send_lsa()

def timer_update():
        '''
        Run dijkstras algorithm for the first time after ROUTING_INTERVAL. Handled by specfic thread.
        :return: None
        '''
        global shared_tbl, ROUTING_INTERVAL
        time.sleep(ROUTING_INTERVAL)
        dijkstra()

def timer_trigger():
        '''
        Wait for TRIGGER_CHANGE to initiate link-cost change if necessary.
        :return: None
        '''
        global TRIGGER_CHANGE
        time.sleep(TRIGGER_CHANGE)
        trigger_cost_change()

def main_ls(argv):
        '''
        Main function spawns threads to handle incoming messages and starts
        other threads to handle link-cost change and first dijkstras run.
        :return: None
        '''
        global my_sock, my_port
        my_port = Port(argv[4])
        my_sock = Socket(my_port) 
        node_init_ls(argv)
        display_ntwk_top()
        if LAST:
                send_lsa()
                shared_tbl = True 
        if TIMER > 0:
                gthread = threading.Thread(target = timer_trigger)
                gthread.start()
        tthread = threading.Thread(target = timer_send)
        uthread = threading.Thread(target = timer_update)
        tthread.start()
        uthread.start()
        while True:
                sender_msg, sender_addr = my_sock.recvfrom(SIZE) 
                pthread = threading.Thread(target = message_proc, args = (sender_msg.decode(), sender_addr[1])) 
                pthread.start()

