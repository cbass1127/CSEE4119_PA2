import threading
import time
import os
from ls import start_ls
from util import *
from sys import argv

POISON = False #Poison-Reverse?
LAST = False #LAST CL param?
shared_tbl = False
my_port = -1
TIMER = -1 #Value that link-cost change gets set to
dv = dict() #distance vector for distance vector protocol.
rtng_tbl = dict() #next step in path to dests
lock = threading.Semaphore(1)
latest = dict()
peer_dvs = dict() #peer distance vectors
nlink_costs = dict() #costs to neighbors through direct links

def parse_peers():
        '''
        Reads in CL arguments specifying settings of dv mode e.g. timed link change 
        and neigboring nodes info.
        :return: peer_ports and peer_costs w/ neighboring ports and link costs 
        '''
        global LAST, TIMER, POISON
        peer_ports = []
        peer_costs = []
        ind = -1
        
        if argv[2] == 'p':
               POISON = True
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

def display_rtng_tbl():
        '''
        Prints current routing table.         
        :return: None  
        '''
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
        '''
        Intializes all datastructures for dv protocol.         
        :return: None  
        '''
        for i in range(len(peer_ports)):
                p_port = peer_ports[i]
                p_cost = peer_costs[i]
                dv[p_port] = p_cost
                rtng_tbl[p_port] = p_port
                nlink_costs[p_port] = p_cost
                latest[p_port] = time.time()
        dv[my_port] = 0
        rtng_tbl[my_port] = my_port

def node_init():
        '''
        parses CL args and fills intializes datastructures.         
        :return: None  
        '''
        peer_ports, peer_costs = parse_peers()
        init_state_info(peer_ports, peer_costs)
        display_rtng_tbl()    

def dv_msg(fake = False, fakedv = None):
        '''
        Formats special DV message to be sent to neigboring nodes.         
        :return: None  
        '''
        global my_port
        costmap = dv if not fake else fakedv
        s = str(time.time()) + ' ' + str(my_port) + ' '  
        for k,v in costmap.items():
                if k == my_port:
                        continue
                s+= str(k) + ' ' + str(v) + ' '
        return s               
 

#def send_dv(socket, individual = False, port = None, fakedv = None):
#        global my_port
#        if not individual:
#                dv_dgram = dv_msg().encode()
#                for k,v in dv.items():
#                        if k == my_port:
#                                continue
#                        Send(socket, dv_dgram, ('127.0.0.1', k))        
#                        pmessage('Message sent from Node {0} to Node {1}'.format(str(my_port), str(k)))
#        else:
#                dv_dgram = dv_msg(True, fakedv).encode()
                #dv_dgram = dv_msg().encode()
#                print('\nSENDING DGRAM {} to {}'.format(dv_dgram, port))
#                Send(socket, dv_dgram, ('127.0.0.1', port))


def find_rtng_keys(value):
        '''
        Finds associated key given a value(destination) of the rtng_tbl.         
        :return: Associated key
        '''
        keys = []
        for k,v in rtng_tbl.items():
                if v == value:
                        keys.append(k)
        return keys

def send_dv(socket):
        '''
        Sends DV to all neigbors. If in poisoned-reverse mode,
        send link cost of infinity to neighbor if it is used to reach a dest.         
        :return: None
        '''
        global my_port
        dv_dgram = dv_msg().encode()
        for k,v in dv.items():
                if k == my_port:
                        continue
                if POISON and k in rtng_tbl.values():
                        dests = find_rtng_keys(k)
                        fakedv = dv.copy()
                        for dest in dests:
                                fakedv[dest] = float('inf')
                        dv_dgram = dv_msg(True, fakedv).encode()
                Send(socket, dv_dgram, ('127.0.0.1', k))        
                pmessage('Message sent from Node {0} to Node {1}'.format(str(my_port), str(k)))

def perform_dvr_update(nport, dport, cost):
        '''
        Take neigbor DV and update distances and own dv if neccessary
        :return: None
        '''
        dv[dport] = cost
        rtng_tbl[dport] = rtng_tbl[nport]
        for k,v in dv.items():
                if nport in peer_dvs.keys() and\
                k in peer_dvs[nport].keys() and dv[nport] + peer_dvs[nport][k] < v:
                        dv[k] = dv[nport] + peer_dvs[nport][k]
                        rtng_tbl[k] = rtng_tbl[nport]

