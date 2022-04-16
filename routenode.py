import threading
import time
from util import *
from sys import argv

LAST = False
my_port = -1
TIMER = -1

dv = dict()
rtng_tbl = dict()

def parse_peers():
        global LAST, TIMER
        peer_ports = []
        peer_costs = []
        ind = -1
        for i in range(5, len(argv), 2):
                ind = i
                if argv[i] == 'last':
                        LAST = True
                if LAST or i + 1 >= len(argv):
                        break
                peer_ports.append(Port(argv[i]))
                peer_costs.append(Cost(argv[i + 1]))
      
        if LAST and ind + 1 < len(argv) and argv[ind + 1].isnumeric():
                TIMER = argv[ind + 1]
        return peer_ports, peer_costs


def init_state_info(peer_ports, peer_costs):
        for i in range(len(peer_ports)):
                p_port = peer_ports[i]
                p_cost = peer_costs[i]
                dv[p_port] = p_cost
                rtng_tbl[p_port] = p_port
   
def node_init():
        peer_ports, peer_costs = parse_peers()
        init_state_info(peer_ports, peer_costs)
        

def dv_msg():
        global my_port
        s = str(time.time) + ' ' + str(my_port) + ' '  
        for k,v in dv.items():
                s+= str(k) + ' ' + str(v) + ' '
        return s               
 
def send_dv(socket):
        dv_dgram = dv_msg().encode()
        for k,v in dv.items():
                Send(socket, dv_dgram, ('127.0.0.1', k))        
        
def main():
        global LAST, TIMER, my_port, dv, rtng_tbl
        if len(argv)< 5:
                Die('Usage: routenode dv <r/p> <update-interval> <local-port> <neighbor1-port> <cost-1> <neighbor2-port> <cost-2> ...'\
                    '[last][<cost-change>]', False)    
        my_port = Port(argv[4])
        my_sock = Socket(my_port) 
        node_init()
        #print('PEER PORTS: ', peer_ports)
        #print('PEER COSTS: ', peer_costs)
        #print('LAST: ', LAST)
        #print('TABLE ', rtng_tbl)
        #print('DV: ', dv) 
        if LAST:
                send_dv()

        while(True):
                sender_msg, sender_addr = my_sock.recvfrom(SIZE) 
                print('NEW MSG: ', sender_msg)

if __name__ == '__main__':
        main()
