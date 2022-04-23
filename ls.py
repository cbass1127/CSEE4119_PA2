import threading
import time
import os
from util import *
import sys
import random


ROUTING_INTERVAL = 10
my_sock = None
MAX_SEQ_NO = sys.maxsize
SEQ_NO = -1
LAST = False
UPDATE_INTERVAL = -1
shared_tbl = False
my_port = -1
TIMER = -1
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

def update_lsa_info(msg, port):
        global my_port
        if port not in peer_links.keys():
                peer_links[port] = dict()
        for i in range(0, len(msg) - 1, 2):
                try:
                        p = Port(msg[i])
                        c = Cost(msg[i + 1])
                        peer_links[port][p] = c
                except Exception as e:
                        return

def vert_min_distance(verts, dist):
        minimum = sys.maxsize
        mvert = my_port 
        for vert in verts:
                if dist[vert] < minimum:
                        minimum = dist[vert]
                        mvert = vert
        return mvert

def dijkstra():
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
                if u == 2222:
                        print('dist[200] = ', dist[u])
                        print('DISTS: ', dist, 'VERTS: ', verts) 
                verts.remove(u)
                if u not in peer_links.keys():
                        continue
                for v in peer_links[u].keys():
                        alt = dist[u] + peer_links[u][v]
                        if alt < dist[v]:
                                dist[v] = alt
                                if v not in peers:
                                        rtng_tbl[v] = rtng_tbl[u]           
       
        print(dist)
        print(rtng_tbl)
        #print(peer_links)

def parse_peers_ls(argv):
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

def lsa_msg():
        global my_port, SEQ_NO
        s = str(my_port) + ' ' + str(time.time()) + ' '
        for k,v in lsa.items():
                s+=(str(k) + ' ' + str(v) + ' ' )
        return s.encode()


def send_lsa(omit = False, omits = None ):
        global my_sock
        dgram = lsa_msg()
        for peer in peers:
                if not omit or peer not in omits:        
                        Send(my_sock, dgram, ('127.0.0.1', peer))

def init_state_info_ls(peer_ports, peer_costs):
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
        peer_ports, peer_costs = parse_peers_ls(argv)
        print('PEER PORTS :', peer_ports)
        print('PEER COSTS : ', peer_costs)
        print('UPDATE INTERVAL: ', UPDATE_INTERVAL)
        print('LAST: ', LAST)
        init_state_info_ls(peer_ports, peer_costs)

def start_ls(argv):
        main_ls(argv)

def relay_msg(sender_message, omit = False, omits = None):
        global my_sock
        dgram = sender_message.encode()
        for peer in peers:
                if not omit or peer not in omits:
                        Send(my_sock, dgram, ('127.0.0.1', peer))

def message_proc(sender_message):
        global my_sock, shared_tbl, lock, peers_rcvd
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
                lock.release()
                return
        else:
                latest[port] = seqno
                peers_rcvd.add(msg_tup)
                relay_msg(sender_message, True, [port])

        update_lsa_info(msg[2:], port) 
        lock.release()
        if not shared_tbl:
                shared_tbl = True
                send_lsa()
                
def timer_send():
        global shared_tbl, UPDATE_INTERVAL
        while not shared_tbl:
                pass
        while True:
                time.sleep(UPDATE_INTERVAL + random.uniform(0, 1))
                send_lsa()

def timer_update():
        global shared_tbl, ROUTING_INTERVAL
        while not shared_tbl:
                pass
        while True:
                time.sleep(ROUTING_INTERVAL)
                dijkstra()
   
def main_ls(argv):
        global my_sock, my_port
        my_port = Port(argv[4])
        my_sock = Socket(my_port) 
        node_init_ls(argv)
        print(lsa) 
        if LAST:
                send_lsa()
                shared_tbl = True 
        if TIMER > 0:
                #tthread = threading.Thread(target = trigger_change, args = (my_sock,))
                #tthread.start()
                pass
        tthread = threading.Thread(target = timer_send)
        uthread = threading.Thread(target = timer_update)
        tthread.start()
        uthread.start()
        while(True):
                sender_msg, sender_addr = my_sock.recvfrom(SIZE) 
                pthread = threading.Thread(target = message_proc, args = (sender_msg.decode(), )) 
                pthread.start()

if __name__ == '__main__':
        main()