#def lie_to_neighbors(socket):
#        global my_port
#        print('\nLYING')
#        for k,v in dv.items():
#                if k == my_port:
#                        continue
#                fake_dv = dv.copy()
#                intermediate = rtng_tbl[k]
#                fake_dv[k] = float('inf')
#                send_dv(socket, True, intermediate, fake_dv)    
                
def check_cost_increase(nport, msg, ts):
        '''
        Check if a neighbors cost increased to a dest that we use.
        :return: Boolean indicating whether cost to dest increased.
        '''
        isincreased = False
        peer_dv = dict()
        if nport not in peer_dvs.keys():
                return False
        for i in range(0, len(msg), 2):
                try:
                        dport = Port(msg[i], False)
                        pcost = Cost(msg[i+1], False) 
                        cost = pcost + dv[nport]
                        peer_dv[dport] = pcost
                        if dport in peer_dvs[nport].keys() and peer_dvs[nport][dport] < pcost:
                                #print('\nPeer {} cost to {} increased from {} to {}'.format(nport, dport, peer_dvs[nport][dport], pcost))
                                isincreased = True     
                        peer_dv[dport] = pcost
                except Exception as e:
                        raise e
                        return True
        latest[nport] =  ts
        peer_dvs[nport] = peer_dv
        return isincreased

def recalibrate_state(socket):
        '''
        Update DV based on new information from neigbors 
        :return: True always (implentation kink).
        '''
        ischanged = False
        cost = -1 
        for dest in dv.keys():
                if dest not in rtng_tbl.keys() or\
                rtng_tbl[dest] not in peer_dvs.keys() or\
                dest not in peer_dvs[rtng_tbl[dest]].keys():
                        continue
                if dest in nlink_costs.keys() and nlink_costs[dest] < dv[rtng_tbl[dest]] + peer_dvs[rtng_tbl[dest]][dest]: 
                        cost = nlink_costs[dest]
                        dv[dest] = cost
                        rtng_tbl[dest] = dest
                else:
                        cost = dv[rtng_tbl[dest]] + peer_dvs[rtng_tbl[dest]][dest]
                        perform_dvr_update(rtng_tbl[dest], dest, cost) 
                #print('COST TO {} is CURRENTLY {}. COST TO dv[{}] = {};  peer_dvs[{}][{}] = {}'.format(dest, cost, rtng_tbl[dest], dv[rtng_tbl[dest]], rtng_tbl[dest], dest, peer_dvs[rtng_tbl[dest]][dest] ))
                for neighbor in nlink_costs.keys():
                    if dest not in peer_dvs[neighbor].keys():
                        continue
                    ncost = dv[neighbor] + peer_dvs[neighbor][dest]
                    if ncost < cost:
                        perform_dvr_update(neighbor, dest, ncost)
                        cost = ncost
                        ischanged = True    
        display_rtng_tbl()
        return True 

def update_min_path(affected_dests):
        '''
        Used for timed-linked change: update dv and shortest paths of destinations
        effected by link cost change
        :return: None.
        '''
        global my_port
        for dest in affected_dests:
                curr = dv[dest]
                for k,v in nlink_costs.items():
                        if k not in peer_dvs.keys():
                                continue 
                        if dest in peer_dvs[k].keys() and dv[k] + peer_dvs[k][dest] < curr:
                                perform_dvr_update(k, dest, dv[k] + peer_dvs[k][dest])
#                                dv[k] + peer_dvs[k][dest], dv[k], peer_dvs[k][dest]))  
                        elif dest == k and nlink_costs[k] < curr:
                                dv[dest] = nlink_costs[k]
                                rtng_tbl[dest] = k
        
        for k,v in nlink_costs.items():
                for k2,v2 in peer_dvs[k].items():
                        if k2 in dv.keys() and v2 + dv[k] < dv[k2]:
                                perform_dvr_update(k, k2, v2 + dv[k])

def affected_dests(node, diff):
        '''
        Check for destinations effected by a local link-cost change
        :return: effected destinations.
        '''
        affected = []
        for k,v in rtng_tbl.items():
                if v == node:
                        if k != v:
                                dv[k]+=diff
                        affected.append(k)
        return affected

