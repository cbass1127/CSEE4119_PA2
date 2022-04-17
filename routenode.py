import threading
import time
from util import *
from sys import argv

LAST = False
shared_tbl = False
my_port = -1
TIMER = -1
dv = dict()
rtng_tbl = dict()
lock = threading.Semaphore(1)
latest = dict()
peer_dvs = dict()

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

def display_rtng_tbl():
        global my_port
        pmessage('Node {0} Routing Table\n'.format(my_port))
        for k in sorted(dv.keys()):
                if k == my_port:
                        continue
                print('- (' + str(dv[k])  + ') -> Node ' + str(k), end = '')
                if rtng_tbl[k] != k:
                        print('; Next hop -> Node ' + str(rtng_tbl[k]), end = ' ')
                print()

def init_state_info(peer_ports, peer_costs):
        for i in range(len(peer_ports)):
                p_port = peer_ports[i]
                p_cost = peer_costs[i]
                dv[p_port] = p_cost
                rtng_tbl[p_port] = p_port
                latest[p_port] = time.time()
        dv[my_port] = 0
        rtng_tbl[my_port] = my_port

def node_init():
        peer_ports, peer_costs = parse_peers()
        init_state_info(peer_ports, peer_costs)
        display_rtng_tbl()    

def dv_msg():
        global my_port
        s = str(time.time()) + ' ' + str(my_port) + ' '  
        for k,v in dv.items():
                if k == my_port:
                        continue
                s+= str(k) + ' ' + str(v) + ' '
        return s               
 
def send_dv(socket):
        global my_port
        dv_dgram = dv_msg().encode()
        for k,v in dv.items():
                if k == my_port:
                        continue
                Send(socket, dv_dgram, ('127.0.0.1', k))        
                pmessage('Message sent from Node {0} to Node {1}'.format(str(my_port), str(k))) 

def perform_dvr_update(nport, dport, cost):
        dv[dport] = cost
        rtng_tbl[dport] = rtng_tbl[nport]
        
        for k,v in dv.items():
                if nport in peer_dvs.keys() and\
                k in peer_dvs[nport].keys() and dv[nport] + peer_dvs[nport][k] < v:
                        dv[k] = dv[nport] + peer_dvs[nport][k]
                        rtng_tbl[k] = rtng_tbl[nport]
        #print('\nRoute to Node {0} now costs {1} through Node {2}'.format(dport, cost, nport)) 

def update_dv(nport, ts, msg):
        global my_port
        update = False
        peer_dv = dict()
        pmessage('Message recieved at Node {0} from Node {1}'.format(str(my_port), str(nport)))
        for i in range(0, len(msg), 2):
                try:
                        dport = Port(msg[i], False)
                        pcost = Cost(msg[i+1], False) 
                        cost = pcost + dv[nport]
                        peer_dv[dport] = pcost      
                        if dport == my_port:
                                continue
                        if dport not in dv.keys():
                                perform_dvr_update(nport, dport, cost)
                                update = True
                        elif dv[dport] > cost:                         
                                perform_dvr_update(nport, dport, cost)
                                update = True
                        #print('\n({0}) --> ({1}) :  {2}'.format(my_port, dport, dv[dport]))
                        #print('\n({0}) --> ({1}) --> ({2}) : {3}'.format(my_port, nport, dport ,cost))
                except Exception as e:
                        #print('\nException: ' + str(e))
                        raise e
                        return False
        latest[nport] =  ts
        peer_dvs[nport] = peer_dv
        display_rtng_tbl()        
        return update

def message_proc(sender_message, sock):
        global shared_tbl
        try:
                msg = sender_message.split()
                port = Port(msg[1], False)
        except:
                return        
        lock.acquire()
        isstale = False
        if port in latest.keys():
                isstale = float(msg[0]) < float(latest[port]) 
        if isstale:
                lock.release()
                return
        isupdated = update_dv(port, float(msg[0]), msg[2:])           
        lock.release()
        if isupdated:
                send_dv(sock)
        elif not shared_tbl:
                shared_tbl = True
                send_dv(sock)
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
                send_dv(my_sock)

        while(True):
                sender_msg, sender_addr = my_sock.recvfrom(SIZE) 
                pthread = threading.Thread(target = message_proc, args = (sender_msg.decode(), my_sock)) 
                pthread.start()


if __name__ == '__main__':
        main()