def update_dv(nport, ts, msg, socket):
        '''
        Parse dv network message from neigbor. Check if updates need to be made to own dv
        :return: Boolean indicating whether an update was made.
        '''
        global my_port
        update = False
        peer_dv = dict()
        pmessage('Message recieved at Node {0} from Node {1}'.format(str(my_port), str(nport)))
        
        if check_cost_increase(nport, msg, ts):
                return recalibrate_state(socket)
                        
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
                        print('\nEXCEPTION: ' + str(e))
                        raise e
                        return False
        latest[nport] =  ts
        peer_dvs[nport] = peer_dv
        display_rtng_tbl()        
        return update


def trigger_update(port, diff):
        '''
        Helper function to perform timed-link cost change
        :return: Boolean indicating whether the link cost change effected local dv.
        '''
        changed = False
        affected = affected_dests(port, diff)
        update_min_path(affected)
        return len(affected) > 0

def triggered_change(socket, port, new_cost):
        ''' Main function that responds to message indicating a link-cost change from neigbor.
        :return: None.
        '''
        diff = new_cost - nlink_costs[port]
        local_change = False
        if dv[port] == nlink_costs[port]:
                dv[port] = new_cost
                local_change = True
        nlink_costs[port] = new_cost
        ischanged = trigger_update(port, diff)
        if ischanged or local_change:
                send_dv(socket)

def message_proc(sender_message, sock):
        ''' Main function responsible for parsing incoming mesage from neigbor.
        :return: None.
        '''
        global shared_tbl, my_port
        try:
                msg = sender_message.split()
                port = Port(msg[1], False)
        except:
                return        
        if msg[0] == 'LC':
                pmessage('Link value message recieved at Node {0} from Node {1}'.format(my_port, float(msg[3])))
                new_cost = float(msg[2])
                return triggered_change(sock, float(msg[3]), new_cost)
        lock.acquire()
        isstale = False
        if port in latest.keys():
                isstale = float(msg[0]) < float(latest[port]) 
        if isstale:
                lock.release()
                return
        isupdated = update_dv(port, float(msg[0]), msg[2:], sock)           
        lock.release()
        if isupdated:
                send_dv(sock)
        elif not shared_tbl:
                shared_tbl = True
                send_dv(sock)

def trigger_ctrl_msg(socket, port):
        ''' Create and send message indicating link-cost change to neighor.
        :return: None.
        '''
        global my_port
        linkc_dgram = ('LC ' + str(port) + ' ' + str(dv[port]) + ' ' + str(my_port)).encode() 
        Send(socket, linkc_dgram, ('127.0.0.1', port))        
        pmessage('Link value message sent from Node {0} to Node {1}'.format(my_port, port))

def trigger_change(socket):
        ''' Thread function responsible for initiating link-cost change Waits 30 seconds for changing cost.
        :return: None.
        '''
        global TIMER
        global my_port
        time.sleep(30) #CHANGE!!!!
        local_change = False
        ports = sorted(dv.keys())        
        max_port = ports[-1]
        if max_port == my_port:
               ports.pop(-1)
               max_port = ports[-1]
        if dv[max_port] == nlink_costs[max_port]:
                dv[max_port] = TIMER
                local_change = True
        diff = TIMER - nlink_costs[max_port]
        nlink_costs[max_port] = TIMER
        pmessage('Node {0} cost updated to {1}'.format(max_port, TIMER))
        trigger_ctrl_msg(socket, max_port)
        ischanged = trigger_update(max_port, diff)
        if ischanged or local_change:
                send_dv(socket)
def main():
        ''' Main function, initalizes theads for handling incoming requests and timed-link cost change if needed.
        :return: None.
        '''
        global LAST, TIMER, POISON, my_port, dv, rtng_tbl
        if len(argv)< 5:
                Die('Usage: routenode <dv/ls> <r/p> <update-interval> <local-port> <neighbor1-port> <cost-1> <neighbor2-port> <cost-2> ...'\
                    '[last][<cost-change>]'
                , False)    
        
        if argv[1] ==  'ls':
                return start_ls(argv) 

        my_port = Port(argv[4])
        my_sock = Socket(my_port) 
        node_init()
         
        if LAST:
                send_dv(my_sock)
        if TIMER > 0:
                tthread = threading.Thread(target = trigger_change, args = (my_sock,))
                tthread.start() 
        while(True):
                sender_msg, sender_addr = my_sock.recvfrom(SIZE) 
                pthread = threading.Thread(target = message_proc, args = (sender_msg.decode(), my_sock)) 
                pthread.start()


if __name__ == '__main__':
        main()
